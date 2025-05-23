import json
import os
import time
from datetime import datetime
import logging
from pathlib import Path
import requests

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

HANDLERS = {
    "PushEvent",  # Will map to commits
    "IssuesEvent",  # Will map to issues
    "PullRequestEvent",  # Will map to merge requests
    "IssueCommentEvent",  # Will map to issue notes
}


class RateLimitExceeded(Exception):
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message)


class GitLab:
    def __init__(
        self,
        repositories=[],
        private_token=None,
        check_interval_s=60 * 60 * 3,
        last_check_file: Path = Path("last_check_gitlab.json"),
        on_event=lambda e: None,
    ):
        self.repositories = repositories
        self.private_token = private_token
        self.last_check = {}  # {repo: {"commits": sha, "issues": iid, ...}}
        self.last_check_file = last_check_file
        self.on_event = on_event
        self.check_interval_s = check_interval_s
        self.current_repo_index = 0

        logger.info("GitLab bot initialized successfully")
        self.load_last_check()

        for repo in repositories:
            if repo not in self.last_check:
                self.add_repository(repo)

    def save_last_check(self):
        with open(self.last_check_file, "w") as file:
            json.dump(self.last_check, file, indent=4)
        logger.info("Last check state saved to file")

    def load_last_check(self):
        if os.path.exists(self.last_check_file):
            with open(self.last_check_file, "r") as file:
                self.last_check = json.load(file)
            logger.info("Last check state loaded from file")
        else:
            logger.info(
                "Last check file not found. State will be initialized when repositories are added."
            )

    def add_repository(self, repo_name):
        self.last_check[repo_name] = {
            "commits": None,
            "issues": None,
            "mrs": None,
            "notes": {},
        }
        logger.info(f"Added repository: {repo_name}")

    def _headers(self):
        return {"PRIVATE-TOKEN": self.private_token} if self.private_token else {}

    def _project_id(self, repo_name):
        return requests.utils.quote(repo_name, safe="")

    def fetch_commits(self, repo_name):
        url = f"https://gitlab.com/api/v4/projects/{self._project_id(repo_name)}/repository/commits"  # Por default solo trae de master/main
        return requests.get(url, headers=self._headers())

    def fetch_issues(self, repo_name):
        url = f"https://gitlab.com/api/v4/projects/{self._project_id(repo_name)}/issues"
        return requests.get(url, headers=self._headers())

    def fetch_merge_requests(self, repo_name):
        url = f"https://gitlab.com/api/v4/projects/{self._project_id(repo_name)}/merge_requests"
        return requests.get(url, headers=self._headers())

    def fetch_issue_notes(self, repo_name, issue_iid):
        url = f"https://gitlab.com/api/v4/projects/{self._project_id(repo_name)}/issues/{issue_iid}/notes"
        return requests.get(url, headers=self._headers())

    def process_commits(self, repo_name, commits):
        last_sha = self.last_check[repo_name]["commits"]
        new_commits = []
        for commit in reversed(commits):
            if last_sha and commit["id"] <= last_sha:
                continue
            new_commits.append(commit)
            self.last_check[repo_name]["commits"] = commit["id"]
            event = {
                "type": "PushEvent",
                "payload": {"commit": commit, "ref": "refs/heads/master"},
                "repo": {"name": repo_name},
            }
            self.handle_event(event)
        return new_commits

    def process_issues(self, repo_name, issues):
        last_iid = self.last_check[repo_name]["issues"]
        new_issues = []
        for issue in reversed(issues):
            if last_iid and issue["iid"] <= last_iid:
                continue
            new_issues.append(issue)
            self.last_check[repo_name]["issues"] = issue["iid"]
            event = {
                "type": "IssuesEvent",
                "payload": {"issue": issue},
                "repo": {"name": repo_name},
            }
            self.handle_event(event)
        return new_issues

    def process_merge_requests(self, repo_name, mrs):
        last_iid = self.last_check[repo_name]["mrs"]
        new_mrs = []
        for mr in reversed(mrs):
            if last_iid and mr["iid"] <= last_iid:
                continue
            new_mrs.append(mr)
            self.last_check[repo_name]["mrs"] = mr["iid"]
            event = {
                "type": "PullRequestEvent",
                "payload": {"pull_request": mr},
                "repo": {"name": repo_name},
            }
            self.handle_event(event)
        return new_mrs

    def process_issue_notes(self, repo_name, issue):
        iid = issue["iid"]
        last_note_id = self.last_check[repo_name]["notes"].get(str(iid))
        notes_resp = self.fetch_issue_notes(repo_name, iid)
        if notes_resp.status_code != 200:
            logger.error(f"Failed to fetch notes for issue {iid} in {repo_name}")
            return
        notes = notes_resp.json()
        for note in reversed(notes):
            if last_note_id and note["id"] <= last_note_id:
                continue
            self.last_check[repo_name]["notes"][str(iid)] = note["id"]
            event = {
                "type": "IssueCommentEvent",
                "payload": {"comment": note, "issue": issue},
                "repo": {"name": repo_name},
            }
            self.handle_event(event)

    def check_repository_events(self, repo_name):
        # Commits
        commits_resp = self.fetch_commits(repo_name)
        if commits_resp.status_code == 200:
            self.process_commits(repo_name, commits_resp.json())
        # Issues
        issues_resp = self.fetch_issues(repo_name)
        if issues_resp.status_code == 200:
            issues = issues_resp.json()
            self.process_issues(repo_name, issues)
            for issue in issues:
                self.process_issue_notes(repo_name, issue)
        # Merge Requests
        mrs_resp = self.fetch_merge_requests(repo_name)
        if mrs_resp.status_code == 200:
            self.process_merge_requests(repo_name, mrs_resp.json())

    def handle_event(self, event):
        if not event:
            logger.error("Empty event data")
            return
        self.on_event(event)

    def run(self):
        logger.info(
            f"GitLab bot started, monitoring repositories: {', '.join(self.last_check.keys())}"
        )
        while True:
            try:
                total_repos = len(self.repositories)
                for i in range(self.current_repo_index, total_repos):
                    repo_name = self.repositories[i]
                    self.check_repository_events(repo_name)
                    self.current_repo_index = (i + 1) % total_repos
            except RateLimitExceeded:
                logger.warning(
                    f"Rate limit exceeded while checking {self.repositories[self.current_repo_index]}"
                )
                logger.info("Waiting for rate limit reset...")
                time.sleep(60 * 60)
                continue
            self.current_repo_index = 0
            time.sleep(self.check_interval_s)
