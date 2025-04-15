from datetime import datetime
import re
import os
from requests import get
import logging

logger = logging.getLogger("mercourier.github")


def load_template(template_name):
    with open(os.path.join("templates", f"{template_name}.md"), encoding="utf-8") as f:
        return f.read()


PUSH_TEMPLATE = load_template("push_template")

COMMIT_TEMPLATE = load_template("commit_template")

ISSUE_TEMPLATE = load_template("issue_template")

PR_TEMPLATE = load_template("pr_template")

COMMENT_TEMPLATE = load_template("comment_template")


def rewrite_issue_numbers(body, repo_name):
    """Rewrite issue numbers (e.g., #7784) as markdown links."""

    issue_number_pattern = re.compile(r"#(\d+)\b")
    matches = issue_number_pattern.findall(body)

    for issue_number in matches:
        issue_url = f"https://github.com/{repo_name}/issues/{issue_number}"
        markdown_link = f"[#{issue_number}]({issue_url})"
        body = re.sub(rf"#{issue_number}\b", markdown_link, body)

    return body


def rewrite_github_issue_urls(body):
    """Rewrite GitHub issue URLs in the comment body as [title](url)."""
    issue_url_pattern = re.compile(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)")
    matches = issue_url_pattern.findall(body)

    for match in matches:
        owner, repo, issue_number = match
        issue_url = f"https://github.com/{owner}/{repo}/issues/{issue_number}"

        response = get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if response.status_code == 200:
            issue_data = response.json()
            issue_title = issue_data.get("title", "Unknown Issue")
            markdown_link = f"[{issue_title}]({issue_url})"
            body = body.replace(issue_url, markdown_link)
        else:
            logger.error(
                f"Failed to fetch issue details for {issue_url}: {response.status_code}"
            )

    return body


def format_push_event(event):
    payload = event.get("payload", {})
    if not payload:
        return None

    commits = payload.get("commits", [])
    ref = payload.get("ref", "")
    if not ref:
        return None

    branch = ref.split("/")[-1]
    username = event.get("actor", {}).get("login", "unknown")
    user_url = f"https://github.com/{username}"
    repo_name = event.get("repo", {}).get("name", "unknown")

    pr_pattern = re.compile(r"\(#(\d+)\)")
    commit_messages = ""

    if commits:
        for commit in commits:
            commit_msg = commit.get("message", "No message").split("\n")[0]
            commit_sha = commit.get("id", commit.get("sha", "unknown"))[:7]
            commit_url = f"https://github.com/{repo_name}/commit/{commit_sha}"

            pr_match = pr_pattern.search(commit_msg)
            if pr_match:
                pr_number = pr_match.group(1)
                pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
                commit_msg = pr_pattern.sub(f"([#{pr_number}]({pr_url}))", commit_msg)

            commit_time = datetime.strptime(
                event.get("created_at"), "%Y-%m-%dT%H:%M:%SZ"
            )
            commit_time_str = commit_time.strftime("%Y-%m-%d %H:%M:%S")

            commit_messages += COMMIT_TEMPLATE.format(
                commit_msg=commit_msg,
                commit_sha=commit_sha,
                commit_url=commit_url,
                commit_time_str=commit_time_str,
            )

    force_push = "\n⚠️ This was a force push!\n" if payload.get("forced") else ""
    branch_created = (
        f"\n🆕 Branch `{branch}` was created\n" if payload.get("created") else ""
    )
    branch_deleted = (
        f"\n❌ Branch `{branch}` was deleted\n" if payload.get("deleted") else ""
    )

    return PUSH_TEMPLATE.format(
        commit_count=len(commits),
        username=username,
        user_url=user_url,
        commit_messages=commit_messages or "No commits found in push event.",
        force_push=force_push,
        branch_created=branch_created,
        branch_deleted=branch_deleted,
    )


