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


def test_run_operation_uses_devnull_stdin(monkeypatch):
    """Subprocess must never inherit stdin — use DEVNULL to prevent hangs."""
    captured = {}

    class FakeProcess:
        pid = 42
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
        captured["stdin"] = kwargs.get("stdin")
        return FakeProcess()

    monkeypatch.setattr(admin_app.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(admin_app.threading, "Thread", SyncThread)
    admin_app.running_operations.clear()

    admin_app._run_operation(
        "update-resumes",
        admin_app.RunRequest(profile="default"),
    )

    assert captured["stdin"] is admin_app.subprocess.DEVNULL, (
        "stdin must be DEVNULL so the process never blocks waiting for user input"
    )


def test_token_status_no_config(tmp_path, monkeypatch):
    """/api/token-status returns no_config when profile directory is absent."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)

    response = client.get("/api/token-status?profile=ghost")

    assert response.status_code == 200
    assert response.json()["status"] == "no_config"


def test_token_status_ok(tmp_path, monkeypatch):
    """/api/token-status returns ok when a valid unexpired token is present."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tok-ok"})
    cfg = tmp_path / "tok-ok" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "good-token",
                "refresh_token": "ref",
                "access_expires_at": time.time() + 3600,
            }
        }),
        encoding="utf-8",
    )

    response = client.get("/api/token-status?profile=tok-ok")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["can_refresh"] is True
    assert data["expires_in_seconds"] > 0


def test_token_status_expired(tmp_path, monkeypatch):
    """/api/token-status returns expired when access_expires_at is in the past."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tok-exp"})
    cfg = tmp_path / "tok-exp" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "stale-token",
                "refresh_token": "ref",
                "access_expires_at": 1000000,   # far in the past
            }
        }),
        encoding="utf-8",
    )

    response = client.get("/api/token-status?profile=tok-exp")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "expired"
    assert data["can_refresh"] is True


def test_agent_preflight_no_token(tmp_path, monkeypatch):
    """/api/agent/preflight reports needs_reauth when no token is present."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "new-agent"})

    response = client.get("/api/agent/preflight?profile=new-agent")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["needs_reauth"] is True
    assert data["action"] == "reauth"


def test_agent_preflight_ready(tmp_path, monkeypatch):
    """/api/agent/preflight returns ready=True when token is valid."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-ok"})
    cfg = tmp_path / "agent-ok" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "live-token",
                "refresh_token": "ref",
                "access_expires_at": time.time() + 7200,
            }
        }),
        encoding="utf-8",
    )

    response = client.get("/api/agent/preflight?profile=agent-ok")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["action"] == "run"
    assert data["needs_reauth"] is False
    assert data["needs_refresh"] is False


def test_agent_run_no_token_returns_401(tmp_path, monkeypatch):
    """/api/agent/run should return 401 when there is no token at all."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-noauth"})

    response = client.post(
        "/api/agent/run",
        json={"profile": "agent-noauth", "operation": "apply-vacancies"},
    )

    assert response.status_code == 401
    assert "авторизаци" in response.json()["detail"].lower()


