import os
from dotenv import load_dotenv


def load_config():
    """Load configuration from environment variables."""
    load_dotenv()

    required_vars = [
        'GITHUB_TOKEN',
        'ZULIP_EMAIL',
        'ZULIP_API_KEY',
        'ZULIP_SITE',
        'ZULIP_STREAM',
        'GITHUB_REPOS'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}")

    return {
        'github_token': os.getenv('GITHUB_TOKEN'),
        'zulip_email': os.getenv('ZULIP_EMAIL'),
        'zulip_api_key': os.getenv('ZULIP_API_KEY'),
        'zulip_site': os.getenv('ZULIP_SITE'),
        'zulip_stream': os.getenv('ZULIP_STREAM'),
        'repositories': [repo.strip() for repo in os.getenv('GITHUB_REPOS').split(',')]
    }
