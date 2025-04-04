import json
import re
import os
from requests import get
import time
from datetime import datetime
import logging
from pathlib import Path


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RateLimitExcedeed(Exception):
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message)

class GitHub:
    def __init__(
        self,
        repositories=[],
        check_interval_s=60*60*3,
        last_check_file: Path = Path("last_check.json"),
        on_event=lambda e: None,
    ):
        self.repositories = repositories
        self.last_check_etag = {}
        self.processed_events = {}
        self.last_check_file = last_check_file
        self.on_event = on_event
        self.check_interval_s = check_interval_s

        self.handlers = {
            "PushEvent": self.handle_push_event,
            "IssuesEvent": self.handle_issue_event,
            "PullRequestEvent": self.handle_pr_event,
            "IssueCommentEvent": self.handle_comment_event,
        }

        logger.info("Bot initialized successfully")

        self.load_last_check()

        for repo in repositories:
            if repo not in self.last_check_etag:
                self.add_repository(repo)

    def save_last_check(self):
        """Save last check etag for all repositories to file."""
        state_data = {}
        for repo_name, last_etag in self.last_check_etag.items():
            state_data[repo_name] = {
                "last_etag": last_etag,
                "processed_events": self.processed_events[repo_name],
            }

        with open(self.last_check_file, "w") as file:
            json.dump(state_data, file, indent=4)
        logger.info("Last check etag and processed events saved to file")

    def load_last_check(self):
        """Load last check etag and processed events from file."""

        if os.path.exists(self.last_check_file):
            with open(self.last_check_file, "r") as file:
                state_data = json.load(file)

            for repo_name, data in state_data.items():

                self.last_check_etag[repo_name] = data["last_etag"]

                self.processed_events[repo_name] = data["processed_events"]

                if repo_name not in self.repositories:
                    logger.info(
                        f"Repository {repo_name} not found in your repositories to check. Removing from the list."
                    )
                    self.last_check_etag.pop(repo_name, None)
                else:
                    logger.info(
                        f"Added repository: {repo_name} with ETag {self.last_check_etag[repo_name]}"
                    )

            logger.info(
                "Last check etag and processed events loaded from file"
            )
        else:
            logger.info(
                "Last check file not found. State will be initialized when repositories are added."
            )

    def add_repository(self, repo_name):
        """Add a repository to monitor."""
        self.last_check_etag[repo_name] = ""
        self.processed_events[repo_name] = None
        logger.info(
            f"Added repository: {repo_name} with last ETag: {self.last_check_etag[repo_name]}"
        )

    def check_repository_events(self, repo_name):
        """Checks new events in every repo."""


        events = get(
                f"https://api.github.com/repos/{repo_name}/events",
                headers={"If-None-Match": self.last_check_etag[repo_name]},
            )

        rate_limit = events.headers.get("X-RateLimit-Remaining", "unknown")
        rate_limit_reset = events.headers.get("X-RateLimit-Reset", "unknown")
        rate_limit_reset_time = datetime.fromtimestamp(int(rate_limit_reset))
        logger.debug(f"Rate limit remaining: {rate_limit}")


        if rate_limit == "0":
            logger.warning(f"Rate limit reset: {rate_limit_reset_time}")
            raise RateLimitExcedeed(f"Rate limit reached. Reset at {rate_limit_reset_time}")

        if events.status_code == 304:
            logger.debug(
                f"Checking events for {repo_name}...No new events."
            )
            return

        events_json = json.loads(events.content)
        etag = events.headers["ETag"]

        self.last_check_etag[repo_name] = etag

        logger.debug(
            f"Last ETag for {repo_name}: {self.last_check_etag[repo_name]}"
        )

        for event in reversed((events_json)):
            if event["type"] not in self.handlers:
                    continue
            logger.debug(
                    f"Found event: {event['type']} at {event['created_at']}"
                )
            event_id = event["id"]

            if (
                    self.processed_events[repo_name]
                    and event_id <= self.processed_events[repo_name]
                ):
                    logger.debug(
                        f"Skipping already processed event: {event['type']} at {event['created_at']}"
                    )
                    continue

            self.processed_events[repo_name] = event_id
            logger.debug(
                    f"Processing event: {event['type']} ({event_id})"
                )

            handler = self.handlers.get(event["type"])
            if handler:
                    logger.debug(
                        f"Checking events for {repo_name}...Found new event, updating last etag to {etag}"
                    )
                    handler(event)



    def handle_push_event(self, event):
        repo_name = event['repo']['name']

        event_data = event
        if not event_data:
            logger.error("Empty event data received for push event")
            return

        payload = event_data.get("payload", {})
        if not payload:
            logger.error("No payload found in event data")
            return

        commits = payload.get("commits", [])
        ref = payload.get("ref", "")

        if not ref:
            logger.error(f"Missing ref in payload: {payload}")
            return

        branch = ref.split("/")[-1]

        message = f"🔨 {len(commits)} by [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')})\n\n"

        pr_pattern = re.compile(r"\(#(\d+)\)")

        if commits:
            for commit in commits:

                commit_msg = commit.get("message", "No message").split("\n")[0]
                commit_sha = commit.get("id", commit.get("sha", "unknown"))[:7]
                commit_url = f"https://github.com/{repo_name}/commit/{commit_sha}"

                pr_match = pr_pattern.search(commit_msg)
                if pr_match:
                    pr_number = pr_match.group(1)
                    pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
                    commit_msg = pr_pattern.sub(
                        f"([#{pr_number}]({pr_url}))", commit_msg
                    )

                commit_time = datetime.strptime(
                    event_data.get("created_at"), "%Y-%m-%dT%H:%M:%SZ"
                )
                commit_time_str = commit_time.strftime("%Y-%m-%d %H:%M:%S")

                message += f"- {commit_msg} ([`{commit_sha}`]({commit_url})) at {commit_time_str}\n"

        else:
            message += "\nNo commits found in push event."

        if payload.get("forced"):
            message += "\n⚠️ This was a force push!\n"

        if payload.get("created"):
            message += f"\n🆕 Branch `{branch}` was created\n"

        if payload.get("deleted"):
            message += f"\n❌ Branch `{branch}` was deleted\n"

        event['_message'] = message
        self.on_event(event)

    def handle_issue_event(self, event):
        repo_name = event['repo']['name']

        event_data = event
        if not event_data:
            logger.error("Empty event data received for issue event")
            return

        payload = event_data.get("payload", {})
        if not payload:
            logger.error("No payload found in event data")
            return

        issue = payload.get("issue", {})
        action = payload.get("action", "")

        url = issue.get("html_url")
        number = issue.get("number")
        if not url:
            url = f"https://github.com/{repo_name}/issues/{number}"

        created_at = issue.get("created_at")
        if created_at:
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at_str = "Unknown"

        message = f"📝 Issue [#{number}]({url}) {action}\n\n"

        message += "| **Title** | " + issue.get("title", "No title") + " |\n"
        message += "|-------|-------|\n"
        message += f"| Author | [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) |\n"
        message += f"| Date | {created_at_str} |\n"

        if issue.get("labels"):
            labels = [label.get("name", "") for label in issue["labels"]]
            if labels:
                message += f"| Labels | {', '.join(labels)} |\n"

        if action == "opened" and issue.get("body"):
            body = issue.get("body", "").strip()
            if body:
                body = self.rewrite_github_issue_urls(body)

            message += f"\n{body}\n"

        if issue.get("comments"):
            message += f"| Comments | {issue['comments']} |\n"

        if action == "closed":
            closed_at = issue.get("closed_at")
            if closed_at:
                closed_at = datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
                closed_at_str = closed_at.strftime("%Y-%m-%d %H:%M:%S")
                message += f"| Closed at | {closed_at_str} |\n"

            state_reason = issue.get("state_reason")
            if state_reason:
                message += f"| Reason | {state_reason} |\n"

        event['_message'] = message
        self.on_event(event)

    def handle_pr_event(self, event):
        repo_name = event['repo']['name']

        event_data = event
        if not event_data:
            logger.error("Empty event data received for PR event")
            return

        payload = event_data.get("payload", {})
        if not payload:
            logger.error("No payload found in event data")
            return

        pr = payload.get("pull_request", {})
        action = payload.get("action", "")

        if not pr or not action:
            logger.error(f"Missing PR or action in payload: {payload}")
            return

        url = pr.get("html_url")
        number = pr.get("number")
        if not url:
            url = f"https://github.com/{repo_name}/pull/{number}"

        created_at = pr.get("created_at")
        if created_at:
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at_str = "Unknown"

        updated_at = pr.get("updated_at")
        if updated_at:
            updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
            updated_at_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            updated_at_str = "Unknown"

        message = f"🔀 Pull request [#{number}]({url}) {action}\n\n"

        message += "| **Title** | " + pr.get("title", "No title") + " |\n"
        message += "|-------|-------|\n"
        message += f"| Author | [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) |\n"
        message += f"| Created at | {created_at_str} |\n"
        message += (
            f"| Changes | +{pr.get('additions', 0)} -{pr.get('deletions', 0)} |\n"
        )
        message += f"| Files changed | {pr.get('changed_files', 0)} |\n"
        message += f"| Last updated | {updated_at_str} |\n"

        if action == "opened" and pr.get("body"):
            body = pr.get("body", "").strip()
            if body:
                body = self.rewrite_github_issue_urls(body)
                body = self.rewrite_issue_numbers(body, repo_name)
                body = body.replace("|", "\\|")
                message += "\n**Description:**\n"
                message += body

        if pr.get("labels"):
            labels = [label.get("name", "") for label in pr["labels"]]
            if labels:
                message += f"| Labels | {', '.join(labels)} |\n"

        event['_message'] = message
        self.on_event(event)

    def handle_comment_event(self, event):
        repo_name = event['repo']['name']

        event_data = event
        if not event_data:
            logger.error("Empty event data received for comment event")
            return

        payload = event_data.get("payload", {})
        if not payload:
            logger.error("No payload found in event data")
            return

        comment = payload.get("comment", {})
        issue = payload.get("issue", {})

        if not comment or not issue:
            logger.error(
                f"Missing comment or issue in payload: {payload}"
            )
            return

        url = comment.get("html_url")
        number = issue.get("number")
        if not url:
            url = issue.get("html_url", f"https://github.com/{repo_name}/issues/{number}")

        created_at = comment.get("created_at")
        if created_at:
            created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
            created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_at_str = "Unknown"

        message = f"💬 New comment on [{issue.get('title')}]({url}) by [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) at {created_at_str}\n\n"

        body = comment.get("body", "").strip()
        if body:
            body = self.rewrite_github_issue_urls(body)
        message += f"\n{body}\n"

        event['_message'] = message
        self.on_event(event)

    def rewrite_issue_numbers(self, body, repo_name):
        """Rewrite issue numbers (e.g., #7784) as markdown links."""

        issue_number_pattern = re.compile(r"#(\d+)\b")
        matches = issue_number_pattern.findall(body)

        for issue_number in matches:
            issue_url = f"https://github.com/{repo_name}/issues/{issue_number}"
            markdown_link = f"[#{issue_number}]({issue_url})"
            body = re.sub(rf"#{issue_number}\b", markdown_link, body)

        return body

    def rewrite_github_issue_urls(self, body):
        """Rewrite GitHub issue URLs in the comment body as [title](url)."""
        issue_url_pattern = re.compile(
            r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)"
        )
        matches = issue_url_pattern.findall(body)

        for match in matches:
            owner, repo, issue_number = match
            issue_url = f"https://github.com/{owner}/{repo}/issues/{issue_number}"



            response = get(
                f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
                headers={"Accept": "application/vnd.github.v3+json"},
                )
            if response.status_code == 200:
                issue_data = response.json()
                issue_title = issue_data.get("title", "Unknown Issue")
                markdown_link = f"[{issue_title}]({issue_url})"
                body = body.replace(issue_url, markdown_link)
            else:
                logger.error(
                    f"Failed to fetch issue details for {issue_url}: {response.status_code}"
                )

        return body

    def run(self):
        """Run the bot with specified check interval (in seconds)."""
        logger.info(
            f"Bot started, monitoring repositories: {', '.join(self.last_check_etag.keys())}"
        )

        while True:
            try:
                for repo_name in self.last_check_etag.keys():
                    self.check_repository_events(repo_name)
            except RateLimitExcedeed:
                time.sleep(60*30)
            time.sleep(self.check_interval_s)
