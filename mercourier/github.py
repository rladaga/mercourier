import json
import os
from requests import get
import time
from datetime import datetime
import logging
from pathlib import Path


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

HANDLERS = {
    "PushEvent",
    "IssuesEvent",
    "PullRequestEvent",
    "IssueCommentEvent",
}


class RateLimitExcedeed(Exception):
    def __init__(self, message="Rate limit exceeded"):
        super().__init__(message)


class GitHub:
    def __init__(
        self,
        repositories=[],
        check_interval_s=60 * 60 * 3,
        last_check_file: Path = Path("last_check.json"),
        on_event=lambda e: None,
    ):
        self.repositories = repositories
        self.last_check_etag = {}
        self.processed_events = {}
        self.last_check_file = last_check_file
        self.on_event = on_event
        self.check_interval_s = check_interval_s
        self.current_repo_index = 0

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

            logger.info("Last check etag and processed events loaded from file")
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

    def fetch_repository_events(self, repo_name):
        events = get(
            f"https://api.github.com/repos/{repo_name}/events",
            headers={"If-None-Match": self.last_check_etag[repo_name]},
        )

        return events

    def handle_response(self, repo_name, response):
        rate_limit = response.headers.get("X-RateLimit-Remaining", "unknown")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset", "unknown")
        rate_limit_reset_time = datetime.fromtimestamp(int(rate_limit_reset))
        logger.debug(f"Rate limit remaining: {rate_limit}")

        if rate_limit == "0":
            logger.warning(f"Rate limit reset: {rate_limit_reset_time}")
            raise RateLimitExcedeed(
                f"Rate limit reached. Reset at {rate_limit_reset_time}"
            )

        if response.status_code == 304:
            logger.debug(f"Checking events for {repo_name}...No new events.")
            return

        if response.status_code == 404:
            logger.error(f"Repository {repo_name} not found.")
            self.last_check_etag.pop(repo_name, None)
            self.processed_events.pop(repo_name, None)
            return

        etag = response.headers.get("ETag")
        if etag is not None:
            self.last_check_etag[repo_name] = etag
            logger.debug(f"Checking events for {repo_name}.")
            logger.debug(
                f"Last ETag for {repo_name}: {self.last_check_etag[repo_name]}"
            )
        else:
            logger.warning(f"No ETag found in response for {repo_name}")
            return

        return json.loads(response.content)

    def process_events(self, repo_name, events_json):
        if not events_json:
            return

        for event in reversed((events_json)):
            if event["type"] not in HANDLERS:
                continue

            logger.debug(f"Found event: {event['type']} at {event['created_at']}")

            event_id = event["id"]
            if (
                self.processed_events[repo_name]
                and event_id <= self.processed_events[repo_name]
            ):
                logger.debug(
                    f"Skipping already processed event: {event['type']} at {event['created_at']}"
                )
                continue

            logger.debug(f"Processing event: {event['type']} ({event_id})")

            try:
                self.handle_event(event)
                self.processed_events[repo_name] = event_id
            except Exception as e:
                logger.error(f"Error processing event {event_id}: {e}", exc_info=True)

    def check_repository_events(self, repo_name):
        """Checks new events in every repo."""
        response = self.fetch_repository_events(repo_name)
        events_json = self.handle_response(repo_name, response)
        self.process_events(repo_name, events_json)

    def handle_event(self, event):
        if not event:
            logger.error("Empty event data")
            return

        self.on_event(event)

    def run(self):
        """Run the bot with specified check interval (in seconds)."""
        logger.info(
            f"Bot started, monitoring repositories: {', '.join(self.last_check_etag.keys())}"
        )

        while True:
            try:
                total_repos = len(self.repositories)
                for i in range(self.current_repo_index, total_repos):
                    repo_name = self.repositories[i]
                    self.check_repository_events(repo_name)
                    self.current_repo_index = (i + 1) % total_repos
            except RateLimitExcedeed:
                logger.warning(
                    f"Rate limit exceeded while checking {self.repositories[self.current_repo_index]}"
                )
                logger.info("Waiting for rate limit reset...")
                time.sleep(60 * 60)
                continue

            self.current_repo_index = 0
            time.sleep(self.check_interval_s)
