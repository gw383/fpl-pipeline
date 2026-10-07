"""Finds and loads the dashboard's data file (see ``serving/data_file.py``).

Where it comes from, first match wins:

1. ``FPL_DATA_FILE``: a data file on disk.
2. ``FPL_DATA_URL``: a gzipped data file to download.
3. ``serving/data/fpl_serving.sqlite`` if the pipeline has written one here.
4. The file the pipeline publishes to the repository's ``data`` branch,
   which is how the hosted dashboard (and a fresh clone) gets its data.

In the dev environment (``FPL_ENV=dev``, see ``extraction/environment.py``)
3 and 4 are the dev copies instead: ``serving/data/dev/`` and the
``data-dev`` branch. That is all that makes a dashboard the dev one.

A downloaded file is kept in the temp folder and only fetched again when it
has changed (the server answers "not modified" otherwise). If a later check
fails, the copy already downloaded keeps serving.

No Streamlit in here: ``database.py`` adds the app's caching on top.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import logging
import os
import sys
import tempfile
import threading
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "serving"))
from data_file import (  # noqa: E402
    ARCHIVE_NAME,
    FORMAT_VERSION,
    data_branch,
    decompress,
    default_file,
    environment_of,
    exported_at,
    read_meta,
)
from environment import LIVE, current  # noqa: E402

logger = logging.getLogger(__name__)

REPOSITORY = "gw383/fpl-pipeline"
DOWNLOAD_TIMEOUT_SECONDS = 60


def default_url(environment: str = LIVE) -> str:
    """Where the pipeline publishes an environment's data file."""
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{data_branch(environment)}/{ARCHIVE_NAME}"


# (status code, body, ETag) for a GET of ``url`` with ``headers``.
Fetch = Callable[[str, dict[str, str]], tuple[int, bytes, str | None]]


class DataUnavailable(RuntimeError):
    """There's no usable data file. The message says what to do about it."""


@dataclass(frozen=True)
class DataFile:
    path: Path
    version: str  # changes whenever the data does
    origin: str  # "file" or "download"
    exported_at: dt.datetime | None
    environment: str = LIVE  # the environment it was exported from


def configured_source(environ: dict[str, str] | None = None, local_file: Path | None = None) -> tuple[str, str]:
    """``("file", path)`` or ``("url", url)``, by the order in the module
    docstring. ``local_file`` overrides where the pipeline's own export is
    looked for."""
    env = os.environ if environ is None else environ
    if env.get("FPL_DATA_FILE"):
        return "file", env["FPL_DATA_FILE"]
    if env.get("FPL_DATA_URL"):
        return "url", env["FPL_DATA_URL"]
    environment = current(env)
    local = Path(local_file) if local_file else default_file(environment)
    if local.is_file():
        return "file", str(local)
    return "url", default_url(environment)


def _checked(path: Path, version: str, origin: str) -> DataFile:
    try:
        meta = read_meta(path)
    except ValueError as exc:
        raise DataUnavailable(str(exc)) from exc
    if int(meta.get("format_version", 0)) > FORMAT_VERSION:
        raise DataUnavailable(
            f"The data file is in a newer format (version {meta.get('format_version')}) than this dashboard "
            f"reads (version {FORMAT_VERSION}). Update the dashboard's code."
        )
    return DataFile(
        path=path, version=version, origin=origin, exported_at=exported_at(meta), environment=environment_of(meta)
    )


def load_file(path: Path) -> DataFile:
    path = Path(path)
    if not path.is_file():
        raise DataUnavailable(
            f"The data file {path} doesn't exist. Run `python serving/export_data.py` (or the whole pipeline) "
            "to create it."
        )
    stat = path.stat()
    return _checked(path, f"{stat.st_mtime_ns}-{stat.st_size}", "file")


def http_get(url: str, headers: dict[str, str]) -> tuple[int, bytes, str | None]:
    import requests

    response = requests.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    return response.status_code, response.content, response.headers.get("ETag")


class Downloads:
    """Downloaded data files, remembered between checks so an unchanged
    file isn't downloaded twice and a failed check falls back to the last
    good copy."""

    def __init__(self, cache_dir: Path | None = None, fetch: Fetch = http_get):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "fpl_dashboard_data"
        self.fetch = fetch
        self._lock = threading.Lock()
        self._url: str | None = None
        self._etag: str | None = None
        self._current: DataFile | None = None

    def load(self, url: str) -> DataFile:
        with self._lock:
            previous = self._current if self._url == url else None
            headers = {"If-None-Match": self._etag} if previous and self._etag else {}
            try:
                status, body, etag = self.fetch(url, headers)
            except Exception as exc:  # network trouble: keep serving what we have
                return self._fallback(previous, f"Couldn't download the data file from {url}: {exc}")
            if status == 304 and previous:
                return previous
            if status != 200:
                hint = " Has the pipeline published one yet?" if status == 404 else ""
                return self._fallback(previous, f"Downloading the data file from {url} returned HTTP {status}.{hint}")

            version = hashlib.sha256(body).hexdigest()[:16]
            if previous and previous.version == version:
                self._etag = etag
                return previous
            # One folder per URL, so two dashboards on one machine (live and dev) don't tidy up each other's file.
            folder = self.cache_dir / hashlib.sha256(url.encode()).hexdigest()[:10]
            target = folder / f"fpl_serving_{version}.sqlite"
            try:
                decompress(body, target)
                data = _checked(target, version, "download")
            except (OSError, EOFError, zlib.error, DataUnavailable) as exc:
                return self._fallback(previous, f"The data file downloaded from {url} couldn't be read: {exc}")

            self._url, self._etag, self._current = url, etag, data
            self._remove_old_files(keep=target)
            return data

    @staticmethod
    def _fallback(previous: DataFile | None, problem: str) -> DataFile:
        if previous is None:
            raise DataUnavailable(problem)
        logger.warning("%s Still using the copy from %s.", problem, previous.exported_at)
        return previous

    @staticmethod
    def _remove_old_files(keep: Path) -> None:
        for old in keep.parent.glob("fpl_serving_*.sqlite"):
            if old != keep:
                with contextlib.suppress(OSError):  # still open in another request; it goes next time
                    old.unlink()


_downloads = Downloads()


def download(url: str) -> DataFile:
    """The data file at ``url``: downloaded, or re-checked if it already has been."""
    return _downloads.load(url)
