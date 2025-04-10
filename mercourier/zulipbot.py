import logging
from zulip import Client
from .template import format_pr_event, format_push_event, format_issue_event, format_comment_event


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZulipHandler(logging.Handler):
    def __init__(self, zulip_client, stream_name):
        super().__init__()
        self.zulip_client = zulip_client
        self.stream_name = stream_name

    def emit(self, record):
        if record.levelno < self.level:
            return
        log_entry = self.format(record)
        topic = f"log/{record.levelname.upper()}"
        request = {
            "type": "stream",
            "to": self.stream_name,
            "topic": topic,
            "content": log_entry,
        }
        self.zulip_client.send_message(request)


class ZulipBot:
    def __init__(self,
        zulip_email=None,
        zulip_api_key=None,
        zulip_site=None,
        stream_name=None,
        zulip_on=True
    ):
        self.stream_name = stream_name
        self.zulip_client= None
        self.zulip_on = zulip_on

        if zulip_on:
            self.zulip_client = Client(
                email=zulip_email, api_key=zulip_api_key, site=zulip_site
            )

            self.log_handler = ZulipHandler(self.zulip_client, self.stream_name)
            self.log_handler.setFormatter(
                    logging.Formatter(
                    "*%(asctime)s* - **%(name)s** - `%(levelname)s`\n\n%(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )

            logger.addHandler(self.log_handler)
            self.log_handler.setLevel(logging.DEBUG)

            logger.info(
                f"Zulip client connected to {zulip_site} as {zulip_email}"
            )


    def on_event(self, event):
        repo_name = event['repo']['name']
        tipo = event['type']
        if tipo == "PushEvent":
            branch = event['payload']['ref'].split('/')[-1]

            message = format_push_event(event)

            self.send_message(topic=f"{repo_name}/push/{branch}", content=message)
        elif tipo == "IssuesEvent":
            number = event['payload']['issue']['number']

            message = format_issue_event(event)

            self.send_message(topic=f"{repo_name}/issues/{number}",content=message)
        elif tipo == "PullRequestEvent":
            number = event['payload']['pull_request']['number']

            message = format_pr_event(event)

            self.send_message(topic=f"{repo_name}/pr/{number}", content=message)
        elif tipo == "IssueCommentEvent":
            issue = event['payload']['issue']
            number = issue['number']

            message = format_comment_event(event)

            if "pull_request" in issue:
                topic = f"{repo_name}/pr/{number}"
            else:
                topic = f"{repo_name}/issues/{number}"
            self.send_message(topic=topic, content=message)


    def send_message(self, topic, content,):
        request = {
            "type": "stream",
            "to": self.stream_name,
            "topic": topic,
            "content": content,
        }
        
        logger.debug(f"Message not sent to Zulip: {content}") # When --zulip-off

        if self.zulip_on:
            response = self.zulip_client.send_message(request)
            if response["result"] != "success":
                logger.error(f"Failed to send message: {response}")
