# Mercourier

Mercourier is a very simple notification bot that bridges GitHub repositories and Zulip servers. It keeps your team informed about repository activities by delivering customized GitHub notifications directly to your Zulip channels.

## What Mercourier Does

- Monitors GitHub repositories of your choice
- Delivers notifications about issues, pull requests, commits, and other GitHub events
- Sends it's own logs to an specific `Zulip` topic

## Why Use Mercourier?

Stay informed about your GitHub repositories without constantly checking GitHub or being overwhelmed by email notifications. Mercourier brings important updates directly to your team's communication platform, making it easier to track development activities and respond promptly to changes.

## Bot Configuration

To set up the bot and obtain the `ZULIP_EMAIL` and `ZULIP_API_KEY`, go to `Zulip` and click the configuration wheel next to your profile picture. Then, navigate to "Personal settings" → "Bots" → "Add a new bot". Select Generic bot as the bot type, enter a name and email of your choice, and click Add. Once created, you'll see the bot's `API KEY` and `BOT EMAIL`, which you need to add to the `config_secrets.py` file.

Inside the `config_secrets.py` file, specify the repositories you want to monitor in the `repositories` list. Refer to `config_secrets.example.py` for guidance on the correct format.

## Installation

We chose to clone the repo in bare mode in the server and to use a worktree strategy,
creating different branches for each deployment we do.

```bash
git clone --bare git@github.com:rladaga/mercourier.git
cd mercourier
git worktree add ../${BRANCH_NAME} # The branch you will use for deployment
cd ../${BRANCH_NAME}
# Populate config_secrets.py
./install.sh
```
`install.sh` is meant to be run manually once.
Code above works on Arch Linux.
If you're using another distribution, you may need to modify `install.sh` accordingly.

Mercourier also includes an `update.sh` script that easily fetch the latest changes and restarts the service.

## Instructions to debug locally

For debug mode, ensure that the `repositories` list is correctly set in the `config_secrets.py` file.
The `--zulip-off` flag enables debug mode, preventing the bot from sending messages to Zulip while displaying all logs in the console.

```
python3 -m venv venv
venv/bin/pip3 install -r requirements.txt
venv/bin/python3 main.py --zulip-off
```