def test_agent_run_expired_triggers_refresh(tmp_path, monkeypatch):
    """/api/agent/run should auto-refresh expired token before running operation."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-ref"})
    cfg = tmp_path / "agent-ref" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "old",
                "refresh_token": "ref",
                "access_expires_at": 1000,          # expired
            }
        }),
        encoding="utf-8",
    )

    refresh_calls = []
    run_calls = []

    def fake_refresh(profile, timeout=30):
        refresh_calls.append(profile)
        # Simulate successful refresh by updating the token in config
        cfg.write_text(
            json.dumps({
                "token": {
                    "access_token": "new",
                    "refresh_token": "ref",
                    "access_expires_at": time.time() + 7200,
                }
            }),
            encoding="utf-8",
        )
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

    def fake_run_op(op, body, extra=None):
        run_calls.append(op)
        return {"op_id": "x1", "stdout": "started", "stderr": ""}

    monkeypatch.setattr(admin_app, "_refresh_token_sync", fake_refresh)
    monkeypatch.setattr(admin_app, "_run_operation", fake_run_op)

    response = client.post(
        "/api/agent/run",
        json={"profile": "agent-ref", "operation": "update-resumes", "auto_refresh": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["refreshed_token"] is True
    assert data["op_id"] == "x1"
    assert refresh_calls == ["agent-ref"]
    assert run_calls == ["update-resumes"]


def test_agent_run_invalid_operation(tmp_path, monkeypatch):
    """/api/agent/run rejects unknown operation names."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-bad"})
    cfg = tmp_path / "agent-bad" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "tok",
                "access_expires_at": time.time() + 3600,
            }
        }),
        encoding="utf-8",
    )

    response = client.post(
        "/api/agent/run",
        json={"profile": "agent-bad", "operation": "rm -rf /"},
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Letter templates
# ---------------------------------------------------------------------------

def test_seed_letter_templates(tmp_path, monkeypatch):
    """/api/letter-templates/seed populates default templates in config."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-seed"})

    resp = client.post("/api/letter-templates/seed?profile=tpl-seed")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert len(data["added"]) == len(admin_app.DEFAULT_LETTER_TEMPLATES)

    cfg = json.loads((tmp_path / "tpl-seed" / "config.json").read_text(encoding="utf-8"))
    assert "letter_templates" in cfg
    assert "universal" in cfg["letter_templates"]


def test_seed_does_not_overwrite_existing(tmp_path, monkeypatch):
    """Seeding without overwrite=true should preserve user-edited templates."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-preserve"})

    # Pre-seed with custom version of 'universal'
    client.post(
        "/api/letter-templates",
        json={"profile": "tpl-preserve", "name": "universal", "content": "My custom text"},
    )

    # Re-seed without overwrite
    client.post("/api/letter-templates/seed?profile=tpl-preserve&overwrite=false")

    cfg = json.loads((tmp_path / "tpl-preserve" / "config.json").read_text(encoding="utf-8"))
    assert cfg["letter_templates"]["universal"] == "My custom text"


def test_upsert_and_delete_letter_template(tmp_path, monkeypatch):
    """Letter templates can be created, updated, and deleted via API."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-crud"})

    # Create
    resp = client.post(
        "/api/letter-templates",
        json={"profile": "tpl-crud", "name": "my-tpl", "content": "Hello %(first_name)s"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # List
    resp = client.get("/api/letter-templates?profile=tpl-crud")
    assert resp.status_code == 200
    assert "my-tpl" in resp.json()["templates"]

    # Delete
    resp = client.delete("/api/letter-templates/my-tpl?profile=tpl-crud")
    assert resp.status_code == 200

    cfg = json.loads((tmp_path / "tpl-crud" / "config.json").read_text(encoding="utf-8"))
    assert "my-tpl" not in (cfg.get("letter_templates") or {})


def test_resolve_letter_file_uses_template(tmp_path, monkeypatch):
    """_resolve_letter_file writes template to tmp file and returns path."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-resolve"})
    client.post(
        "/api/letter-templates",
        json={"profile": "tpl-resolve", "name": "hello", "content": "Hi %(first_name)s!"},
    )

    path = admin_app._resolve_letter_file("tpl-resolve", "hello")

    assert path is not None
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "Hi %(first_name)s!"


def test_resolve_letter_file_falls_back_to_default(tmp_path, monkeypatch):
    """_resolve_letter_file falls back to DEFAULT_LETTER_TEMPLATES if not in config."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-fallback"})

    # 'universal' is in DEFAULT_LETTER_TEMPLATES but NOT in user config
    path = admin_app._resolve_letter_file("tpl-fallback", "universal")

    assert path is not None
    assert path.exists()


def test_apply_full_passes_letter_file_arg(tmp_path, monkeypatch):
    """ApplyFullRequest with template_name resolves and passes --letter-file."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-apply"})
    client.post(
        "/api/letter-templates",
        json={"profile": "tpl-apply", "name": "short", "content": "Short letter"},
    )

    body = admin_app.ApplyFullRequest(
        profile="tpl-apply",
        template_name="short",
        force_message=True,
    )
    args = admin_app._build_apply_args(body)

    assert "--letter-file" in args
    letter_path_idx = args.index("--letter-file") + 1
    assert args[letter_path_idx].endswith("_letter_tmp.txt")


