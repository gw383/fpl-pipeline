"""Tests for extraction/db.py's connection settings (no database needed)."""

from urllib.parse import unquote_plus

import pytest

from db import DbSettings, build_connection_string, build_url

AZURE = DbSettings(
    server="fplwarehouse.database.windows.net", database="fpl", user="fpl_web", password="p@ss;word!", trust_cert=False
)


def test_local_windows_auth_is_unchanged():
    conn = build_connection_string(DbSettings())
    assert "SERVER=localhost;" in conn and "Trusted_Connection=yes;" in conn
    assert "TrustServerCertificate=yes" in conn


def test_azure_odbc_uses_tcp_port_and_checks_the_certificate():
    conn = build_connection_string(AZURE)
    assert "SERVER=tcp:fplwarehouse.database.windows.net,1433;" in conn
    assert "UID=fpl_web;" in conn and "TrustServerCertificate=no" in conn
    assert build_url(AZURE).startswith("mssql+pyodbc:///?odbc_connect=")


def test_pymssql_url_for_azure():
    url = build_url(DbSettings(**{**AZURE.__dict__, "driver": "pymssql"}))
    assert url.startswith("mssql+pymssql://")
    credentials, rest = url[len("mssql+pymssql://") :].split("@", 1)
    user, password = credentials.split(":", 1)
    assert unquote_plus(user) == "fpl_web@fplwarehouse"  # FreeTDS-friendly Azure login
    assert unquote_plus(password) == "p@ss;word!"
    assert rest.startswith("fplwarehouse.database.windows.net:1433/fpl")


def test_pymssql_needs_a_login_and_unknown_drivers_fail():
    with pytest.raises(ValueError):
        build_url(DbSettings(driver="pymssql"))
    with pytest.raises(ValueError):
        build_url(DbSettings(driver="jdbc"))


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("FPL_DB_SERVER", "x.database.windows.net")
    monkeypatch.setenv("FPL_DB_USER", "u")
    monkeypatch.setenv("FPL_DB_DRIVER", "PyMSSQL")
    monkeypatch.setenv("FPL_DB_TRUST_CERT", "no")
    monkeypatch.delenv("FPL_DB_PORT", raising=False)
    s = DbSettings.from_env()
    assert s.is_azure and s.driver == "pymssql" and not s.trust_cert and s.port == 1433
