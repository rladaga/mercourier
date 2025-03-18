import json
import re
import os
from requests import get
from zulip import Client
import time
from datetime import datetime, timezone, timedelta
import logging

debug_logger = logging.getLogger('debug_logger')
error_logger = logging.getLogger('error_logger')
info_logger = logging.getLogger('info_logger')

logger = logging.getLogger('bot')


class ZulipHandler(logging.Handler):
    def __init__(self, zulip_client, stream_name, topic):
        super().__init__()
        self.zulip_client = zulip_client
        self.stream_name = stream_name
        self.topic = topic

    def emit(self, record):
        log_entry = self.format(record)
        request = {
            "type": "stream",
            "to": self.stream_name,
            "topic": self.topic,
            "content": log_entry
        }
        self.zulip_client.send_message(request)


class GitHubZulipBot:
    def __init__(self, zulip_email=None, zulip_api_key=None, zulip_site=None, stream_name=None, repositories=None, zulip_on=True, last_check_file="last_check.json"):
        """Initialize the bot with Zulip credentials."""

        self.stream_name = stream_name
        self.repositories = repositories
        self.last_check_etag = {}
        self.processed_events = {}
        self.zulip_on = zulip_on
        self.last_check_file = last_check_file

        self.handlers = {
            "PushEvent": self.handle_push_event,
            "IssuesEvent": self.handle_issue_event,
            "PullRequestEvent": self.handle_pr_event,
            "IssueCommentEvent": self.handle_comment_event,
        }

        info_logger.info("Bot initialized successfully")

        if self.zulip_on:
            self.zulip = Client(
                email=zulip_email,
                api_key=zulip_api_key,
                site=zulip_site
            )

            zulip_handler = ZulipHandler(
                self.zulip, stream_name, "log/DEBUG")
            zulip_handler.setLevel(logging.DEBUG)
            zulip_handler.setFormatter(logging.Formatter(
                '*%(asctime)s* - **%(name)s** - `%(levelname)s`\n\n%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            debug_logger.addHandler(zulip_handler)

            error_handler = ZulipHandler(
                self.zulip, stream_name, "log/ERROR")
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(
                '*%(asctime)s* - **%(name)s** - `%(levelname)s`\n\n%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            error_logger.addHandler(error_handler)

            info_handler = ZulipHandler(
                self.zulip, stream_name, "log/INFO")
            info_handler.setLevel(logging.INFO)
            info_handler.setFormatter(logging.Formatter(
                '*%(asctime)s* - **%(name)s** - `%(levelname)s`\n\n%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            info_logger.addHandler(info_handler)

            info_logger.info(
                f"Zulip client connected to {zulip_site} as {zulip_email}")
        else:
            info_logger.info("Zulip client not connected (debug mode)")

        self.load_last_check()

        for repo in repositories:
            if repo not in self.last_check_etag:
                self.add_repository(repo)

    def save_last_check(self):
        """ Save last check etag for all repositories to file. """
        state_data = {}
        for repo_name, last_etag in self.last_check_etag.items():
            state_data[repo_name] = {
                'last_etag': last_etag,
                'processed_events': self.processed_events[repo_name]
            }

        with open(self.last_check_file, 'w') as file:
            json.dump(state_data, file)
        info_logger.info(
            "Last check etag and processed events saved to file")

    def load_last_check(self):
        """ Load last check etag and processed events from file. """

        if os.path.exists(self.last_check_file):
            with open(self.last_check_file, 'r') as file:
                state_data = json.load(file)

            for repo_name, data in state_data.items():

                self.last_check_etag[repo_name] = data['last_etag']

                self.processed_events[repo_name] = data['processed_events']

                info_logger.info(
                    f"Added repository: {repo_name} with ETag {self.last_check_etag[repo_name]}")

            info_logger.info(
                "Last check etag and processed events loaded from file")
        else:
            info_logger.info(
                "Last check file not found. State will be initialized when repositories are added.")

    def add_repository(self, repo_name):
        """Add a repository to monitor."""
        self.last_check_etag[repo_name] = ""
        self.processed_events[repo_name] = None
        info_logger.info(
            f"Added repository: {repo_name} with last ETag: {self.last_check_etag[repo_name]}")

    def send_zulip_message(self, topic, content):
        """Send a message to Zulip stream."""
        request = {
            "type": "stream",
            "to": self.stream_name,
            "topic": topic,
            "content": content
        }

        if self.zulip_on:
            response = self.zulip.send_message(request)
            if response['result'] != 'success':
                error_logger.error(f"Failed to send message: {response}")
        else:
            info_logger.info(
                f"Debug mode: Message not sent to Zulip: {request}")

    def check_repository_events(self, repo_name):
        """Checks new events in every repo."""

        try:
            events = get(f"https://api.github.com/repos/{repo_name}/events",
                         headers={'If-None-Match': self.last_check_etag[repo_name]})

            if events.status_code == 304:
                info_logger.info(
                    f"Checking events for {repo_name}...No new events.")
                return

            events_json = json.loads(events.content)
            etag = events.headers['ETag']

            self.last_check_etag[repo_name] = etag

            logger.info(
                f"Last ETag for {repo_name}: {self.last_check_etag[repo_name]}")

            for event in reversed((events_json)):
                logger.info(
                    f"Found event: {event['type']} at {event['created_at']}")
                event_id = event['id']

                if self.processed_events[repo_name] and event_id <= self.processed_events[repo_name]:
                    logger.info(
                        f"Skipping already processed event: {event['type']} at {event['created_at']}")
                    continue

                self.processed_events[repo_name] = event_id
                logger.info(f"Processing event: {event['type']} ({event_id})")

                handler = self.handlers.get(event['type'])
                if handler:
                    handler(repo_name, event)

            info_logger.info(
                f"Checking events for {repo_name}...Found events, updating last etag to {etag}")

        except Exception as e:
            error_logger.error(
                f"Unexpected error while checking {repo_name}: {str(e)}")

    def handle_push_event(self, repo_name, event):
        """Handle push events."""
        try:
            event_data = event
            if not event_data:
                error_logger.error("Empty event data received for push event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                error_logger.error("No payload found in event data")
                return

            commits = payload.get('commits', [])
            ref = payload.get('ref', '')

            if not ref:
                error_logger.error(f"Missing ref in payload: {payload}")
                return

            branch = ref.split('/')[-1]

            message = f"🔨 {len(commits)} by [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')})\n\n"

            pr_pattern = re.compile(r'\(#(\d+)\)')

            if commits:
                for commit in commits:

                    commit_msg = commit.get(
                        'message', 'No message').split('\n')[0]
                    commit_sha = commit.get(
                        'id', commit.get('sha', 'unknown'))[:7]
                    commit_url = f"https://github.com/{repo_name}/commit/{commit_sha}"

                    print(commit_url)

                    pr_match = pr_pattern.search(commit_msg)
                    if pr_match:
                        pr_number = pr_match.group(1)
                        pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
                        commit_msg = pr_pattern.sub(
                            f'([#{pr_number}]({pr_url}))', commit_msg)

                    commit_time = datetime.strptime(
                        event_data.get('created_at'), "%Y-%m-%dT%H:%M:%SZ")
                    commit_time_str = commit_time.strftime("%Y-%m-%d %H:%M:%S")

                    message += f"- {commit_msg} ([`{commit_sha}`]({commit_url})) at {commit_time_str}\n"

            else:
                message += "\nNo commits found in push event."

            if payload.get('forced'):
                message += "\n⚠️ This was a force push!\n"

            if payload.get('created'):
                message += f"\n🆕 Branch `{branch}` was created\n"

            if payload.get('deleted'):
                message += f"\n❌ Branch `{branch}` was deleted\n"

            self.send_zulip_message(
                topic=f"{repo_name}/push/{branch}",
                content=message
            )

        except Exception as e:
            error_logger.error(f"Error handling push event: {str(e)}")
            debug_logger.debug(f"Problematic event data: {event}")

    def handle_issue_event(self, repo_name, event):
        """Handle issue events."""
        try:
            event_data = event
            if not event_data:
                error_logger.error("Empty event data received for issue event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                error_logger.error("No payload found in event data")
                return

            issue = payload.get('issue', {})
            action = payload.get('action', '')

            url = issue.get('html_url')
            number = issue.get('number')
            if not url:
                url = f"https://github.com/{repo_name}/issues/{number}"

            created_at = issue.get('created_at')
            if created_at:
                created_at = datetime.strptime(
                    created_at, "%Y-%m-%dT%H:%M:%SZ")
                created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = "Unknown"

            message = f"📝 Issue [#{number}]({url}) {action}\n\n"

            message += "| **Title** | " + \
                issue.get('title', 'No title') + " |\n"
            message += "|-------|-------|\n"
            message += f"| Author | [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) |\n"
            message += f"| Date | {created_at_str} |\n"

            if issue.get('labels'):
                labels = [label.get('name', '') for label in issue['labels']]
                if labels:
                    message += f"| Labels | {', '.join(labels)} |\n"

            if action == 'opened' and issue.get('body'):
                body = issue.get('body', '').strip()

                message += f"{body}\n"

            if issue.get('comments'):
                message += f"| Comments | {issue['comments']} |\n"

            if action == 'closed':
                closed_at = issue.get('closed_at')
                if closed_at:
                    closed_at = datetime.strptime(
                        closed_at, "%Y-%m-%dT%H:%M:%SZ")
                    closed_at_str = closed_at.strftime("%Y-%m-%d %H:%M:%S")
                    message += f"| Closed at | {closed_at_str} |\n"

                state_reason = issue.get('state_reason')
                if state_reason:
                    message += f"| Reason | {state_reason} |\n"

            self.send_zulip_message(
                topic=f"{repo_name}/issues/{number}",
                content=message
            )

        except Exception as e:
            error_logger.error(f"Error handling issue event: {str(e)}")
            debug_logger.debug(f"Problematic event data: {event}")

    def handle_pr_event(self, repo_name, event):
        """Handle pull request events."""
        try:
            event_data = event
            if not event_data:
                error_logger.error("Empty event data received for PR event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                error_logger.error("No payload found in event data")
                return

            pr = payload.get('pull_request', {})
            action = payload.get('action', '')

            if not pr or not action:
                error_logger.error(
                    f"Missing PR or action in payload: {payload}")
                return

            url = pr.get('html_url')
            number = pr.get('number')
            if not url:
                url = f"https://github.com/{repo_name}/pull/{number}"

            created_at = pr.get('created_at')
            if created_at:
                created_at = datetime.strptime(
                    created_at, "%Y-%m-%dT%H:%M:%SZ")
                created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = "Unknown"

            updated_at = pr.get('updated_at')
            if updated_at:
                updated_at = datetime.strptime(
                    updated_at, "%Y-%m-%dT%H:%M:%SZ")
                updated_at_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                updated_at_str = "Unknown"

            message = f"🔀 Pull request [#{number}]({url}) {action}\n\n"

            message += "| **Title** | " + pr.get('title', 'No title') + " |\n"
            message += "|-------|-------|\n"
            message += f"| Author | [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) |\n"
            message += f"| Created at | {created_at_str} |\n"
            message += f"| Changes | +{pr.get('additions', 0)} -{pr.get('deletions', 0)} |\n"
            message += f"| Files changed | {pr.get('changed_files', 0)} |\n"
            message += f"| Last updated | {updated_at_str} |\n"

            if action == 'opened' and pr.get('body'):
                body = pr.get('body', '').strip()
                if body:
                    body = body.replace("|", "\\|")
                    message += "\n**Description:**\n"
                    message += body

            if pr.get('labels'):
                labels = [label.get('name', '') for label in pr['labels']]
                if labels:
                    message += f"| Labels | {', '.join(labels)} |\n"

            self.send_zulip_message(
                topic=f"{repo_name}/pr/{number}",
                content=message
            )

        except Exception as e:
            error_logger.error(f"Error handling PR event: {str(e)}")
            debug_logger.debug(f"Problematic event data: {event}")

    def handle_comment_event(self, repo_name, event):
        """Handle issue and PR comment events."""
        try:
            event_data = event
            if not event_data:
                error_logger.error(
                    "Empty event data received for comment event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                error_logger.error("No payload found in event data")
                return

            comment = payload.get('comment', {})
            issue = payload.get('issue', {})

            if not comment or not issue:
                error_logger.error(
                    f"Missing comment or issue in payload: {payload}")
                return

            url = comment.get('html_url')
            number = issue.get('number')
            if not url:
                url = issue.get(
                    'html_url', f"https://github.com/{repo_name}/issues/{number}")

            created_at = comment.get('created_at')
            if created_at:
                created_at = datetime.strptime(
                    created_at, "%Y-%m-%dT%H:%M:%SZ")
                created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = "Unknown"

            message = f"💬 New comment on [#{number}]({url}) by [{event['actor'].get('login')}](https://github.com/{event['actor'].get('login')}) at {created_at_str}\n\n"
            message += f"# **Title**: {issue.get('title', 'Unknown title')}\n"

            body = comment.get('body', '').strip()
            message += f"## **Comment**:\n {body}\n"

            if 'pull_request' in issue:
                topic = f"{repo_name}/pr/{number}"
            else:
                topic = f"{repo_name}/issues/{number}"

            self.send_zulip_message(
                topic=topic,
                content=message
            )

        except Exception as e:
            error_logger.error(f"Error handling comment event: {str(e)}")
            debug_logger.debug(f"Problematic event data: {event}")

    def run(self, check_interval):
        """Run the bot with specified check interval (in seconds)."""
        info_logger.info(
            f"Bot started, monitoring repositories: {', '.join(self.last_check_etag.keys())}")

        while True:
            for repo_name in self.last_check_etag.keys():
                self.check_repository_events(repo_name)
            time.sleep(check_interval)
