"""Tests for run_pipeline.py (the one-command pipeline runner)."""

import shutil
import subprocess

import pytest

from run_pipeline import (
    ROOT,
    check_dbt_follows,
    current_branch,
    dbt_environment,
    export_command,
    resolve_environment,
)


def test_sql_login_uses_the_projects_env_driven_profile():
    env = dbt_environment({"FPL_DB_USER": "fpl_admin"})
    assert env["DBT_PROFILES_DIR"] == str(ROOT / "transformation" / "profiles")


def test_windows_auth_and_explicit_profiles_dir_are_left_alone():
    assert "DBT_PROFILES_DIR" not in dbt_environment({})
    assert dbt_environment({"FPL_DB_USER": "u", "DBT_PROFILES_DIR": "/mine"})["DBT_PROFILES_DIR"] == "/mine"


def test_data_file_step_publishes_only_when_asked():
    assert export_command("python", publish=False) == ["python", "serving/export_data.py"]
    assert export_command("python", publish=True) == ["python", "serving/export_data.py", "--publish"]
    assert (ROOT / "serving" / "export_data.py").is_file()


# ---------------------------------------------------------------------------
# Live or dev
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("branch", ["main", "master", None])
def test_on_main_the_pipeline_updates_live_by_default(branch):
    assert resolve_environment(None, {}, branch) == "live"


def test_on_another_branch_you_have_to_say_which_environment():
    with pytest.raises(SystemExit, match="--env dev"):
        resolve_environment(None, {}, "dev")
    with pytest.raises(SystemExit, match="'mobile-layout' branch"):
        resolve_environment(None, {"FPL_ENV": ""}, "mobile-layout")


def test_the_flag_wins_then_fpl_env():
    assert resolve_environment("dev", {"FPL_ENV": "live"}, "main") == "dev"
    assert resolve_environment("live", {}, "dev") == "live"  # deliberate, so allowed
    assert resolve_environment(None, {"FPL_ENV": "dev"}, "dev") == "dev"
    assert resolve_environment(None, {"FPL_ENV": "DEV"}, "main") == "dev"
    with pytest.raises(ValueError):
        resolve_environment(None, {"FPL_ENV": "prod"}, "main")


def test_current_branch_of_a_checkout(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git isn't installed")
    assert current_branch(tmp_path) is None  # not a checkout
    subprocess.run(["git", "init", "--quiet", "--initial-branch", "dev", str(tmp_path)], check=True)
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.test"]
    subprocess.run(["git", "-C", str(tmp_path), *identity, "commit", "--quiet", "--allow-empty", "-m", "x"], check=True)
    assert current_branch(tmp_path) == "dev"
    subprocess.run(["git", "-C", str(tmp_path), "checkout", "--quiet", "--detach"], check=True)
    assert current_branch(tmp_path) is None  # detached: no branch to go by


def test_dev_needs_dbt_to_use_the_projects_profile():
    """With Windows authentication dbt would build into the user's own (live) database."""
    with pytest.raises(SystemExit, match="SQL login"):
        check_dbt_follows("dev", {})
    check_dbt_follows("dev", {"FPL_DB_USER": "fpladmin"})
    check_dbt_follows("dev", {"DBT_PROFILES_DIR": "/mine"})
    check_dbt_follows("live", {})


def _render_profile(values):
    jinja2 = pytest.importorskip("jinja2")  # comes with dbt
    env = jinja2.Environment()
    env.filters.update(as_number=int, as_bool=lambda v: v == "True")
    env.globals["env_var"] = lambda name, default=None: values.get(name, default)
    return env.from_string((ROOT / "transformation" / "profiles" / "profiles.yml").read_text()).render()


def test_env_profile_renders():
    """The profile's Jinja is valid and picks up the FPL_DB_* variables."""
    rendered = _render_profile(
        {
            "FPL_DB_SERVER": "x.database.windows.net",
            "FPL_DB_USER": "u",
            "FPL_DB_PASSWORD": "p",
            "FPL_DB_TRUST_CERT": "no",
        }  # fmt: skip
    )
    assert 'server: "x.database.windows.net"' in rendered
    assert 'port: "1433"' in rendered and 'trust_cert: "False"' in rendered and 'database: "FPL"' in rendered


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"FPL_DB_NAME": "fpl"},
        {"FPL_ENV": "live", "FPL_DB_NAME": "fpl", "FPL_DB_NAME_DEV": "scratch"},
        {"FPL_ENV": "dev"},
        {"FPL_ENV": " Dev ", "FPL_DB_NAME": "fpl"},
        {"FPL_ENV": "dev", "FPL_DB_NAME": "fpl", "FPL_DB_NAME_DEV": "scratch"},
    ],
)
def test_dbt_builds_into_the_same_database_as_the_rest_of_the_pipeline(values):
    """The profile's rule for the database is the one in extraction/environment.py."""
    from environment import database_name

    connection = {"FPL_DB_SERVER": "s", "FPL_DB_USER": "u", "FPL_DB_PASSWORD": "p"}
    assert f'database: "{database_name(values)}"' in _render_profile({**connection, **values})
