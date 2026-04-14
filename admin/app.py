"""
HH Applicant Tool — Web Admin Panel
FastAPI backend

Запуск:
    pip install fastapi uvicorn
    python -m uvicorn admin.app:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="HH Admin Panel", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers: paths
# ---------------------------------------------------------------------------

# Корень проекта (на уровень выше папки admin/)
PROJECT_ROOT = Path(__file__).parent.parent


def _config_root() -> Path:
    # Поддержка CONFIG_DIR (Docker-режим: /app/config или ./config)
    env_config_dir = os.getenv("CONFIG_DIR")
    if env_config_dir:
        return Path(env_config_dir)

    # Проверяем config/ в корне проекта (Docker legacy)
    local_config = PROJECT_ROOT / "config"
    if local_config.exists() and any(local_config.iterdir()):
        return local_config

    # Стандартный путь ОС
    match platform.system():
        case "Windows":
            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        case "Darwin":
            base = Path.home() / "Library" / "Application Support"
        case _:
            base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "hh-applicant-tool"


def _profile_dir(profile: str = "default") -> Path:
    root = _config_root()
    # Если root сам является профилем (CONFIG_DIR указывает прямо на папку с config.json)
    if (root / "config.json").exists():
        return root
    if profile == "default":
        dirs = [d for d in root.iterdir() if d.is_dir()] if root.exists() else []
        return dirs[0] if dirs else root / "default"
    return root / profile


def _db_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "data"


def _config_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "config.json"


def _log_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "log.txt"


def get_profiles() -> list[str]:
    root = _config_root()
    if not root.exists():
        return []
    # Если root сам является профилем
    if (root / "config.json").exists():
        return ["default"]
    return [d.name for d in sorted(root.iterdir()) if d.is_dir()]


def get_conn(profile: str = "default") -> sqlite3.Connection:
    db = _db_path(profile)
    if not db.exists():
        raise HTTPException(404, f"База данных не найдена: {db}")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Helpers: queries
# ---------------------------------------------------------------------------

def q(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def q1(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Routes: system
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    """Проверка состояния: есть ли конфиг и БД."""
    profiles = get_profiles()
    config_root = _config_root()
    status = {
        "config_root": str(config_root),
        "profiles": profiles,
        "ready": False,
        "has_config": False,
        "has_db": False,
    }
    if profiles:
        profile = profiles[0]
        cfg = _config_path(profile)
        db = _db_path(profile)
        status["has_config"] = cfg.exists()
        status["has_db"] = db.exists()
        status["ready"] = cfg.exists() and db.exists()
    return status


@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/api/profiles")
def list_profiles():
    return {"profiles": get_profiles()}


# ---------------------------------------------------------------------------
# Routes: statistics
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats(profile: str = Query("default")):
    conn = get_conn(profile)
    try:
        # Общее кол-во по таблицам
        neg_total = q1(conn, "SELECT count(*) as c FROM negotiations")["c"]
        vac_total = q1(conn, "SELECT count(*) as c FROM vacancies")["c"]
        emp_total = q1(conn, "SELECT count(*) as c FROM employers")["c"]
        skipped_total = q1(conn, "SELECT count(*) as c FROM skipped_vacancies")["c"]
        resume_total = q1(conn, "SELECT count(*) as c FROM resumes")["c"]

        # Отклики по состоянию
        states = q(conn, "SELECT state, count(*) as cnt FROM negotiations GROUP BY state ORDER BY cnt DESC")

        # Отклики по дням (последние 14 дней)
        daily = q(conn, """
            SELECT date(created_at) as day, count(*) as cnt
            FROM negotiations
            WHERE created_at >= date('now', '-14 days')
            GROUP BY day ORDER BY day
        """)

        # Топ-5 причин пропуска вакансий
        skip_reasons = q(conn, """
            SELECT reason, count(*) as cnt
            FROM skipped_vacancies
            GROUP BY reason ORDER BY cnt DESC LIMIT 5
        """)

        # Последние 5 откликов
        recent_neg = q(conn, """
            SELECT n.id, n.state, n.created_at,
                   v.name as vacancy_name, v.alternate_url,
                   e.name as employer_name
            FROM negotiations n
            LEFT JOIN vacancies v ON v.id = n.vacancy_id
            LEFT JOIN employers e ON e.id = n.employer_id
            ORDER BY n.created_at DESC LIMIT 5
        """)

        # Статистика просмотров резюме
        resume_views = q(conn, "SELECT title, total_views, new_views FROM resumes")

        return {
            "totals": {
                "negotiations": neg_total,
                "vacancies": vac_total,
                "employers": emp_total,
                "skipped": skipped_total,
                "resumes": resume_total,
            },
            "negotiations_by_state": states,
            "daily_applications": daily,
            "skip_reasons": skip_reasons,
            "recent_negotiations": recent_neg,
            "resume_views": resume_views,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: negotiations
# ---------------------------------------------------------------------------

@app.get("/api/negotiations")
def list_negotiations(
    profile: str = Query("default"),
    state: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    conn = get_conn(profile)
    try:
        where = "WHERE n.state = ?" if state else ""
        params = [state] if state else []
        params += [limit, offset]
        rows = q(conn, f"""
            SELECT n.id, n.state, n.chat_id, n.created_at, n.updated_at,
                   v.name as vacancy_name, v.alternate_url as vacancy_url,
                   v.salary_from, v.salary_to, v.currency,
                   e.name as employer_name
            FROM negotiations n
            LEFT JOIN vacancies v ON v.id = n.vacancy_id
            LEFT JOIN employers e ON e.id = n.employer_id
            {where}
            ORDER BY n.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(conn, f"SELECT count(*) as c FROM negotiations n {where}", [state] if state else [])["c"]
        return {"items": rows, "total": total}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: vacancies
