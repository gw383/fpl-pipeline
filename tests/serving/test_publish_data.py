"""Tests for serving/publish_data.py, pushing to a local bare repository."""

import shutil
import subprocess

import pandas as pd
import pytest

from data_file import ARCHIVE_NAME, FILE_NAME, archive_meta, compress, write_data_file
from publish_data import _redact, publish, remote_url

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git isn't installed")


def _git(remote, *args):
    return subprocess.run(
        ["git", "--git-dir", str(remote), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _archive(folder, environment="live", rows=1):
    """A real (if tiny) data file exported from ``environment``, gzipped."""
    frames = {"players": pd.DataFrame({"p_id": range(rows)})}
    return compress(write_data_file(frames, folder / FILE_NAME, environment=environment))


def _published(remote, tmp_path, branch):
    """The metadata of the archive on ``branch`` of the remote."""
    copy = tmp_path / "published" / branch / ARCHIVE_NAME
    copy.parent.mkdir(parents=True, exist_ok=True)
    with copy.open("wb") as out:
        subprocess.run(["git", "--git-dir", str(remote), "show", f"{branch}:{ARCHIVE_NAME}"], stdout=out, check=True)
    return archive_meta(copy)


@pytest.fixture
def remote(tmp_path):
    path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(path)], check=True)
    return path


@needs_git
def test_publish_puts_the_archive_on_the_data_branch(tmp_path, remote):
    archive = _archive(tmp_path)
    publish(archive, remote=str(remote), environment="live")

    assert _git(remote, "ls-tree", "--name-only", "data").splitlines() == ["README.md", ARCHIVE_NAME]
    assert _published(remote, tmp_path, "data") == archive_meta(archive)


@needs_git
def test_each_publish_replaces_the_branch_with_one_commit(tmp_path, remote):
    for rows in (1, 2):
        publish(_archive(tmp_path, rows=rows), remote=str(remote), environment="live")

    assert _git(remote, "rev-list", "--count", "data") == "1"  # no history of old files
    assert _published(remote, tmp_path, "data")["row_counts"] == '{"players": 2}'


@needs_git
def test_dev_publishes_to_its_own_branch_and_leaves_live_alone(tmp_path, remote):
    publish(_archive(tmp_path / "live"), remote=str(remote), environment="live")
    live_commit = _git(remote, "rev-parse", "data")

    publish(_archive(tmp_path / "dev", "dev", rows=3), remote=str(remote), environment="dev")

    assert _published(remote, tmp_path, "data-dev")["environment"] == "dev"
    assert _git(remote, "rev-parse", "data") == live_commit
    assert "dev" in _git(remote, "show", "data-dev:README.md")


@needs_git
@pytest.mark.parametrize(("exported", "publishing"), [("dev", "live"), ("live", "dev")])
def test_a_file_is_never_published_to_the_other_environment(tmp_path, remote, exported, publishing):
    with pytest.raises(SystemExit, match=f"exported from the {exported} environment"):
        publish(_archive(tmp_path, exported), remote=str(remote), environment=publishing)
    assert _git(remote, "branch", "--list") == ""  # nothing was pushed


def test_something_that_is_not_a_data_file_is_not_published(tmp_path):
    archive = tmp_path / ARCHIVE_NAME
    archive.write_bytes(b"not a data file")
    with pytest.raises(SystemExit, match="isn't a readable data file"):
        publish(archive, remote="unused", environment="live")


def test_environment_defaults_to_fpl_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FPL_ENV", "dev")
    with pytest.raises(SystemExit, match="exported from the live environment, but this is the dev environment"):
        publish(_archive(tmp_path), remote="unused")


@needs_git
def test_a_failed_push_reports_the_step_without_the_token(tmp_path):
    with pytest.raises(SystemExit) as failure:
        publish(_archive(tmp_path), remote=str(tmp_path / "no-such-remote.git"), environment="live")
    assert "Publishing the data file failed" in str(failure.value)


def test_publishing_a_missing_archive_says_what_to_run(tmp_path):
    with pytest.raises(SystemExit, match="export_data.py"):
        publish(tmp_path / ARCHIVE_NAME, remote="unused", environment="live")


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
