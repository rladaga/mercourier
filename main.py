from bot import GitHubZulipBot, load_config
import logging
import argparse
logger = logging.getLogger('bot')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():

    logger.info("Starting bot...")
    # last_time=open("last_time.txt","r").read();

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", action='store_true', help="Enable debug mode")
    args = parser.parse_args()

    zulip_on = not args.d

    try:

        config = load_config()

        bot = GitHubZulipBot(
            github_token=config['github_token'],
            zulip_email=config['zulip_email'],
            zulip_api_key=config['zulip_api_key'],
            zulip_site=config['zulip_site'],
            stream_name=config['zulip_stream'],
            zulip_on=zulip_on
        )

        bot.load_last_check()

        for repo in config['repositories']:
            if repo not in bot.last_check:
                bot.add_repository(repo)

        bot.run(check_interval=1800)

    except InterruptedError or KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        # with open("last_time.txt","w") as file:
        #     file.write(str(bot.last_time));
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

    logger.info("Closing bot...")


if __name__ == "__main__":
    main()
