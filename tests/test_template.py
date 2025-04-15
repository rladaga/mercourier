import pytest
from unittest.mock import patch
from mercourier import rewrite_issue_numbers, rewrite_github_issue_urls


def test_rewrite_issue_numbers():
    body = "Fixed issue #56 and improved #97"
    expected = "Fixed issue [#56](https://github.com/test/repo/issues/56) and improved [#97](https://github.com/test/repo/issues/97)"
    result = rewrite_issue_numbers(body, "test/repo")
    assert result == expected


@patch("mercourier.template.get")
def test_rewrite_github_issue_url(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"title": "Testing rewrite issue"}

    body = (
        "Testing https://github.com/test/repo/issues/97 with pytest and unittest.mock"
    )
    result = rewrite_github_issue_urls(body)
    assert "[Testing rewrite issue](https://github.com/test/repo/issues/97)" in result
