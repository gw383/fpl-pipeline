"""Tests for dashboard/data_source.py: finding, downloading and re-checking
the dashboard's data file."""

import datetime as dt
import sqlite3

import pandas as pd
import pytest

from data_file import FORMAT_VERSION, META_TABLE, compress, write_data_file
from data_source import DataUnavailable, Downloads, configured_source, default_url, load_file

URL = "https://example.test/fpl_serving.sqlite.gz"


def _archive(tmp_path, name="source", rows=2, exported=None, environment="live") -> bytes:
    frame = pd.DataFrame({"p_id": range(rows)})
    path = write_data_file(
        {"players": frame}, tmp_path / name / "data.sqlite", exported_at=exported, environment=environment
    )
    return compress(path).read_bytes()


class FakeServer:
    """Stands in for the web server: counts requests, honours If-None-Match."""

    def __init__(self, body: bytes | None, etag: str | None = '"v1"', status: int = 200):
        self.body, self.etag, self.status = body, etag, status
        self.requests: list[dict] = []
        self.error: Exception | None = None

    def __call__(self, url, headers):
        self.requests.append(headers)
        if self.error:
            raise self.error
        if self.status != 200:
            return self.status, b"", None
        if self.etag and headers.get("If-None-Match") == self.etag:
            return 304, b"", self.etag
        return 200, self.body, self.etag


# ---------------------------------------------------------------------------
# Where the file comes from
# ---------------------------------------------------------------------------


def test_source_order(tmp_path):
    local = tmp_path / "fpl_serving.sqlite"
    explicit = {"FPL_DATA_FILE": "/data/mine.sqlite", "FPL_DATA_URL": URL}
    assert configured_source(explicit, local) == ("file", "/data/mine.sqlite")
    assert configured_source({"FPL_DATA_URL": URL}, local) == ("url", URL)
    # Nothing set and no local export: the published file (a fresh clone, the hosted app).
    assert configured_source({}, local) == ("url", default_url())
    local.write_bytes(b"")
    assert configured_source({}, local) == ("file", str(local))
    # An explicit URL still wins over a local export.
    assert configured_source({"FPL_DATA_URL": URL}, local) == ("url", URL)


def test_default_url_is_the_data_branch():
    assert default_url() == "https://raw.githubusercontent.com/gw383/fpl-pipeline/data/fpl_serving.sqlite.gz"
    assert default_url("dev") == "https://raw.githubusercontent.com/gw383/fpl-pipeline/data-dev/fpl_serving.sqlite.gz"


def test_dev_dashboard_reads_the_dev_copies(tmp_path, monkeypatch):
    import data_file

    monkeypatch.setattr(data_file, "DATA_DIR", tmp_path)
    # A live export on this machine is not what the dev dashboard shows...
    (tmp_path / "fpl_serving.sqlite").write_bytes(b"")
    assert configured_source({"FPL_ENV": "dev"}) == ("url", default_url("dev"))
    assert configured_source({}) == ("file", str(tmp_path / "fpl_serving.sqlite"))
    # ...its own export is.
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "fpl_serving.sqlite").write_bytes(b"")
    assert configured_source({"FPL_ENV": "dev"}) == ("file", str(tmp_path / "dev" / "fpl_serving.sqlite"))


# ---------------------------------------------------------------------------
# A local file
# ---------------------------------------------------------------------------


def test_local_file_reports_its_export_time_and_changes_version_when_rewritten(tmp_path):
    when = dt.datetime(2026, 10, 3, 6, 20, tzinfo=dt.UTC)
    path = write_data_file({"players": pd.DataFrame({"p_id": [1]})}, tmp_path / "data.sqlite", exported_at=when)
    first = load_file(path)
    assert (first.path, first.origin, first.exported_at, first.environment) == (path, "file", when, "live")
    assert load_file(path).version == first.version

    write_data_file({"players": pd.DataFrame({"p_id": [1, 2, 3]})}, path)
    assert load_file(path).version != first.version


def test_missing_local_file_says_how_to_create_it(tmp_path):
    with pytest.raises(DataUnavailable, match="export_data.py"):
        load_file(tmp_path / "nope.sqlite")


