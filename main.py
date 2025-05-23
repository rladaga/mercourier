import argparse
import signal
import logging
from mercourier import GitHub, load_config, GitLab
from mercourier import ZulipBot


logging.getLogger("mercourier.github").setLevel(logging.DEBUG)
logging.getLogger("mercourier.zulipbot").setLevel(logging.DEBUG)
logging.getLogger("mercourier.gitlab").setLevel(logging.DEBUG)


def main():
    logger = logging.getLogger("Mercourier")
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(console_handler)
    logging.getLogger("mercourier.github").addHandler(console_handler)
    logging.getLogger("mercourier.gitlab").addHandler(console_handler)
    logger.info("Starting bot...")

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "config_path",
        nargs="?",
        default="config_and_secrets.py",
        help="Path to config file (default: config_and_secrets.py)",
    )
    parser.add_argument(
        "--zulip-off", action="store_true", help="Turn off Zulip notifications"
    )

    args = parser.parse_args()

    zulip_on = not args.zulip_off

    config = load_config(args.config_path)

    github = GitHub(
        **config["github"],
    )

    zulip = ZulipBot(
        **config["zulip"],
        zulip_on=zulip_on,
    )

    gitlab = GitLab(
        **config["gitlab"],
    )

    github.on_event = zulip.on_event
    gitlab.on_event = zulip.on_event
    logging.getLogger("mercourier.zulipbot").addHandler(console_handler)

    if zulip_on:
        zulip.log_handler.setLevel(logging.INFO)
        logger.addHandler(zulip.log_handler)
        logging.getLogger("mercourier.github").addHandler(zulip.log_handler)

    def handle_signal(signum, frame):
        logger.debug(
            f"Received {signal.Signals(signum).name}. Saving last check and exiting..."
        )
        github.save_last_check()
        logger.info("Closing bot...")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # github.run()
    gitlab.run()


if __name__ == "__main__":
    main()
