from unittest.mock import patch
from mercourier import (
    rewrite_issue_numbers,
    rewrite_github_issue_urls,
    remove_html_comments,
)


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


def test_remove_html_comments():
    body = "Backport of #7705\n\nRight-clicking in the canvas now brings up a context menu on a selected block.\nIf multiple blocks are selected the context menu is assoziated to th 'first' block\nin the list. If no block is selected a message appears.\n\nIf the mouse is over a block this block will be selected.\n\nFixes #7610\n\nSigned-off-by: Volker Schroer <3470424+dl1ksv@users.noreply.github.com>\n\n<!--- The title of the PR should summarize the change implemented. -->\n<!--- Example commit message format: -->\n<!--- `module: summary of change` -->\n<!--- (leave blank) -->\n<!--- `details of what/why/how an issue was addressed` -->\n<!--- Keep subject lines to 50 characters (but 72 is a hard limit!) -->\n<!--- characters. Refer to the [Revision Control Guidelines](https://github.com/gnuradio/greps/blob/main/grep-0001-coding-guidelines.md#revision-control-guidelines) section of the coding guidelines -->\n\n## Description\n<!--- Provide a general summary of your changes in the title above -->\n<!--- Why is this change required? What problem does it solve? -->\n\n## Related Issue\n<!--- Refer to any related issues here -->\n<!--- If this PR fully addresses an issue, please say \"Fixes #1234\", -->\n<!--- as this will allow Github to automatically close the related Issue -->\n\n## Which blocks/areas does this affect?\n<!--- Include blocks that are affected and some details on what -->\n<!--- areas these changes affect, such as performance. -->\n\n## Testing Done\n<!--- Please describe in detail how you tested your changes. -->\n<!--- Include details of your testing environment, and th100  6563  100  6563    0     0  40381      0 --:--:-- --:--:-- --:--:-- 40763etc. Then, include justifications for how your tests -->\n<!--- demonstrate those affects. -->\n\n## Checklist\n<!--- Go over all the following points, and put an `x` in all the\n<!--- boxes that apply. Note that some of these may not be valid -->\n<!--- for all PRs. -->\n\n- [ ] I have read the [CONTRIBUTING document](https://github.com/gnuradio/gnuradio/blob/main/CONTRIBUTING.md).\n- [ ] I have squashed my commits to have one significant change per commit. \n- [ ] I [have signed my commits before making this PR](https://github.com/gnuradio/gnuradio/blob/main/CONTRIBUTING.md#dco-signed)\n- [ ] My code follows the code style of this project. See [GREP1.md](https://github.com/gnuradio/greps/blob/main/grep-0001-coding-guidelines.md).\n- [ ] I have updated [the documentation](https://wiki.gnuradio.org/index.php/Main_Page#Documentation) where necessary.\n- [ ] I have added tests to cover my changes, and all previous tests pass.\n"

    result = remove_html_comments(body)

    assert (
        "<!--- The title of the PR should summarize the change implemented. -->"
        not in result
    )
    assert "<!--- Example commit message format: -->" not in result
    assert "<!--- (leave blank) -->" not in result
    assert "<!--- `details of what/why/how an issue was addressed` -->" not in result
    assert (
        "<!--- Keep subject lines to 50 characters (but 72 is a hard limit!) -->"
        not in result
    )
