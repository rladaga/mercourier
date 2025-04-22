from mercourier import GitHub


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


def test_check_repository_events():
    pass