def test_apply_full_uses_improved_system_prompt(tmp_path, monkeypatch):
    """ApplyFullRequest with use_ai=True injects DEFAULT_SYSTEM_PROMPT if none given."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "tpl-ai-prompt"})

    body = admin_app.ApplyFullRequest(
        profile="tpl-ai-prompt",
        use_ai=True,
        force_message=True,
    )
    args = admin_app._build_apply_args(body)

    assert "--system-prompt" in args
    sp_idx = args.index("--system-prompt") + 1
    assert args[sp_idx] == admin_app.DEFAULT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Inbox reply with conversation history
# ---------------------------------------------------------------------------

def test_inbox_reply_fetches_history_when_use_ai(tmp_path, monkeypatch):
    """send_reply with use_ai=True should load conversation history from HH API."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "reply-hist"})
    cfg = tmp_path / "reply-hist" / "config.json"
    cfg.write_text(
        json.dumps({"token": {"access_token": "tok", "access_expires_at": time.time() + 3600},
                    "openai": {"api_key": "sk-test", "model": "gpt-4o-mini"}}),
        encoding="utf-8",
    )

    hh_calls = []
    ai_calls = []

    def fake_hh_get(profile, path, params=None):
        hh_calls.append(path)
        if "messages" in path:
            return {"items": [
                {"text": "Приглашаем на собеседование", "author": {"participant_type": "employer"}},
                {"text": "Спасибо, жду подробностей", "author": {"participant_type": "applicant"}},
                {"text": "Когда вам удобно?", "author": {"participant_type": "employer"}},
            ], "pages": 1}
        return {}

    def fake_call_openai(cfg_path, system, user, max_tokens=400):
        ai_calls.append(user)
        return "Добрый день! Удобно в среду с 14:00."

    monkeypatch.setattr(admin_app, "_hh_get", fake_hh_get)
    monkeypatch.setattr(admin_app, "_hh_post", lambda *a, **k: {})
    monkeypatch.setattr(admin_app, "_call_openai", fake_call_openai)

    resp = client.post("/api/inbox/12345/reply", json={
        "profile": "reply-hist",
        "message": "",
        "use_ai": True,
        "vacancy_name": "Python Dev",
        "employer_name": "Acme Corp",
        "fetch_history": True,
    })

    assert resp.status_code == 200
    assert resp.json()["sent"] == "Добрый день! Удобно в среду с 14:00."
    # Проверяем что история загружалась
    assert any("messages" in p for p in hh_calls)
    # Проверяем что история попала в AI prompt
    assert any("Когда вам удобно" in u for u in ai_calls)


def test_inbox_reply_uses_provided_history(tmp_path, monkeypatch):
    """send_reply should use history from request body without fetching from HH API."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "reply-prov"})
    (tmp_path / "reply-prov" / "config.json").write_text(
        json.dumps({"openai": {"api_key": "sk-x"}}), encoding="utf-8"
    )

    hh_calls = []
    ai_prompts = []

    monkeypatch.setattr(admin_app, "_hh_get", lambda *a, **k: (hh_calls.append(a), {})[1])
    monkeypatch.setattr(admin_app, "_hh_post", lambda *a, **k: {})
    monkeypatch.setattr(
        admin_app, "_call_openai",
        lambda cfg, sys, user, **kw: (ai_prompts.append(user), "Ответ агента")[1],
    )

    resp = client.post("/api/inbox/99/reply", json={
        "profile": "reply-prov",
        "use_ai": True,
        "vacancy_name": "Dev",
        "employer_name": "Corp",
        "history": [{"text": "Привет!", "author": {"participant_type": "employer"}}],
        "fetch_history": False,  # не загружать из HH
    })

    assert resp.status_code == 200
    # HH API за сообщениями не обращался
    assert not any("messages" in str(c) for c in hh_calls)
    # Но история из тела попала в промпт
    assert any("Привет" in p for p in ai_prompts)


# ---------------------------------------------------------------------------
# Digest endpoint
# ---------------------------------------------------------------------------

def test_digest_returns_action_needed(tmp_path, monkeypatch):
    """/api/agent/digest returns action_needed=reauth when token is missing."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "digest-noauth"})

    resp = client.get("/api/agent/digest?profile=digest-noauth")

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"]["status"] == "no_token"
    assert data["action_needed"] == "reauth"


