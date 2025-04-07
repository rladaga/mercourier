import json
import os
from requests import get
import time
from datetime import datetime
import logging
from pathlib import Path
from template import format_pr_event, format_push_event, format_issue_event, format_comment_event

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
        if not event:
            logger.error("Empty event data")
            return

        message = format_push_event(event)

        event['_message'] = message
        self.on_event(event)

    def handle_issue_event(self, event):
        if not event:
            logger.error("Empty event data")
            return

        message = format_issue_event(event)

        event['_message'] = message
        self.on_event(event)

    def handle_pr_event(self, event):
        if not event:
            logger.error("Empty event data")
            return

        message = format_pr_event(event)

        event['_message'] = message
        self.on_event(event)

    def handle_comment_event(self, event):
        if not event:
            logger.error("Empty event data")
            return

        message = format_comment_event(event)
        print(message)

        event['_message'] = message
        self.on_event(event)


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
