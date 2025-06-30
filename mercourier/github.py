import json
import os
import anyio
import anyio.to_thread
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
        accumulated_events_file: Path = Path("accumulated_events.json"),
        on_event=lambda e: None,
        send_channel=None,
        receive_channel=None,
        async_mode=False,
    ):
        self.repositories = repositories
        self.last_check_etag = {}
        self.processed_events = {}
        self.last_check_file = last_check_file
        self.accumulated_events_file = accumulated_events_file
        self.accumulated_events = []
        self.on_event = on_event
        self.send_channel = send_channel
        self.receive_channel = receive_channel
        self.check_interval_s = check_interval_s
        self.current_repo_index = 0
        self.async_mode = async_mode

        logger.info("Bot initialized successfully")

        self.load_last_check()
        if self.async_mode:
            self.load_accumulated_events()

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

        if self.async_mode:
            if self.accumulated_events:
                logger.info(
                    f"Saving {len(self.accumulated_events)} accumulated events to file"
                )
                self.save_accumulated_events()
            else:
                logger.info("No accumulated events to save")

    def save_accumulated_events(self):
        """Save accumulated events to file."""
        with open(self.accumulated_events_file, "w") as file:
            json.dump(self.accumulated_events, file, indent=4)
        logger.info(f"Saved {len(self.accumulated_events)} accumulated events to file")

    def load_accumulated_events(self):
        """Load accumulated events from file."""
        if os.path.exists(self.accumulated_events_file):
            try:
                with open(self.accumulated_events_file, "r") as file:
                    self.accumulated_events = json.load(file)
                logger.info(
                    f"Loaded {len(self.accumulated_events)} accumulated events from file"
                )
            except Exception as e:
                logger.error(f"Failed to load accumulated events: {e}")
                self.accumulated_events = []
        else:
            self.accumulated_events = []
            logger.info("Accumulated events file not found. Starting with empty list.")

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

    async def fetch_repository_events_async(self, repo_name):
        events = await anyio.to_thread.run_sync(
            lambda: get(
                f"https://api.github.com/repos/{repo_name}/events",
                headers={"If-None-Match": self.last_check_etag[repo_name]},
            )
        )

        return events

    async def run_producer(self):
        logger.info("Starting producer for GitHub events")

        while True:
            for repo_name in self.repositories:
                response = await self.fetch_repository_events_async(repo_name)

                event_pkg = {
                    "repo_name": repo_name,
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                }

                if self.send_channel:
                    await self.send_channel.send(event_pkg)
                    logger.debug(f"Sent event package for {repo_name} to channel")

            await anyio.sleep(self.check_interval_s)

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

        etag = response.headers["ETag"]
        self.last_check_etag[repo_name] = etag
        logger.debug(f"Checking events for {repo_name}.")
        logger.debug(f"Last ETag for {repo_name}: {self.last_check_etag[repo_name]}")

        return json.loads(response.content)

    async def event_accumulator(self, receive_channel):
        logger.info("Starting event accumulator")

        async with receive_channel:
            async for event_pkg in receive_channel:
                repo_name = event_pkg["repo_name"]
                response = event_pkg["response"]

                events_json = self.handle_response(repo_name, response)

                if events_json:
                    for event in reversed((events_json)):
                        if event["type"] not in HANDLERS:
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

                        self.accumulated_events.append(event)
                        logger.debug(
                            f"Accumulated event {event['type']} for {repo_name}. Total: {len(self.accumulated_events)}"
                        )

    async def daily_processor(self):
        logger.info("Starting daily processor")
        while True:
            await anyio.sleep(60 * 60 * 24)
            if self.accumulated_events:
                logger.info(
                    f"Processing {len(self.accumulated_events)} accumulated events"
                )
                for event in self.accumulated_events:
                    self.handle_event(event)
                self.accumulated_events.clear()
                self.save_accumulated_events()

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

            self.processed_events[repo_name] = event_id
            logger.debug(f"Processing event: {event['type']} ({event_id})")

            self.handle_event(event)

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
