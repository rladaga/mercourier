from bot import GitHubZulipBot, load_config
import logging
import argparse
import signal


logger = logging.getLogger('bot')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():

    logger.info("Starting bot...")

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", action='store_true', help="Enable debug mode")
    args = parser.parse_args()

    zulip_on = not args.d

    config = load_config()

    bot = GitHubZulipBot(
        zulip_email=config.get('zulip_email'),
        zulip_api_key=config.get('zulip_api_key'),
        zulip_site=config.get('zulip_site'),
        stream_name=config.get('zulip_stream'),
        repositories=config.get('repositories'),
        zulip_on=zulip_on
    )

    def handle_signal(signum, frame):
        logger.info(
            f"Received {signal.Signals(signum).name}. Saving last check and exiting...")
        bot.save_last_check()
        logger.info("Closing bot...")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    bot.run(check_interval=10800)


if __name__ == "__main__":
    main()