# ---------------------------------------------------------------------------

@app.get("/api/vacancies")
def list_vacancies(
    profile: str = Query("default"),
    search: str = Query(""),
    limit: int = Query(50),
    offset: int = Query(0),
):
    conn = get_conn(profile)
    try:
        where = "WHERE v.name LIKE ?" if search else ""
        params = [f"%{search}%"] if search else []
        params += [limit, offset]
        rows = q(conn, f"""
            SELECT v.*, e.name as employer_name
            FROM vacancies v
            LEFT JOIN employers e ON e.id = (
                SELECT employer_id FROM negotiations WHERE vacancy_id = v.id LIMIT 1
            )
            {where}
            ORDER BY v.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(conn, f"SELECT count(*) as c FROM vacancies v {where}", [f"%{search}%"] if search else [])["c"]
        return {"items": rows, "total": total}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: skipped vacancies
# ---------------------------------------------------------------------------

@app.get("/api/skipped")
def list_skipped(
    profile: str = Query("default"),
    reason: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    conn = get_conn(profile)
    try:
        where = "WHERE reason = ?" if reason else ""
        params = [reason] if reason else []
        params += [limit, offset]
        rows = q(conn, f"""
            SELECT * FROM skipped_vacancies
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(conn, f"SELECT count(*) as c FROM skipped_vacancies {where}", [reason] if reason else [])["c"]
        return {"items": rows, "total": total}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: employers
# ---------------------------------------------------------------------------

@app.get("/api/employers")
def list_employers(
    profile: str = Query("default"),
    search: str = Query(""),
    limit: int = Query(50),
    offset: int = Query(0),
):
    conn = get_conn(profile)
    try:
        where = "WHERE name LIKE ?" if search else ""
        params = [f"%{search}%"] if search else []
        params += [limit, offset]
        rows = q(conn, f"""
            SELECT e.*,
                   (SELECT count(*) FROM negotiations n WHERE n.employer_id = e.id) as applications_count
            FROM employers e
            {where}
            ORDER BY applications_count DESC, e.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(conn, f"SELECT count(*) as c FROM employers e {where}", [f"%{search}%"] if search else [])["c"]
        return {"items": rows, "total": total}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: resumes
# ---------------------------------------------------------------------------

@app.get("/api/resumes")
def list_resumes(profile: str = Query("default")):
    conn = get_conn(profile)
    try:
        return {"items": q(conn, "SELECT * FROM resumes ORDER BY updated_at DESC")}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: config
# ---------------------------------------------------------------------------

MASKED_KEYS = {"access_token", "refresh_token", "password", "api_key"}


def _mask_config(obj: Any, depth: int = 0) -> Any:
    if isinstance(obj, dict):
        return {
            k: "***" if k in MASKED_KEYS else _mask_config(v, depth + 1)
            for k, v in obj.items()
        }
    return obj


@app.get("/api/config")
def get_config(profile: str = Query("default"), show_secrets: bool = Query(False)):
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "config.json не найден")
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    if not show_secrets:
        data = _mask_config(data)
    return data


class ConfigUpdate(BaseModel):
    data: dict


@app.put("/api/config")
def update_config(body: ConfigUpdate, profile: str = Query("default")):
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "config.json не найден")
    # Читаем текущий конфиг и мёрдж только безопасные ключи
    with open(cfg_path, encoding="utf-8") as f:
        current = json.load(f)

    # Запрещаем перезаписывать токены через API
    safe_keys = {"api_delay", "openai", "email_settings", "proxy_url"}
    for k, v in body.data.items():
        if k in safe_keys:
            if isinstance(v, dict) and isinstance(current.get(k), dict):
                current[k].update(v)
            else:
                current[k] = v

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes: logs
# ---------------------------------------------------------------------------

@app.get("/api/logs")
def get_logs(profile: str = Query("default"), lines: int = Query(200)):
    log_path = _log_path(profile)
    if not log_path.exists():
        return {"lines": []}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": all_lines[-lines:]}


# ---------------------------------------------------------------------------
# Routes: generate cover letter
# ---------------------------------------------------------------------------

class LetterRequest(BaseModel):
    vacancy_name: str
    vacancy_description: str = ""
    employer_name: str = ""
    resume_title: str = ""
    extra: str = ""
    profile: str = "default"


@app.post("/api/generate-letter")
def generate_letter(body: LetterRequest):
    cfg_path = _config_path(body.profile)
    if not cfg_path.exists():
        raise HTTPException(404, "config.json не найден — нет доступа к OpenAI ключу")

    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    openai_cfg = cfg.get("openai") or {}
    api_key = openai_cfg.get("api_key")
    if not api_key:
        raise HTTPException(400, "OpenAI API key не настроен в config.json")

    base_url = openai_cfg.get("base_url", "https://api.openai.com/v1")
    model = openai_cfg.get("model", "gpt-4o-mini")

    try:
        import urllib.request
        import urllib.error

        system_prompt = (
            "Ты опытный HR-специалист и помогаешь писать сопроводительные письма для откликов на вакансии. "
            "Пиши живо, искренне, без шаблонных фраз. Письмо должно быть персонализировано под вакансию. "
            "Объём: 3-4 абзаца, не более 250 слов. Язык: русский."
        )

        user_prompt = (
            f"Напиши сопроводительное письмо для отклика на вакансию.\n\n"
            f"Вакансия: {body.vacancy_name}\n"
            f"Работодатель: {body.employer_name or 'не указан'}\n"
            f"Моё резюме / должность: {body.resume_title or 'не указана'}\n"
        )
        if body.vacancy_description:
            user_prompt += f"\nОписание вакансии:\n{body.vacancy_description[:1500]}\n"
        if body.extra:
            user_prompt += f"\nДополнительные пожелания: {body.extra}\n"

        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 600,
        }).encode()

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.load(resp)

        letter = result["choices"][0]["message"]["content"]
        return {"letter": letter}

    except Exception as e:
        raise HTTPException(500, f"Ошибка OpenAI: {e}")


# ---------------------------------------------------------------------------
# Routes: run operations
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    profile: str = "default"
    dry_run: bool = False
    extra_args: list[str] = []


@app.post("/api/run/update-resumes")
def run_update_resumes(body: RunRequest):
    return _run_operation("update-resumes", body)


@app.post("/api/run/apply-vacancies")
def run_apply_vacancies(body: RunRequest):
    args = []
    if body.dry_run:
        args.append("--dry-run")
    return _run_operation("apply-vacancies", body, extra=args)


def _run_operation(op: str, body: RunRequest, extra: list[str] = []) -> dict:
    cmd = [
        sys.executable, "-m", "hh_applicant_tool",
        "--profile", body.profile,
        op,
    ] + extra + body.extra_args

    project_root = Path(__file__).parent.parent

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_root),
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Операция заняла слишком много времени (>5 мин)")
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin.app:app", host="127.0.0.1", port=8000, reload=True)