def test_local_file_that_is_not_a_data_file(tmp_path):
    path = tmp_path / "junk.sqlite"
    path.write_text("not a database")
    with pytest.raises(DataUnavailable, match="isn't a dashboard data file"):
        load_file(path)


def test_file_from_a_newer_dashboard_is_refused(tmp_path):
    path = write_data_file({"players": pd.DataFrame({"p_id": [1]})}, tmp_path / "data.sqlite")
    conn = sqlite3.connect(path)
    conn.execute(f"update {META_TABLE} set value = ? where key = 'format_version'", (str(FORMAT_VERSION + 1),))
    conn.commit()
    conn.close()
    with pytest.raises(DataUnavailable, match="newer format"):
        load_file(path)


# ---------------------------------------------------------------------------
# A downloaded file
# ---------------------------------------------------------------------------


def test_download_is_unpacked_and_readable(tmp_path):
    when = dt.datetime(2026, 10, 3, 6, 20, tzinfo=dt.UTC)
    server = FakeServer(_archive(tmp_path, exported=when))
    data = Downloads(tmp_path / "cache", server).load(URL)
    assert data.origin == "download" and data.exported_at == when and data.environment == "live"
    assert data.path.parent.parent == tmp_path / "cache" and data.path.is_file()
    conn = sqlite3.connect(data.path)
    assert conn.execute("select count(*) from players").fetchone() == (2,)
    conn.close()


def test_unchanged_file_is_not_downloaded_again(tmp_path):
    server = FakeServer(_archive(tmp_path))
    downloads = Downloads(tmp_path / "cache", server)
    first = downloads.load(URL)
    second = downloads.load(URL)
    assert second is first
    assert server.requests == [{}, {"If-None-Match": '"v1"'}]  # the second was answered "not modified"


def test_same_content_under_a_new_etag_keeps_the_same_version(tmp_path):
    server = FakeServer(_archive(tmp_path))
    downloads = Downloads(tmp_path / "cache", server)
    first = downloads.load(URL)
    server.etag = '"v2"'
    assert downloads.load(URL) is first


def test_new_file_replaces_the_old_one(tmp_path):
    server = FakeServer(_archive(tmp_path, "a", rows=2))
    downloads = Downloads(tmp_path / "cache", server)
    first = downloads.load(URL)

    server.body, server.etag = _archive(tmp_path, "b", rows=5), '"v2"'
    second = downloads.load(URL)
    assert second.version != first.version and second.path != first.path
    assert [p.name for p in second.path.parent.iterdir()] == [second.path.name]  # the old copy is removed


def test_live_and_dev_downloads_are_kept_apart(tmp_path):
    """Two dashboards on one machine share the cache folder; neither removes the other's file."""
    live = Downloads(tmp_path / "cache", FakeServer(_archive(tmp_path, "live"))).load(default_url())
    dev_server = FakeServer(_archive(tmp_path, "dev", rows=4, environment="dev"))
    dev = Downloads(tmp_path / "cache", dev_server).load(default_url("dev"))

    assert (live.environment, dev.environment) == ("live", "dev")
    assert live.path.is_file() and dev.path.is_file() and live.path.parent != dev.path.parent


@pytest.mark.parametrize("problem", ["network", "server", "corrupt"])
def test_a_failed_check_keeps_serving_the_last_good_file(tmp_path, problem):
    server = FakeServer(_archive(tmp_path))
    downloads = Downloads(tmp_path / "cache", server)
    first = downloads.load(URL)

    if problem == "network":
        server.error = ConnectionError("no route to host")
    elif problem == "server":
        server.status = 503
    else:
        server.body, server.etag = b"not gzip at all", '"v2"'
    assert downloads.load(URL) is first
    assert first.path.is_file()


def test_first_download_failing_explains_why(tmp_path):
    server = FakeServer(None, status=404)
    with pytest.raises(DataUnavailable, match="HTTP 404.*published"):
        Downloads(tmp_path / "cache", server).load(URL)

    server = FakeServer(None)
    server.error = ConnectionError("no route to host")
    with pytest.raises(DataUnavailable, match="no route to host"):
        Downloads(tmp_path / "cache", server).load(URL)

    with pytest.raises(DataUnavailable, match="couldn't be read"):
        Downloads(tmp_path / "cache", FakeServer(b"not gzip at all")).load(URL)
