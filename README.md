# Mercourier

Mercourier is a very simple notification bot that bridges GitHub repositories and Zulip servers. It keeps your team informed about repository activities by delivering customized GitHub notifications directly to your Zulip channels.

## What Mercourier Does

- Monitors GitHub repositories of your choice
- Delivers notifications about issues, pull requests, commits, and other GitHub events
- Integrates seamlessly with your Zulip workspace

## Why Use Mercourier?

Stay informed about your GitHub repositories without constantly checking GitHub or being overwhelmed by email notifications. Mercourier brings important updates directly to your team's communication platform, making it easier to track development activities and respond promptly to changes.

## Deploy

To deploy this project we used a basic DigitalOcean Droplet with an Arch-Linux image, once the droplet is configured this are the steps we took:

Inside the /opt folder

```bash
git clone git@github.com:rladaga/mercourier.git
```

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
WorkingDirectory=/opt/mercourier
Environment=PATH=/opt/mercourier/venv/bin
ExecStart=/opt/mercourier/venv/bin/python /opt/mercourier/main.py
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

The -d flag enables the debug mode so the bot doesn't send the messages to each Zulip topic.

```
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements.txt
python3 main.py -d
```