def test_digest_with_valid_token_no_inbox(tmp_path, monkeypatch):
    """/api/agent/digest returns action_needed=none when token ok and no inbox updates."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "digest-ok"})
    (tmp_path / "digest-ok" / "config.json").write_text(
        json.dumps({"token": {"access_token": "t", "access_expires_at": time.time() + 3600}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(admin_app, "_hh_get", lambda *a, **k: {"items": [], "found": 0})

    resp = client.get("/api/agent/digest?profile=digest-ok")

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"]["status"] == "ok"
    assert data["inbox_needs_reply_count"] == 0
    assert data["action_needed"] == "none"


# ---------------------------------------------------------------------------
# Blacklist endpoints
# ---------------------------------------------------------------------------

def test_add_to_blacklist_calls_hh_api(tmp_path, monkeypatch):
    """/api/employers/blacklist/{id} should call HH API PUT."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "bl-test"})
    (tmp_path / "bl-test" / "config.json").write_text(
        json.dumps({"token": {"access_token": "tok", "access_expires_at": time.time() + 3600}}),
        encoding="utf-8",
    )

    calls = []
    monkeypatch.setattr(
        admin_app, "_hh_request",
        lambda profile, method, path, **kw: (calls.append((method, path)), {})[1],
    )

    resp = client.post("/api/employers/blacklist/12345?profile=bl-test")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert any(m == "PUT" and "blacklisted/12345" in p for m, p in calls)


def test_blacklist_rejects_non_numeric_employer_id(tmp_path, monkeypatch):
    """Blacklist endpoint should reject non-numeric employer_id."""
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "bl-bad"})

    resp = client.post("/api/employers/blacklist/not-a-number?profile=bl-bad")

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# reply-employers operation
# ---------------------------------------------------------------------------

def test_reply_employers_run_builds_correct_args(monkeypatch):
    """reply-employers endpoint should pass --use-ai and context to CLI."""
    captured = {}

    class FakeProcess:
        pid = 7
        returncode = 0
        def communicate(self, timeout=None): return "", ""
        def poll(self): return 0

    class SyncThread:
        def __init__(self, target, daemon=None): self.target = target
        def start(self): self.target()

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeProcess()

    monkeypatch.setattr(admin_app.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(admin_app.threading, "Thread", SyncThread)
    admin_app.running_operations.clear()

    result = admin_app.run_reply_employers(
        admin_app.ReplyEmployersRequest(
            profile="default",
            use_ai=True,
            only_invitations=True,
            max_pages=5,
        )
    )

    assert result["op_id"]
    cmd = captured["cmd"]
    assert "reply-employers" in cmd
    assert "--use-ai" in cmd
    assert "--only-invitations" in cmd
    assert "--no-auto-auth" in cmd


def test_agent_run_allows_reply_employers(tmp_path, monkeypatch):
    """/api/agent/run should accept reply-employers as a valid operation."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-reply"})
    (tmp_path / "agent-reply" / "config.json").write_text(
        json.dumps({"token": {"access_token": "t", "access_expires_at": time.time() + 3600}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        admin_app, "_run_operation",
        lambda op, body, extra=None: {"op_id": "r1", "stdout": "", "stderr": ""},
    )

    resp = client.post("/api/agent/run", json={
        "profile": "agent-reply",
        "operation": "reply-employers",
        "args": ["--use-ai", "--only-invitations"],
    })

    assert resp.status_code == 200
    assert resp.json()["op_id"] == "r1"


def test_agent_run_with_apply_params(tmp_path, monkeypatch):
    """/api/agent/run with apply_params should build and pass correct CLI args."""
    import time

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    client = TestClient(admin_app.app)
    client.post("/api/profiles", json={"profile": "agent-params"})
    cfg = tmp_path / "agent-params" / "config.json"
    cfg.write_text(
        json.dumps({
            "token": {
                "access_token": "live",
                "access_expires_at": time.time() + 3600,
            }
        }),
        encoding="utf-8",
    )

    run_calls = []

    def fake_run_op(op, req_body, extra=None):
        # apply_params args are passed via req_body.extra_args, not extra
        combined = list(extra or []) + list(req_body.extra_args or [])
        run_calls.append({"op": op, "extra": combined})
        return {"op_id": "p1", "stdout": "", "stderr": ""}

    monkeypatch.setattr(admin_app, "_run_operation", fake_run_op)

    resp = client.post("/api/agent/run", json={
        "profile": "agent-params",
        "operation": "apply-vacancies",
        "apply_params": {
            "profile": "agent-params",
            "search": "Python",
            "use_ai": True,
            "force_message": True,
            "skip_tests": True,
        }
    })

    assert resp.status_code == 200
    assert run_calls[0]["op"] == "apply-vacancies"
    extra = run_calls[0]["extra"]
    assert "--search" in extra
    assert "Python" in extra
    assert "--use-ai" in extra
    assert "--force-message" in extra