def format_issue_event(event):
    payload = event.get("payload", {})
    issue = payload.get("issue", {})
    action = payload.get("action", {})

    number = issue.get("number")
    url = issue.get("html_url")

    title = issue.get("title", "No title")
    username = event.get("actor", {}).get("login", "unknown")
    user_url = f"https://github.com/{username}"

    created_at = issue.get("created_at")
    if created_at:
        created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_at_str = "Unknown"

    labels_row = ""
    labels = issue.get("labels", [])
    if labels:
        label_names = [label.get("name", "") for label in labels]
        if label_names:
            labels_row = f"| Labels | {', '.join(label_names)} |\n"

    comments_row = (
        f"| Comments | {issue.get('comments')} |\n" if issue.get("comments") else ""
    )

    closed_row = ""
    reason_row = ""
    if action == "closed":
        closed_at = issue.get("closed_at")
        if closed_at:
            closed_at = datetime.strptime(closed_at, "%Y-%m-%dT%H:%M:%SZ")
            closed_at_str = closed_at.strftime("%Y-%m-%d %H:%M:%S")
            closed_row = f"| Closed at | {closed_at_str} |\n"

        state_reason = issue.get("state_reason")
        if state_reason:
            reason_row = f"| Reason | {state_reason} |\n"

    body = ""
    if action == "opened":
        raw_body = issue.get("body", "").strip()
        if raw_body:
            body = rewrite_github_issue_urls(raw_body)
            body = f"\n{body}\n"

    return ISSUE_TEMPLATE.format(
        number=number,
        url=url,
        action=action,
        title=title,
        username=username,
        user_url=user_url,
        created_at_str=created_at_str,
        labels_row=labels_row,
        comments_row=comments_row,
        closed_row=closed_row,
        reason_row=reason_row,
        body=body,
    )


def format_pr_event(event):
    payload = event.get("payload", {})
    pr = payload.get("pull_request", {})
    action = payload.get("action", {})
    repo_name = event.get("repo", {}).get("name", "unknown")

    url = pr.get("html_url")
    number = pr.get("number")

    created_at = pr.get("created_at")
    if created_at:
        created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_at_str = "Unknown"

    updated_at = pr.get("updated_at")
    if updated_at:
        updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
        updated_at_str = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        updated_at_str = "Unknown"

    title = pr.get("title", "No title")

    username = event.get("actor", {}).get("login", "unknown")
    user_url = f"https://github.com/{username}"

    additions = pr.get("additions", 0)
    deletions = pr.get("deletions", 0)

    changed_files = pr.get("changed_files", 0)

    body = ""
    if action == "opened" and pr.get("body"):
        body = pr.get("body", "").strip()
        if body:
            body = rewrite_github_issue_urls(body)
            body = rewrite_issue_numbers(body, repo_name)
            body = body.replace("|", "\\|")
            body = f"{body} \n"

    labels_row = ""
    if pr.get("labels"):
        labels = [label.get("name", "") for label in pr["labels"]]
        if labels:
            labels_row = f"| Labels | {', '.join(labels)} |\n"

    return PR_TEMPLATE.format(
        number=number,
        url=url,
        action=action,
        title=title,
        username=username,
        user_url=user_url,
        created_at_str=created_at_str,
        updated_at_str=updated_at_str,
        labels_row=labels_row,
        body=body,
        additions=additions,
        deletions=deletions,
        changed_files=changed_files,
    )


def format_comment_event(event):
    payload = event.get("payload", {})
    comment = payload.get("comment", {})
    issue = payload.get("issue", {})
    repo_name = event.get("repo", {}).get("name", "unknown")

    url = comment.get("html_url")
    number = issue.get("number")
    title = issue.get("title")

    username = event.get("actor", {}).get("login", "unknown")
    user_url = f"https://github.com/{username}"

    if not url:
        url = issue.get("html_url", f"https://github.com/{repo_name}/issues/{number}")

    created_at = comment.get("created_at")
    if created_at:
        created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_at_str = "Unknown"

    body = comment.get("body", "").strip()
    if body:
        body = rewrite_github_issue_urls(body)
        body = f"\n{body}\n"

    return COMMENT_TEMPLATE.format(
        title=title,
        url=url,
        username=username,
        user_url=user_url,
        created_at_str=created_at_str,
        body=body,
    )
