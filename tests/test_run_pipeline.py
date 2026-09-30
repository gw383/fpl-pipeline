"""Tests for run_pipeline.py (the one-command pipeline runner)."""

import pytest

from run_pipeline import ROOT, dbt_environment


def test_sql_login_uses_the_projects_env_driven_profile():
    env = dbt_environment({"FPL_DB_USER": "fpl_admin"})
    assert env["DBT_PROFILES_DIR"] == str(ROOT / "transformation" / "profiles")


def test_windows_auth_and_explicit_profiles_dir_are_left_alone():
    assert "DBT_PROFILES_DIR" not in dbt_environment({})
    assert dbt_environment({"FPL_DB_USER": "u", "DBT_PROFILES_DIR": "/mine"})["DBT_PROFILES_DIR"] == "/mine"


def test_env_profile_renders():
    """The profile's Jinja is valid and picks up the FPL_DB_* variables."""
    jinja2 = pytest.importorskip("jinja2")  # comes with dbt
    values = {"FPL_DB_SERVER": "x.database.windows.net", "FPL_DB_USER": "u", "FPL_DB_PASSWORD": "p",
              "FPL_DB_TRUST_CERT": "no"}  # fmt: skip
    env = jinja2.Environment()
    env.filters.update(as_number=int, as_bool=lambda v: v == "True")
    env.globals["env_var"] = lambda name, default=None: values.get(name, default)
    rendered = env.from_string((ROOT / "transformation" / "profiles" / "profiles.yml").read_text()).render()
    assert 'server: "x.database.windows.net"' in rendered
    assert 'port: "1433"' in rendered and 'trust_cert: "False"' in rendered and 'database: "FPL"' in rendered
