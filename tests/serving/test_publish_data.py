"""Tests for serving/publish_data.py, pushing to a local bare repository."""

import shutil
import subprocess

import pytest

from data_file import ARCHIVE_NAME
from publish_data import _redact, publish, remote_url

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git isn't installed")


def _git(remote, *args):
    return subprocess.run(
        ["git", "--git-dir", str(remote), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(path)], check=True)
    return path


@needs_git
def test_publish_puts_the_archive_on_the_data_branch(tmp_path, remote):
    archive = tmp_path / ARCHIVE_NAME
    archive.write_bytes(b"first")
    publish(archive, remote=str(remote))

    assert _git(remote, "ls-tree", "--name-only", "data").splitlines() == ["README.md", ARCHIVE_NAME]
    assert _git(remote, "show", f"data:{ARCHIVE_NAME}") == "first"


@needs_git
def test_each_publish_replaces_the_branch_with_one_commit(tmp_path, remote):
    archive = tmp_path / ARCHIVE_NAME
    for content in (b"first", b"second"):
        archive.write_bytes(content)
        publish(archive, remote=str(remote))

    assert _git(remote, "rev-list", "--count", "data") == "1"  # no history of old files
    assert _git(remote, "show", f"data:{ARCHIVE_NAME}") == "second"


@needs_git
def test_a_failed_push_reports_the_step_without_the_token(tmp_path):
    archive = tmp_path / ARCHIVE_NAME
    archive.write_bytes(b"data")
    with pytest.raises(SystemExit) as failure:
        publish(archive, remote=str(tmp_path / "no-such-remote.git"))
    assert "Publishing the data file failed" in str(failure.value)


def test_publishing_a_missing_archive_says_what_to_run(tmp_path):
    with pytest.raises(SystemExit, match="export_data.py"):
        publish(tmp_path / ARCHIVE_NAME, remote="unused")


def test_remote_prefers_an_explicit_setting():
    assert remote_url({"FPL_DATA_REMOTE": "/srv/data.git", "GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"}) == (
        "/srv/data.git",
        [],
    )


def test_remote_in_github_actions_uses_the_job_token_and_hides_it():
    url, secrets = remote_url({"GITHUB_TOKEN": "s3cret", "GITHUB_REPOSITORY": "gw383/fpl-pipeline"})
    assert url == "https://x-access-token:s3cret@github.com/gw383/fpl-pipeline.git"
    assert secrets == ["s3cret"]
    assert "s3cret" not in _redact(f"git push {url} failed", secrets)


@needs_git
def test_remote_falls_back_to_the_checkouts_origin(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/me/repo.git"], check=True
    )
    assert remote_url({}, root=tmp_path) == ("https://github.com/me/repo.git", [])


@needs_git
def test_remote_outside_a_checkout_asks_for_a_setting(tmp_path):
    with pytest.raises(SystemExit, match="FPL_DATA_REMOTE"):
        remote_url({}, root=tmp_path)
