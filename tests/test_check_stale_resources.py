from datetime import datetime, timezone
from unittest.mock import patch

from scripts.check_stale_resources import github_repo, get_pushed_at


def test_github_repo_extracts_owner_and_repo():
    assert github_repo("https://github.com/owner/project") == "owner/project"


def test_github_repo_ignores_non_github_urls():
    assert github_repo("https://example.com/project") is None


def test_github_repo_handles_git_suffix():
    assert github_repo("https://github.com/owner/project.git") == "owner/project"


def test_get_pushed_at_parses_timestamp():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"pushed_at": "2026-01-01T00:00:00Z"}'

    with patch("scripts.check_stale_resources.urlopen", return_value=FakeResponse()):
        result = get_pushed_at("owner/project")

    assert result == datetime(2026, 1, 1, tzinfo=timezone.utc)