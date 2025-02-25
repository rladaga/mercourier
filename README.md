# Mercourier

Mercourier is a very simple notification bot that bridges GitHub repositories and Zulip servers. It keeps your team informed about repository activities by delivering customized GitHub notifications directly to your Zulip channels.

## What Mercourier Does

- Monitors GitHub repositories of your choice
- Delivers notifications about issues, pull requests, commits, and other GitHub events
- Sends it's own logs to an specific `Zulip` topic

## Why Use Mercourier?

Stay informed about your GitHub repositories without constantly checking GitHub or being overwhelmed by email notifications. Mercourier brings important updates directly to your team's communication platform, making it easier to track development activities and respond promptly to changes.

## Bot Configuration

To set up the bot and obtain the `ZULIP_EMAIL` and `ZULIP_API_KEY`, go to `Zulip` and click the configuration wheel next to your profile picture. Then, navigate to "Personal settings" → "Bots" → "Add a new bot". Select Generic bot as the bot type, enter a name and email of your choice, and click Add. Once created, you'll see the bot's `API KEY` and `BOT EMAIL`, which you need to add to the `.env` file.

Inside the `.env` file, specify each repository you want to be notified about in the `GITHUB_REPOS` variable. Refer to `.env.example` for guidance on the correct format.

You will also need a [Github Personal Access Token (classic)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic) placed in the `.env`

## Deploy/Installation

```bash
git clone git@github.com:rladaga/mercourier.git
```

Don't forget to create your `.env` file!

Then:

```bash
sudo pacman -S python python-pip python-virtualenv

cd mercourier

python -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

After this we created a systemd service to keep the bot running:

```bash
sudo nvim /etc/systemd/system/mercourier.service
```

and add this content:

```bash
[Unit]
Description=GitHub to Zulip Notification Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mercourier # Change if you cloned in other path than "/opt"
Environment=PATH=/opt/mercourier/venv/bin # Change if you cloned in other path than "/opt"
ExecStart=/opt/mercourier/venv/bin/python /opt/mercourier/main.py # Change if you cloned in other path than "/opt"
Restart=always

[Install]
WantedBy=multi-user.target
```

Then we start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable mercourier

# Start the service
sudo systemctl start mercourier

# Check the status
sudo systemctl status mercourier
```

## Instructions to debug locally

For the debug mode you will only need to have the `GITHUB_TOKEN` and `GITHUB_REPOS` variables set in the `.env`.
The -d flag enables the debug mode so the bot doesn't send the messages to Zulip and you can see all the logs in your console.

```
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt
python3 main.py -d
```
