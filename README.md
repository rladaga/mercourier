# Mercourier

A Github-to-Zulip notification bot that keeps your team in the loop. Mercourier brings all the info you need to where conversations already happen.

## What It Does

Mercourier watches any GitHub repos and sends important events directly to your Zulip channels:

- Issue and PR activity, including comments
- Code pushes
- Self-monitoring (sends its own logs to a dedicated Zulip topic)

### GitHub Events to Zulip Topics Mapping

Here you can see which events are currently handled.
Those not in this list are ignored.

| GitHub Event      | Description                     | Zulip Topic Format                  |
| ----------------- | ------------------------------- | ----------------------------------- |
| PushEvent         | Code pushed to repository       | `{repo_name}/push/{branch}`         |
| IssuesEvent       | Issue opened, closed, etc.      | `{repo_name}/issues/{issue_number}` |
| PullRequestEvent  | PR opened, closed, merged, etc. | `{repo_name}/pr/{pr_number}`        |
| IssueCommentEvent | Comment on an issue             | `{repo_name}/issues/{issue_number}` |
| IssueCommentEvent | Comment on a PR                 | `{repo_name}/pr/{pr_number}`        |
| Log messages      | Bot's internal logs             | `log/{LOG_LEVEL}`                   |

## Setting Up the Bot

Getting your own Mercourier running is quite simple:

1. Head to your Zulip settings (click the gear by your profile pic)
2. Navigate to Personal settings → Bots → Add a new bot
3. Choose "Generic bot", give it a name you'll recognize
4. After creation, copy the API key and bot email
5. Put these into your `config_and_secrets.py` file (see the [`config_and_secrets.example.py`](./config_and_secrets.example.py) file for a template)
6. Add the repos you want to monitor in the same config and secrets file.

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
# Populate config_and_secrets.py, see the example in config_and_secrets.example.py
./install.sh
```

Mercourier also includes an [`update.sh`](./update.sh) script that easily fetch the latest changes and restarts the service.

## Development

First you will need to install [`uv`](https://github.com/astral-sh/uv)

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

## Known Issues

- Edited Issue or PR bodies are not detected:  
  GitHub does not emit an event when someone edits the body of an existing Issue or Pull Request.  
  This means Mercourier might display outdated information if the body was modified after it was first created.

## Roadmap

- Implement asynchronous sending of messages to Zulip using queues.
- Add support for configuring active hours for when messages are sent.
- Add support for GitLab repositories.
- Add interactive capabilities: users will be able to send commands to the bot to perform certain actions.
