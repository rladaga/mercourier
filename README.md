# Mercourier

A simple Github-to-Zulip notification bot that keeps your team in the loop, avoiding to miss important updates. Mercourier brings all the info you need to where conversations already happen.

## What It Does

Mercourier watches your GitHub repos and sends important events directly to your Zulip channels:
- Issue and PR activity, including comments
- Code pushes
- Self-monitoring (sends its own logs to a dedicated Zulip topic)

## Setting Up the Bot

Getting your own Mercourier running is quite simple:

1. Head to your Zulip settings (click the gear by your profile pic)
2. Navigate to Personal settings → Bots → Add a new bot
3. Choose "Generic bot", give it a name you'll recognize
4. After creation, copy the API key and bot email
5. Put these into your `config_secrets.py` file (see the `config_secrets.example.py` file for a template)
6. Add the repos you want to monitor in the same config file.

## Deployment

We chose to clone the repo in bare mode in the server and use a worktree strategy,
creating different branches for each deployment we do.

```bash
git clone --bare https://github.com/rladaga/mercourier.git
```

Create deployment branch locally and push it to the remote, this is what we refer below as ${BRANCH_NAME}.

Then for each deployment:
```bash
cd mercourier.git
git fetch --prune origin "+refs/heads/${BRANCH_NAME}:refs/heads/${BRANCH_NAME}" # The branch you will use for deployment
git worktree add ../${BRANCH_NAME} # The branch you will use for deployment
cd ../${BRANCH_NAME}
./os_dependencies.sh # Install required dependencies
# Populate config_secrets.py, see the example in config_secrets.example.py
./install.sh
```

Mercourier also includes an `update.sh` script that easily fetch the latest changes and restarts the service.

## Development

First you will need to install `uv`

### Local Debugging

When working on Mercourier locally, use the `--zulip-off` flag to avoid spamming your team channels.

```bash
uv run main.py --zulip-off
```

This shows everything in your console instead, so you can see what would be sent without actually sending it.

### Testing

```bash
uv run pytest
```

## Authors

- [@franalbani](https://github.com/franalbani)
- [@rladaga](https://github.com/rladaga)
- [@juanrunzio](https://github.com/juanrunzio)

## Contributors

- Be the first!
