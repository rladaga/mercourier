import os
from github import Github
from zulip import Client
import time
from datetime import datetime, timezone
import logging
from .config import load_config


logger = logging.getLogger(__name__)
# logger.removeHandlers()


class GitHubZulipBot:
    def __init__(self, github_token, zulip_email, zulip_api_key, zulip_site, stream_name, zulip_on=False):
        """Initialize the bot with GitHub and Zulip credentials."""
        self.github = Github(github_token)
        self.zulip = Client(
            email=zulip_email,
            api_key=zulip_api_key,
            site=zulip_site
        )
        self.stream_name = stream_name
        self.last_check = {}
        self.processed_events = {}
        self.zulip_on = zulip_on
        logger.info("Bot initialized successfully")

    def add_repository(self, repo_name):
        """Add a repository to monitor."""

        self.last_check[repo_name] = datetime.now(timezone.utc)
        self.processed_events[repo_name] = set()
        logger.info(
            f"Added repository: {repo_name} with initial check time set to {self.last_check[repo_name]}")

    def send_zulip_message(self, topic, content):
        """Send a message to Zulip stream."""
        request = {
            "type": "stream",
            "to": self.stream_name,
            "topic": topic,
            "content": content
        }
        # if self.zulip_on:
        #   self.zulip.send_message(request)
        # logger.debug(f"Message sent to Zulip: {request}")
        response = self.zulip.send_message(request)
        if response['result'] != 'success':
            logger.error(f"Failed to send message: {response}")

    def check_repository_events(self, repo_name):
        """Revisa eventos nuevos en el repositorio."""
        self.processed_events[repo_name] = set()

        try:
            logger.info(f"Checking events for {repo_name}...")
            repo = self.github.get_repo(repo_name)
            events = repo.get_events()

            logger.info(
                f"Last check time for {repo_name}: {self.last_check[repo_name]}")

            last_event_time = self.last_check[repo_name]

            for event in events:
                logger.info(f"Found event: {event.type} at {event.created_at}")
                event_id = event.id
                event_time = event.created_at

                if event_time <= last_event_time:
                    continue  # Cambiar en droplet
                if event_id in self.processed_events[repo_name]:
                    continue

                self.processed_events[repo_name].add(
                    event_id)
                logger.info(f"Processing event: {event.type} ({event_id})")

                handlers = {
                    "PushEvent": self.handle_push_event,
                    "IssuesEvent": self.handle_issue_event,
                    "PullRequestEvent": self.handle_pr_event,
                    "IssueCommentEvent": self.handle_comment_event,
                }

                handler = handlers.get(event.type)
                if handler:
                    handler(repo_name, event)
                else:
                    logger.info(f"Sin manejador para el evento: {event.type}")

                last_event_time = max(last_event_time, event_time)

            self.last_check[repo_name] = max(
                last_event_time, datetime.now(timezone.utc))
            logger.info(
                f"Actualizado el último check de {repo_name} a {last_event_time}")

        except Exception as e:
            logger.error(f"Error al revisar {repo_name}: {str(e)}")
            if "rate limit" in str(e).lower():
                logger.warning(
                    "Se alcanzó el límite de GitHub. Durmiendo 60 segundos...")
                time.sleep(60)

    def handle_push_event(self, repo_name, event):
        """Handle push events."""
        try:
            event_data = event.raw_data
            if not event_data:
                logger.error("Empty event data received for push event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                logger.error("No payload found in event data")
                return

            commits = payload.get('commits', [])
            ref = payload.get('ref', '')

            if not ref:
                logger.error(f"Missing ref in payload: {payload}")
                return

            branch = ref.split('/')[-1]

            message = f"🔨 New push by {event.actor.login} to `{branch}`\n\n"
            message += f"Number of commits: {len(commits)}\n"

            repo_url = event_data.get('repo', {}).get(
                'url', '').replace('api.github.com/repos', 'github.com')
            if repo_url:
                message += f"Repository: {repo_url}/tree/{branch}\n\n"

            if commits:
                for commit in commits:
                    try:
                        commit_msg = commit.get(
                            'message', 'No message').split('\n')[0]
                        commit_sha = commit.get(
                            'id', commit.get('sha', 'unknown'))[:7]
                        commit_url = (commit.get('url', '') or '').replace(
                            'api.github.com/repos', 'github.com')

                        if not commit_url:
                            commit_url = f"https://github.com/{repo_name}/commit/{commit_sha}"

                        message += f"- {commit_msg} ([`{commit_sha}`]({commit_url}))\n"
                    except Exception as e:
                        logger.error(
                            f"Error processing commit in push event: {str(e)}")
                        continue
            else:
                message += "\nNo commits found in push event."

            if payload.get('forced'):
                message += "\n⚠️ This was a force push!\n"

            if payload.get('created'):
                message += f"\n🆕 Branch `{branch}` was created\n"

            if payload.get('deleted'):
                message += f"\n❌ Branch `{branch}` was deleted\n"

            self.send_zulip_message(
                topic=f"{repo_name} Pushes",
                content=message
            )

        except Exception as e:
            logger.error(f"Error handling push event: {str(e)}")
            logger.debug(f"Problematic event data: {event.raw_data}")

    def handle_issue_event(self, repo_name, event):
        """Handle issue events."""
        try:
            event_data = event.raw_data
            if not event_data:
                logger.error("Empty event data received for issue event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                logger.error("No payload found in event data")
                return

            issue = payload.get('issue', {})
            action = payload.get('action', '')

            message = f"📝 Issue #{issue.get('number')} {action} by {event.actor.login}\n\n"

            title = issue.get('title', 'No title')
            message += f"**Title**: {title}\n"

            if action == 'opened' and issue.get('body'):
                body = issue.get('body', '').strip()
                if body:
                    if len(body) > 300:
                        body = body[:297] + "..."
                    message += f"**Description**: {body}\n"

            if issue.get('comments'):
                message += f"**Comments**: {issue['comments']}\n"

            if issue.get('labels'):
                labels = [label.get('name', '') for label in issue['labels']]
                if labels:
                    message += f"**Labels**: {', '.join(labels)}\n"

            url = issue.get('html_url')
            if not url:
                url = f"https://github.com/{repo_name}/issues/{issue.get('number')}"
            message += f"**URL**: {url}"

            if action == 'closed':
                closed_at = issue.get('closed_at')
                if closed_at:
                    message += f"\n**Closed at**: {closed_at}"

                state_reason = issue.get('state_reason')
                if state_reason:
                    message += f"\n**Reason**: {state_reason}"

            self.send_zulip_message(
                topic=f"{repo_name} Issues",
                content=message
            )

        except Exception as e:
            logger.error(f"Error handling issue event: {str(e)}")
            logger.debug(f"Problematic event data: {event.raw_data}")

    def handle_pr_event(self, repo_name, event):
        """Handle pull request events."""
        try:
            event_data = event.raw_data
            if not event_data:
                logger.error("Empty event data received for PR event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                logger.error("No payload found in event data")
                return

            pr = payload.get('pull_request', {})
            action = payload.get('action', '')

            if not pr or not action:
                logger.error(f"Missing PR or action in payload: {payload}")
                return

            message = f"🔀 Pull request #{pr.get('number')} {action} by {event.actor.login}\n\n"

            title = pr.get('title', 'No title')
            message += f"**Title**: {title}\n"

            if action == 'opened' and pr.get('body'):
                body = pr.get('body', '').strip()
                if body:
                    if len(body) > 300:
                        body = body[:297] + "..."
                    message += f"**Description**: {body}\n"

            message += f"**Changes**: +{pr.get('additions', 0)} -{pr.get('deletions', 0)}\n"
            message += f"**Files changed**: {pr.get('changed_files', 0)}\n"

            if pr.get('labels'):
                labels = [label.get('name', '') for label in pr['labels']]
                if labels:
                    message += f"**Labels**: {', '.join(labels)}\n"

            url = pr.get('html_url')
            if not url:
                url = f"https://github.com/{repo_name}/pull/{pr.get('number')}"
            message += f"**URL**: {url}"

            self.send_zulip_message(
                topic=f"{repo_name} Pull Requests",
                content=message
            )

        except Exception as e:
            logger.error(f"Error handling PR event: {str(e)}")
            logger.debug(f"Problematic event data: {event.raw_data}")

    def handle_comment_event(self, repo_name, event):
        """Handle issue and PR comment events."""
        try:
            event_data = event.raw_data
            if not event_data:
                logger.error("Empty event data received for comment event")
                return

            payload = event_data.get('payload', {})
            if not payload:
                logger.error("No payload found in event data")
                return

            comment = payload.get('comment', {})
            issue = payload.get('issue', {})

            if not comment or not issue:
                logger.error(f"Missing comment or issue in payload: {payload}")
                return

            message = f"💬 New comment on #{issue.get('number')} by {event.actor.login}\n\n"
            message += f"**On**: {issue.get('title', 'Unknown title')}\n"

            body = comment.get('body', '').strip()
            if body:
                if len(body) > 300:
                    body = body[:297] + "..."
                message += f"**Comment**: {body}\n"

            url = comment.get('html_url')
            if not url:
                url = issue.get(
                    'html_url', f"https://github.com/{repo_name}/issues/{issue.get('number')}")
            message += f"**URL**: {url}"

            if 'pull_request' in issue:
                topic = f"{repo_name} Pull Request Comments"
            else:
                topic = f"{repo_name} Issue Comments"

            self.send_zulip_message(
                topic=topic,
                content=message
            )

        except Exception as e:
            logger.error(f"Error handling comment event: {str(e)}")
            logger.debug(f"Problematic event data: {event.raw_data}")

    def run(self, check_interval):
        """Run the bot with specified check interval (in seconds)."""
        logger.info(
            f"Bot started, monitoring repositories: {', '.join(self.last_check.keys())}")

        while True:
            try:
                for repo_name in self.last_check.keys():
                    self.check_repository_events(repo_name)
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(60)
