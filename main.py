from bot import GitHubZulipBot, load_config, mercourier_logger
import argparse
import signal


def main():

    mercourier_logger.info("Starting bot...")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zulip-off", action="store_true", help="Turn off Zulip notifications"
    )
    args = parser.parse_args()

    zulip_on = not args.zulip_off

    config = load_config()

    bot = GitHubZulipBot(
        zulip_email=config.get("zulip_email"),
        zulip_api_key=config.get("zulip_api_key"),
        zulip_site=config.get("zulip_site"),
        stream_name=config.get("zulip_stream"),
        repositories=config.get("repositories"),
        zulip_on=zulip_on,
    )

    def handle_signal(signum, frame):
        mercourier_logger.debug(
            f"Received {signal.Signals(signum).name}. Saving last check and exiting..."
        )
        bot.save_last_check()
        mercourier_logger.info("Closing bot...")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    bot.run(check_interval=config.get("check_interval"))


if __name__ == "__main__":
    main()
