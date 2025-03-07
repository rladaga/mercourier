from bot import GitHubZulipBot, load_config
import logging
import argparse
import signal
import sys

logger = logging.getLogger('bot')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():

    logger.info("Starting bot...")

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", action='store_true', help="Enable debug mode")
    args = parser.parse_args()

    zulip_on = not args.d

    try:

        config = load_config()

        bot = GitHubZulipBot(
            zulip_email=config.get('zulip_email'),
            zulip_api_key=config.get('zulip_api_key'),
            zulip_site=config.get('zulip_site'),
            stream_name=config.get('zulip_stream'),
            zulip_on=zulip_on
        )

        bot.load_last_check()

        for repo in config['repositories']:
            if repo not in bot.last_check_etag:
                bot.add_repository(repo)

        def handle_signal(signum, frame):
            logger.info(
                "Received signal to stop. Saving last check and exiting...")
            bot.save_last_check()
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        bot.run(check_interval=10800)

    except (InterruptedError, KeyboardInterrupt):
        logger.info("Bot stopped by user.")
        bot.save_last_check()
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        bot.save_last_check()
        raise

    logger.info("Closing bot...")


if __name__ == "__main__":
    main()
