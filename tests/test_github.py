import json
import pytest
from mercourier import GitHub, RateLimitExcedeed
from unittest.mock import patch, Mock
from pathlib import Path


def make_response(
    etag="W/some-etag", remaining="10", reset="9999999999", content=b"[]", status=200
):
    response = Mock()
    response.status_code = status
    response.headers = {
        "ETag": etag,
        "X-RateLimit-Remaining": remaining,
        "X-RateLimit-Reset": reset,
    }
    response.content = content
    return response


def test_github_empty_state(tmp_path):
    file = tmp_path / "state.json"
    repo_name = "author/repo1"
    github = GitHub(repositories=[repo_name], last_check_file=file)

    assert repo_name in github.last_check_etag
    assert github.last_check_etag[repo_name] == ""
    assert github.processed_events[repo_name] is None


def test_save_and_load(tmp_path):
    file = tmp_path / "state.json"
    repo_name = "author/repo1"
    github = GitHub(repositories=[repo_name], last_check_file=file)
    github.last_check_etag[repo_name] = (
        'W/"4a163ea87adf69d0910f2d5e65bfa38764eba6cf1a1575662b98ea0e5d00b863"'
    )
    github.processed_events[repo_name] = "48463696315"
    github.save_last_check()

    new_github = GitHub(repositories=[repo_name], last_check_file=file)

    assert (
        new_github.last_check_etag[repo_name]
        == 'W/"4a163ea87adf69d0910f2d5e65bfa38764eba6cf1a1575662b98ea0e5d00b863"'
    )
    assert new_github.processed_events[repo_name] == "48463696315"


@patch("mercourier.github.get")
def test_check_repository_events(mock_get):
    with open("tests/test_events.json", "r") as file:
        events = json.load(file)

    repo_name = "rladaga/mercourier"
    etag = 'W/"9f861365bc7b3adb22e03ecec119361d563efa2283ba8da9a285c4dfdd7af91b"'
    processed = []

    def mock_on_event(event):
        processed.append(event)

    bot = GitHub(
        repositories=[repo_name],
        on_event=mock_on_event,
        last_check_file=Path("test_last_check.json"),
    )

    mock_response = Mock()
    mock_response.content = json.dumps(events).encode("utf-8")
    mock_get.return_value = make_response(etag=etag, content=mock_response.content)

    bot.check_repository_events(repo_name)

    assert len(processed) == 23
    assert processed[0]["type"] == "PullRequestEvent"
    assert processed[1]["type"] == "PushEvent"
    assert processed[2]["type"] == "IssuesEvent"

    assert bot.last_check_etag[repo_name] == etag

    bot.processed_events[repo_name] = "130"
    processed.clear()

    bot.check_repository_events(repo_name)
    assert len(processed) == 0


@patch("mercourier.github.get")
def test_rate_limit_exception(mock_get):
    mock_get.return_value = make_response(remaining="0")

    bot = GitHub(
        repositories=["user/repo"],
        on_event=lambda e: None,
        last_check_file=Path("test_last_check.json"),
    )

    with pytest.raises(RateLimitExcedeed):
        bot.check_repository_events("user/repo")


@patch("mercourier.github.get")
def test_rate_limit_resume(mock_get):
    def side_effect(url, headers):
        if "repo1" in url:
            return make_response()
        elif "repo2" in url:
            return make_response(remaining="0")
        else:
            return make_response()

    mock_get.side_effect = side_effect

    bot = GitHub(
        repositories=["user/repo1", "user/repo2", "user/repo3"],
        on_event=lambda e: None,
        last_check_file=Path("test_last_check.json"),
    )

    with pytest.raises(RateLimitExcedeed):
        for i in range(bot.current_repo_index, len(bot.repositories)):
            bot.check_repository_events(bot.repositories[i])
            bot.current_repo_index = (i + 1) % len(bot.repositories)

    assert bot.current_repo_index == 1

    mock_get.reset_mock()
    mock_get.side_effect = None
    mock_get.return_value = make_response()

    for i in range(bot.current_repo_index, len(bot.repositories)):
        bot.check_repository_events(bot.repositories[i])
        bot.current_repo_index = (i + 1) % len(bot.repositories)

    assert mock_get.call_count == 2
    assert "repo2" in mock_get.call_args_list[0][0][0]
    assert "repo3" in mock_get.call_args_list[1][0][0]
    assert bot.current_repo_index == 0
