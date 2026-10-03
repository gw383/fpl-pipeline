"""Publish the dashboard's data file to the repository's ``data`` branch.

    python serving/publish_data.py        # publish serving/data/fpl_serving.sqlite.gz

The hosted dashboard downloads the file from that branch (raw.githubusercontent.com),
so publishing is what makes a pipeline run visible on the site. The branch
holds one commit with one file: each publish replaces it (a forced push),
so the repository doesn't grow by a data file a day.

Where it pushes, first match wins:

* ``FPL_DATA_REMOTE``: any git remote URL.
* GitHub Actions: this repository, using the job's ``GITHUB_TOKEN`` (the
  workflow needs ``permissions: contents: write``).
* Otherwise the ``origin`` remote of this checkout, with your own git login.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_file import ARCHIVE_NAME, DATA_BRANCH, DEFAULT_FILE  # noqa: E402

logger = logging.getLogger("publish_data")

README = """# Dashboard data

`{archive}` is the data file the FPL Analytics dashboard reads: a gzipped
SQLite database of the warehouse's analytics tables, exported by the
pipeline (`serving/export_data.py` on the main branch).

This branch is generated. It is replaced on every pipeline run, so don't
commit to it.

Last published: {published} UTC
"""


def remote_url(environ: dict[str, str] | None = None, root: Path = ROOT) -> tuple[str, list[str]]:
    """The remote to push to, and any secrets in it to keep out of the logs."""
    env = os.environ if environ is None else environ
    if env.get("FPL_DATA_REMOTE"):
        return env["FPL_DATA_REMOTE"], []
    token, repository = env.get("GITHUB_TOKEN"), env.get("GITHUB_REPOSITORY")
    if token and repository:
        server = env.get("GITHUB_SERVER_URL", "https://github.com").removeprefix("https://")
        return f"https://x-access-token:{token}@{server}/{repository}.git", [token]
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise SystemExit(
            "Can't tell where to publish the data file: this isn't a git checkout with an 'origin' remote. "
            "Set FPL_DATA_REMOTE to a git remote URL."
        )
    return result.stdout.strip(), []


def _redact(message: str, secrets: list[str]) -> str:
    for secret in secrets:
        message = message.replace(secret, "***")
    return message


def _git(args: list[str], cwd: Path, secrets: list[str]) -> None:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        command = _redact(" ".join(["git", *args]), secrets)
        detail = _redact((result.stderr or result.stdout).strip(), secrets)
        raise SystemExit(f"Publishing the data file failed at `{command}`:\n{detail}")


def publish(archive: Path | None = None, remote: str | None = None, branch: str = DATA_BRANCH) -> None:
    """Replace ``branch`` on the remote with a single commit holding ``archive``."""
    archive = Path(archive) if archive else DEFAULT_FILE.with_name(ARCHIVE_NAME)
    if not archive.is_file():
        raise SystemExit(f"{archive} doesn't exist. Run `python serving/export_data.py` first.")
    secrets: list[str] = []
    if remote is None:
        remote, secrets = remote_url()

    published = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M")
    # ignore_cleanup_errors: git leaves read-only files that Windows can't always delete.
    with tempfile.TemporaryDirectory(prefix="fpl-data-", ignore_cleanup_errors=True) as workdir:
        work = Path(workdir)
        shutil.copy2(archive, work / ARCHIVE_NAME)
        (work / "README.md").write_text(README.format(archive=ARCHIVE_NAME, published=published), encoding="utf-8")
        identity = ["-c", "user.name=FPL pipeline", "-c", "user.email=fpl-pipeline@users.noreply.github.com"]
        _git(["init", "--quiet"], work, secrets)
        _git(["symbolic-ref", "HEAD", f"refs/heads/{branch}"], work, secrets)
        _git(["add", "--all", "--force"], work, secrets)  # --force: ignore any global gitignore
        _git([*identity, "commit", "--quiet", "-m", f"Dashboard data, {published} UTC"], work, secrets)
        _git(["push", "--force", "--quiet", remote, f"HEAD:refs/heads/{branch}"], work, secrets)
    logger.info("Published %s (%.1f MB) to the '%s' branch", archive.name, archive.stat().st_size / 1e6, branch)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    publish()


if __name__ == "__main__":
    main()
