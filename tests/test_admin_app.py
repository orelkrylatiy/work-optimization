"""Tests for admin panel auth/profile endpoints."""

from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

import admin.app as admin_app
from hh_applicant_tool.main import HHApplicantTool


def test_create_profile_initializes_storage(tmp_path, monkeypatch):
    """Profile creation should prepare config and SQLite storage."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)

    response = client.post("/api/profiles", json={"profile": "account-2"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["profile"] == "account-2"

    profile_dir = tmp_path / "account-2"
    assert (profile_dir / "config.json").exists()
    assert (profile_dir / "data").exists()

    conn = sqlite3.connect(profile_dir / "data")
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "settings" in tables
    assert "vacancies" in tables


def test_legacy_root_config_does_not_swallow_named_profiles(tmp_path, monkeypatch):
    """Named profiles should stay isolated even when CONFIG_DIR is a legacy profile."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "..bad").mkdir()
    client = TestClient(admin_app.app)

    response = client.post("/api/profiles", json={"profile": "account-2"})

    assert response.status_code == 200
    assert response.json()["config_path"] == str(tmp_path / "account-2" / "config.json")
    assert (tmp_path / "account-2" / "config.json").exists()
    profiles = client.get("/api/profiles").json()["profiles"]
    assert profiles == ["default", "account-2"]


def test_cli_named_profile_uses_subdir_with_legacy_root_config(tmp_path):
    """CLI profile resolution must match the admin panel layout."""
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    tool = HHApplicantTool()
    tool.config_dir = tmp_path
    tool.profile_id = "account-2"

    assert tool.config_path == (tmp_path / "account-2").resolve()


def test_cli_profile_rejects_path_traversal(tmp_path):
    """CLI profile IDs should be account names, not filesystem paths."""
    tool = HHApplicantTool()
    tool.config_dir = tmp_path
    tool.profile_id = ".."

    try:
        _ = tool.config_path
    except ValueError as ex:
        assert "Invalid profile name" in str(ex)
    else:
        raise AssertionError("Expected invalid profile name")


def test_reauthorize_uses_manual_visible_flags(tmp_path, monkeypatch):
    """Reauthorize endpoint should create storage and run visible manual auth."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    captured = {}

    def fake_run_operation(op, body, extra=None):
        captured["op"] = op
        captured["profile"] = body.profile
        captured["extra"] = list(extra or [])
        return {"op_id": "auth-op", "stdout": "", "stderr": ""}

    monkeypatch.setattr(admin_app, "_run_operation", fake_run_operation)
    client = TestClient(admin_app.app)

    response = client.post(
        "/api/auth/reauthorize?profile=fresh-user&manual=true&visible=true"
    )

    assert response.status_code == 200
    assert response.json()["op_id"] == "auth-op"
    assert captured == {
        "op": "authorize",
        "profile": "fresh-user",
        "extra": ["--manual", "--no-headless"],
    }
    assert (tmp_path / "fresh-user" / "config.json").exists()
    assert (tmp_path / "fresh-user" / "data").exists()


def test_config_validation_does_not_add_empty_defaults(tmp_path, monkeypatch):
    """Reading or writing config should not add empty optional fields."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "session-a"})
    config_path = tmp_path / "session-a" / "config.json"
    config_path.write_text(
        json.dumps({"token": {"access_token": "USER-token"}}),
        encoding="utf-8",
    )

    response = client.put(
        "/api/config?profile=session-a",
        json={"data": {"api_delay": 1.5}},
    )

    assert response.status_code == 200
    saved_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved_config == {
        "api_delay": 1.5,
        "token": {"access_token": "USER-token"},
    }


def test_run_operation_disables_auto_auth_for_admin_jobs(monkeypatch):
    """Background admin jobs should fail fast instead of waiting for CLI input."""
    captured = {}

    class FakeProcess:
        pid = 123
        returncode = 0

        def communicate(self, timeout=None):
            return "", ""

        def poll(self):
            return self.returncode

    class SyncThread:
        def __init__(self, target, daemon=None):
            self.target = target

        def start(self):
            self.target()

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(admin_app.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(admin_app.threading, "Thread", SyncThread)
    admin_app.running_operations.clear()

    response = admin_app._run_operation(
        "apply-vacancies",
        admin_app.RunRequest(profile="account-2"),
    )

    assert response["op_id"]
    assert "--no-auto-auth" in captured["cmd"]
    assert captured["cmd"].index("--no-auto-auth") < captured["cmd"].index("apply-vacancies")


def test_logout_clears_token_and_cookies(tmp_path, monkeypatch):
    """Logout should wipe local token payload and browser cookies."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "session-a"})

    profile_dir = tmp_path / "session-a"
    config_path = profile_dir / "config.json"
    cookies_path = profile_dir / "cookies.txt"

    config_path.write_text(
        json.dumps(
            {
                "token": {
                    "access_token": "USER-token",
                    "refresh_token": "refresh-token",
                    "access_expires_at": 1234567890,
                }
            }
        ),
        encoding="utf-8",
    )
    cookies_path.write_text("cookie-data", encoding="utf-8")

    response = client.post("/api/auth/logout?profile=session-a")

    assert response.status_code == 200
    assert response.json()["cookies_deleted"] is True
    saved_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved_config["token"] == {}
    assert not cookies_path.exists()
