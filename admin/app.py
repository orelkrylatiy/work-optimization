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
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hh_applicant_tool import constants
from hh_applicant_tool.api import errors as api_errors
from hh_applicant_tool.storage.utils import init_db

app = FastAPI(title="HH Admin Panel", version="1.0.0")

# Отслеживание запущенных операций
running_operations = {}
operations_lock = threading.Lock()

# Устанавливаем UTF-8 для всех JSON ответов
app.default_response_class = JSONResponse

# Middleware для явного указания UTF-8 кодировки
@app.middleware("http")
async def add_utf8_header(request, call_next):
    response = await call_next(request)
    if "content-type" in response.headers:
        response.headers["content-type"] = response.headers["content-type"].replace("charset=", "").split(";")[0] + "; charset=utf-8"
    return response

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
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _build_local_cli_cmd(args: list[str]) -> list[str]:
    """Run CLI from local src tree to avoid env drift."""
    return [
        sys.executable,
        "-c",
        (
            "import sys; "
            "sys.path.insert(0, 'src'); "
            "from hh_applicant_tool.main import main; "
            "raise SystemExit(main(sys.argv[1:]))"
        ),
        *args,
    ]


def _config_root() -> Path:
    # Поддержка CONFIG_DIR (Docker-режим: /app/config или ./config)
    env_config_dir = os.getenv("CONFIG_DIR")
    if env_config_dir:
        return Path(env_config_dir)

    # Проверяем config/ в корне проекта (Docker legacy)
    # Считаем папку "с данными" только если в ней есть config.json
    # или подпапки с config.json (профили) — игнорируем .gitkeep и yaml-файлы
    local_config = PROJECT_ROOT / "config"
    if local_config.exists() and (
        (local_config / "config.json").exists()
        or any(
            d.is_dir() and (d / "config.json").exists()
            for d in local_config.iterdir()
        )
    ):
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
    profile = _validate_profile_name(profile)
    root = _config_root()
    # Keep compatibility with a legacy CONFIG_DIR that points directly to one
    # profile, but never collapse named accounts into the same directory.
    if profile == constants.ADMIN_DEFAULT_PROFILE and (root / "config.json").exists():
        return root
    return root / profile


def _validate_profile_name(profile: str) -> str:
    normalized = (profile or "").strip()
    if not normalized:
        raise HTTPException(400, "Profile name is required")
    if normalized in {".", ".."} or not PROFILE_NAME_RE.fullmatch(normalized):
        raise HTTPException(
            400,
            "Invalid profile name. Use letters, numbers, dot, dash or underscore.",
        )
    return normalized


def _ensure_profile_storage(profile: str) -> dict[str, Any]:
    profile = _validate_profile_name(profile)
    profile_dir = _profile_dir(profile)
    created = not profile_dir.exists()
    profile_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        with open(cfg_path, "w", encoding="utf-8") as fp:
            json.dump({}, fp, indent=2, ensure_ascii=False)

    db_path = _db_path(profile)
    if not db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            init_db(conn)
            conn.commit()
        finally:
            conn.close()

    return {
        "profile": profile,
        "created": created,
        "config_path": str(cfg_path),
        "db_path": str(db_path),
    }


def _db_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "data"


def _config_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "config.json"


def _cookies_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "cookies.txt"


def _log_path(profile: str = "default") -> Path:
    return _profile_dir(profile) / "log.txt"


def get_profiles() -> list[str]:
    root = _config_root()
    if not root.exists():
        return []
    profiles = [
        d.name
        for d in sorted(root.iterdir())
        if d.is_dir() and PROFILE_NAME_RE.fullmatch(d.name)
    ]
    if (root / "config.json").exists():
        return [
            constants.ADMIN_DEFAULT_PROFILE,
            *[p for p in profiles if p != constants.ADMIN_DEFAULT_PROFILE],
        ]
    return profiles


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


def _build_optional_filter(
    column: str,
    value: str | None,
    *,
    like: bool = False,
) -> tuple[str, list[str]]:
    if not value:
        return "", []
    if like:
        return f"WHERE {column} LIKE ?", [f"%{value}%"]
    return f"WHERE {column} = ?", [value]


# ---------------------------------------------------------------------------
# Routes: system
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"ok": True}


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


@app.get("/api/constants")
def get_constants():
    """Возвращает константы API для фронтенда."""
    return {
        "API_PREFIX": constants.ADMIN_API_PREFIX,
        "endpoints": {
            "status": constants.ADMIN_API_STATUS,
            "profiles": constants.ADMIN_API_PROFILES,
            "stats": constants.ADMIN_API_STATS,
            "negotiations": constants.ADMIN_API_NEGOTIATIONS,
            "vacancies": constants.ADMIN_API_VACANCIES,
            "skipped": constants.ADMIN_API_SKIPPED,
            "employers": constants.ADMIN_API_EMPLOYERS,
            "resumes": constants.ADMIN_API_RESUMES,
            "config": constants.ADMIN_API_CONFIG,
            "logs": constants.ADMIN_API_LOGS,
            "user": constants.ADMIN_API_USER,
            "whoami": "/api/whoami",
            "logout": constants.ADMIN_API_AUTH_LOGOUT,
            "reauthorize": constants.ADMIN_API_AUTH_REAUTHORIZE,
            "generate_letter": constants.ADMIN_API_GENERATE_LETTER,
            "run": constants.ADMIN_API_RUN,
            "cancel": constants.ADMIN_API_CANCEL,
            "operations": constants.ADMIN_API_OPERATIONS,
            "operation_status": constants.ADMIN_API_OPERATION_STATUS,
        },
        "operations": {
            "update_resumes": constants.ADMIN_OP_UPDATE_RESUMES,
            "apply_vacancies": constants.ADMIN_OP_APPLY_VACANCIES,
        },
        "defaults": {
            "profile": constants.ADMIN_DEFAULT_PROFILE,
            "response_delay": f"{constants.RESPONSE_DELAY_MIN}-{constants.RESPONSE_DELAY_MAX}",
        }
    }


@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).parent / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/api/profiles")
def list_profiles():
    return {"profiles": get_profiles()}


class ProfileCreateRequest(BaseModel):
    profile: str


@app.post("/api/profiles")
def create_profile(body: ProfileCreateRequest):
    return {"ok": True, **_ensure_profile_storage(body.profile)}


@app.get("/api/whoami")
def get_whoami(profile: str = Query("default")):
    """Return raw output of `hh-applicant-tool whoami -v` for selected profile."""
    profile = _validate_profile_name(profile)
    # Используем --no-auto-auth чтобы не запускалась инициализация браузера
    cmd = _build_local_cli_cmd(["-v", "--profile-id", profile, "whoami"])
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["CONFIG_DIR"] = str(_config_root())
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,  # Увеличен таймаут с 20с до 60с
            env=env,
            check=False,
        )
        stdout = proc.stdout or ""
        # Expected line format:
        # 🆔 <id> <ФИО> [ ...counters... ]
        full_name = None
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "🆔" in line and "[" in line:
                prefix = line.split("[", 1)[0].strip()
                parts = prefix.split()
                if len(parts) >= 3:
                    full_name = " ".join(parts[2:]).strip() or None
                break

        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": proc.stderr or "",
            "command": "hh-applicant-tool whoami -v",
            "profile": profile,
            "full_name": full_name,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Команда whoami превысила лимит времени (60с)")
    except Exception as ex:
        raise HTTPException(500, f"Ошибка запуска whoami: {ex}") from ex


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
        where, where_params = _build_optional_filter("n.state", state)
        params = list(where_params)
        params += [limit, offset]
        rows = q(conn, """
            SELECT n.id, n.state, n.chat_id, n.created_at, n.updated_at,
                   v.name as vacancy_name, v.alternate_url as vacancy_url,
                   v.salary_from, v.salary_to, v.currency,
                   e.name as employer_name
            FROM negotiations n
            LEFT JOIN vacancies v ON v.id = n.vacancy_id
            LEFT JOIN employers e ON e.id = n.employer_id
        """ + where + """
            ORDER BY n.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(
            conn,
            "SELECT count(*) as c FROM negotiations n " + where,
            where_params,
        )["c"]
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
        where, where_params = _build_optional_filter("v.name", search, like=True)
        params = list(where_params)
        params += [limit, offset]
        rows = q(conn, """
            SELECT v.*, e.name as employer_name
            FROM vacancies v
            LEFT JOIN employers e ON e.id = (
                SELECT employer_id FROM negotiations WHERE vacancy_id = v.id LIMIT 1
            )
        """ + where + """
            ORDER BY v.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(
            conn,
            "SELECT count(*) as c FROM vacancies v " + where,
            where_params,
        )["c"]
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
        where, where_params = _build_optional_filter("reason", reason)
        params = list(where_params)
        params += [limit, offset]
        rows = q(conn, """
            SELECT * FROM skipped_vacancies
        """ + where + """
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(
            conn,
            "SELECT count(*) as c FROM skipped_vacancies " + where,
            where_params,
        )["c"]
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
        where, where_params = _build_optional_filter("e.name", search, like=True)
        params = list(where_params)
        params += [limit, offset]
        rows = q(conn, """
            SELECT e.*,
                   (SELECT count(*) FROM negotiations n WHERE n.employer_id = e.id) as applications_count
            FROM employers e
        """ + where + """
            ORDER BY applications_count DESC, e.created_at DESC
            LIMIT ? OFFSET ?
        """, params)
        total = q1(
            conn,
            "SELECT count(*) as c FROM employers e " + where,
            where_params,
        )["c"]
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

MASKED_KEYS = constants.MASKED_CONFIG_KEYS


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
    try:
        data = _load_and_validate_config(cfg_path)
    except ValidationError as ex:
        raise HTTPException(400, f"Некорректный config.json: {ex}") from ex
    if not show_secrets:
        data = _mask_config(data)
    return data


class ConfigUpdate(BaseModel):
    data: dict


class OpenAIConfigModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class AdminConfigModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    api_delay: float | int | None = None
    proxy_url: str | None = None
    email_settings: dict[str, Any] | None = None
    openai: OpenAIConfigModel | dict[str, Any] | None = None
    letter_templates: dict[str, str] | None = None   # именованные шаблоны писем


# Встроенные шаблоны — будут добавлены при первом вызове /api/letter-templates/seed
DEFAULT_LETTER_TEMPLATES: dict[str, str] = {
    "universal": (
        "{Здравствуйте|Добрый день}!\n\n"
        "Меня зовут %(first_name)s, и я {хотел бы|хочу} откликнуться на вакансию «%(vacancy_name)s» в компании %(employer_name)s.\n\n"
        "Я внимательно ознакомился с требованиями и уверен, что мой опыт {соответствует|совпадает с} вашим ожиданиям. "
        "{Готов|Буду рад} {рассказать подробнее|обсудить детали} на собеседовании.\n\n"
        "С уважением, %(first_name)s %(last_name)s"
    ),
    "short": (
        "{Здравствуйте|Добрый день}! "
        "Откликаюсь на вакансию «%(vacancy_name)s». "
        "{Уверен, что|Считаю, что} мой опыт будет полезен вашей команде. "
        "Готов к {обсуждению деталей|собеседованию} в {удобное для вас время|любое время}."
    ),
    "motivated": (
        "{Здравствуйте|Добрый день}, команда %(employer_name)s!\n\n"
        "Вакансия «%(vacancy_name)s» сразу привлекла моё внимание — "
        "{она точно совпадает с моим опытом|требования совпадают с моими компетенциями}. "
        "В резюме «%(resume_title)s» подробно описан мой путь, но если коротко: "
        "я {умею решать задачи системно|нацелен на результат} и {быстро вхожу в контекст|легко адаптируюсь}.\n\n"
        "Буду рад {познакомиться с командой|пообщаться} и рассказать о своём опыте подробнее.\n\n"
        "С уважением, %(first_name)s"
    ),
    "remote": (
        "{Здравствуйте|Добрый день}!\n\n"
        "Откликаюсь на вакансию «%(vacancy_name)s». "
        "Я {успешно работаю|работаю} в удалённом формате {уже несколько лет|давно} — "
        "умею {самостоятельно организовывать работу|эффективно работать без офиса}, "
        "{соблюдать дедлайны|не срывать сроки} и {поддерживать связь с командой|быть на связи}.\n\n"
        "Готов приступить {в ближайшее время|сразу после согласования}.\n\n"
        "С уважением, %(first_name)s %(last_name)s"
    ),
    "experienced": (
        "{Здравствуйте|Добрый день}!\n\n"
        "Рассматриваю вакансию «%(vacancy_name)s» в %(employer_name)s как {интересную|привлекательную} возможность. "
        "За {годы практики|время работы} я {накопил|приобрёл} опыт, который {напрямую|точно} "
        "соответствует вашим требованиям.\n\n"
        "Подробности — в резюме «%(resume_title)s». "
        "{Буду рад|С удовольствием} {обсудить детали|познакомиться} при {созвоне|собеседовании}.\n\n"
        "%(first_name)s %(last_name)s"
    ),
}


def _load_and_validate_config(cfg_path: Path) -> dict[str, Any]:
    with open(cfg_path, encoding="utf-8") as f:
        raw = json.load(f)
    validated = AdminConfigModel.model_validate(raw)
    return validated.model_dump(mode="python", exclude_none=True)


@app.put("/api/config")
def update_config(body: ConfigUpdate, profile: str = Query("default")):
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "config.json не найден")
    # Читаем текущий конфиг и мёрдж только безопасные ключи
    try:
        current = _load_and_validate_config(cfg_path)
    except ValidationError as ex:
        raise HTTPException(400, f"Некорректный config.json: {ex}") from ex

    # Запрещаем перезаписывать токены через API
    safe_keys = {"api_delay", "openai", "email_settings", "proxy_url", "letter_templates"}
    for k, v in body.data.items():
        if k in safe_keys:
            if isinstance(v, dict) and isinstance(current.get(k), dict):
                current[k].update(v)
            else:
                current[k] = v

    try:
        current = AdminConfigModel.model_validate(current).model_dump(
            mode="python",
            exclude_none=True,
        )
    except ValidationError as ex:
        raise HTTPException(400, f"Некорректные данные конфига: {ex}") from ex

    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes: user / authorization
# ---------------------------------------------------------------------------

@app.get("/api/user")
def get_user_info(profile: str = Query("default")):
    """Получить информацию о текущем авторизованном пользователе и статусе токена."""
    profile = _validate_profile_name(profile)
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        return {"token_valid": False, "error": "Profile not found"}

    try:
        config = _load_and_validate_config(cfg_path)
    except Exception:
        return {"token_valid": False, "error": "Failed to load config"}

    # Проверяем есть ли токен
    token_info = config.get("token", {})
    access_token = token_info.get("access_token")
    refresh_token = token_info.get("refresh_token")
    expires_at = token_info.get("access_expires_at")

    if not access_token:
        return {"token_valid": False, "error": "Not authorized"}

    # Проверяем истекает ли токен
    expires_in_seconds = None
    if expires_at:
        expires_in_seconds = max(0, expires_at - time.time())

    # Пытаемся получить информацию о пользователе через HH API
    try:
        from hh_applicant_tool.api import client as api_client
        from hh_applicant_tool.constants import DESKTOP_USER_AGENT

        # Создаем API клиент с токеном
        api = api_client.ApiClient(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=expires_at,
            user_agent=DESKTOP_USER_AGENT,
        )

        # Получаем информацию о текущем пользователе
        user_data = api.get("/me")

        return {
            "token_valid": True,
            "email": user_data.get("email"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "expires_in_seconds": expires_in_seconds,
        }
    except api_errors.Forbidden as ex:
        return {
            "token_valid": False,
            "error": str(ex),
            "expires_in_seconds": expires_in_seconds,
        }
    except api_errors.ClientError as ex:
        return {
            "token_valid": False,
            "error": str(ex),
            "expires_in_seconds": expires_in_seconds,
        }
    except Exception as ex:
        # Если не смогли получить данные, возвращаем минimalную информацию
        return {
            "token_valid": True,
            "email": "unknown",
            "first_name": "User",
            "last_name": "",
            "expires_in_seconds": expires_in_seconds,
            "error": str(ex),
        }


@app.post("/api/auth/logout")
def logout(profile: str = Query("default")):
    """Удалить токены авторизации."""
    profile = _validate_profile_name(profile)
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "Profile not found")

    try:
        config = _load_and_validate_config(cfg_path)
    except Exception as ex:
        raise HTTPException(400, f"Failed to load config: {ex}")

    # Удаляем токены
    if "token" in config:
        config["token"] = {}

    # Сохраняем конфиг
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        raise HTTPException(500, f"Failed to save config: {ex}")

    cookies_path = _cookies_path(profile)
    cookies_deleted = False
    if cookies_path.exists():
        cookies_path.unlink(missing_ok=True)
        cookies_deleted = True

    return {
        "ok": True,
        "message": "Logged out successfully",
        "cookies_deleted": cookies_deleted,
    }


@app.post("/api/auth/reauthorize")
def reauthorize(
    profile: str = Query("default"),
    manual: bool = Query(True),
    visible: bool = Query(True),
):
    """Запустить операцию авторизации."""
    profile = _validate_profile_name(profile)
    _ensure_profile_storage(profile)

    body = RunRequest(profile=profile)
    extra = []
    if manual:
        extra.append("--manual")
    if visible:
        extra.append("--no-headless")

    result = _run_operation("authorize", body, extra=extra)
    result["profile"] = profile
    return result


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

    try:
        cfg = _load_and_validate_config(cfg_path)
    except ValidationError as ex:
        raise HTTPException(400, f"Некорректный config.json: {ex}") from ex

    openai_cfg = cfg.get("openai") or {}
    api_key = openai_cfg.get("api_key")
    if not api_key:
        raise HTTPException(400, "OpenAI API key не настроен в config.json")

    base_url = openai_cfg.get("base_url", constants.OPENAI_DEFAULT_BASE_URL)
    model = openai_cfg.get("model", constants.OPENAI_DEFAULT_MODEL)

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
    extra_args: list[str] = Field(default_factory=list)
    response_delay: str = f"{constants.RESPONSE_DELAY_MIN}-{constants.RESPONSE_DELAY_MAX}"


@app.post("/api/run/update-resumes")
def run_update_resumes(body: RunRequest):
    return _run_operation("update-resumes", body)


@app.post("/api/run/apply-vacancies")
def run_apply_vacancies(body: RunRequest):
    args = []
    if body.dry_run:
        args.append("--dry-run")
    if body.response_delay and body.response_delay != f"{constants.RESPONSE_DELAY_MIN}-{constants.RESPONSE_DELAY_MAX}":
        args.extend(["--response-delay", body.response_delay])
    return _run_operation("apply-vacancies", body, extra=args)


def _run_operation(op: str, body: RunRequest, extra: list[str] | None = None) -> dict:
    import uuid

    profile = _validate_profile_name(body.profile)
    extra = extra or []

    # Генерируем уникальный ID для операции
    op_id = str(uuid.uuid4())[:8]

    cli_args = ["--profile-id", profile]
    if op != "authorize":
        cli_args.append("--no-auto-auth")
    cmd = _build_local_cli_cmd(cli_args + [op] + extra + body.extra_args)

    # Функция для выполнения в потоке
    def execute_operation():
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env["CONFIG_DIR"] = str(_config_root())
            print(f"DEBUG: Starting operation {op_id}: {' '.join(cmd)}")

            # Используем Popen чтобы можно было отменить процесс.
            # stdin=DEVNULL гарантирует что процесс не зависнет ожидая ввода —
            # любая попытка читать stdin сразу получит EOF.
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(PROJECT_ROOT),
                env=env,
            )

            # Сохраняем процесс для возможности отмены
            with operations_lock:
                running_operations[op_id] = process
            print(f"DEBUG: Process {op_id} started with PID {process.pid}")

            try:
                # Ждём завершения с таймаутом
                stdout, stderr = process.communicate(timeout=constants.ADMIN_OPERATION_TIMEOUT)
                returncode = process.returncode
                print(f"DEBUG: Process {op_id} completed with code {returncode}")
            except subprocess.TimeoutExpired:
                print(f"DEBUG: Process {op_id} timeout - terminating")
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    print(f"DEBUG: Force killing process {op_id}")
                    process.kill()
                    stdout, stderr = process.communicate()
                    returncode = process.returncode

            # Сохраняем результат
            with operations_lock:
                if op_id in running_operations:
                    running_operations[op_id] = {
                        "completed": True,
                        "returncode": int(returncode) if returncode is not None else 0,
                        "stdout": stdout[-constants.ADMIN_LOG_OUTPUT_LIMIT:] if stdout else "",
                        "stderr": stderr[-constants.ADMIN_LOG_ERROR_LIMIT:] if stderr else "",
                    }

        except Exception as e:
            print(f"DEBUG: Exception in operation {op_id}: {type(e).__name__}: {e}")
            import traceback
            print(traceback.format_exc())
            with operations_lock:
                if op_id in running_operations:
                    running_operations[op_id] = {
                        "completed": True,
                        "error": str(e),
                        "returncode": 1,
                        "stdout": "",
                        "stderr": str(e),
                    }

    # Запускаем операцию в отдельном потоке
    thread = threading.Thread(target=execute_operation, daemon=True)
    thread.start()

    # Сразу возвращаем ID операции
    return {
        "op_id": op_id,
        "stdout": "Операция запущена в фоне...",
        "stderr": "",
    }


# ---------------------------------------------------------------------------
# Routes: cancel operations
# ---------------------------------------------------------------------------

@app.post("/api/cancel/{op_id}")
def cancel_operation(op_id: str):
    """Отменить выполняющуюся операцию."""
    # Получаем процесс под защитой lock
    with operations_lock:
        process = running_operations.get(op_id)
        if not process:
            raise HTTPException(404, f"Операция {op_id} не найдена или уже завершена")

        # Проверяем, что это действительно процесс, а не завершённый результат
        if isinstance(process, dict) and process.get("completed"):
            raise HTTPException(404, f"Операция {op_id} уже завершена")

    try:
        print(f"DEBUG: Terminating process {op_id}")
        process.terminate()
        # Даём 3 секунды на graceful shutdown
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            print(f"DEBUG: Force killing process {op_id}")
            process.kill()
            process.wait()

        with operations_lock:
            running_operations.pop(op_id, None)
        return {"ok": True, "message": f"Операция {op_id} отменена"}
    except Exception as e:
        raise HTTPException(500, f"Ошибка при отмене: {e}")


@app.get("/api/operations")
def list_operations():
    """Список запущенных операций."""
    with operations_lock:
        ops = []
        for op_id, proc_or_result in running_operations.items():
            if isinstance(proc_or_result, dict) and proc_or_result.get("completed"):
                # Завершённая операция
                ops.append({
                    "op_id": op_id,
                    "running": False,
                    "returncode": proc_or_result.get("returncode"),
                })
            else:
                # Выполняющаяся операция (процесс)
                ops.append({
                    "op_id": op_id,
                    "running": proc_or_result.poll() is None,
                    "pid": proc_or_result.pid,
                })
    return {"operations": ops}


@app.get("/api/operation-status/{op_id}")
def get_operation_status(op_id: str):
    """Получить статус конкретной операции."""
    with operations_lock:
        item = running_operations.get(op_id)

    if not item:
        raise HTTPException(404, f"Операция {op_id} не найдена")

    if isinstance(item, dict) and item.get("completed"):
        # Завершённая операция
        return {
            "op_id": op_id,
            "running": False,
            "returncode": item.get("returncode"),
            "stdout": item.get("stdout", ""),
            "stderr": item.get("stderr", ""),
        }
    else:
        # Выполняющаяся операция
        return {
            "op_id": op_id,
            "running": True,
            "pid": item.pid if hasattr(item, 'pid') else None,
        }


# ---------------------------------------------------------------------------
# HH API proxy helper
# ---------------------------------------------------------------------------

import requests as _requests


def _hh_request(profile: str, method: str, path: str, **kwargs) -> Any:
    """Прямой запрос к HH API через сохранённый access_token."""
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "config.json не найден")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    token = (cfg.get("token") or {}).get("access_token")
    if not token:
        raise HTTPException(
            401,
            "Нет access_token. Авторизуйтесь: python -m hh_applicant_tool auth"
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": cfg.get("user_agent", constants.DESKTOP_USER_AGENT),
        "X-HH-App-Active": "true",
        "Accept": "application/json",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    resp = _requests.request(
        method,
        f"https://api.hh.ru{path}",
        headers=headers,
        timeout=15,
        **kwargs,
    )
    if resp.status_code == 401:
        raise HTTPException(
            401,
            "Токен устарел. Обновите: python -m hh_applicant_tool refresh-token"
        )
    if not resp.ok:
        raise HTTPException(resp.status_code, f"HH API: {resp.text[:300]}")
    if resp.status_code == 204:
        return {}
    return resp.json()


def _hh_get(profile: str, path: str, params: dict | None = None) -> Any:
    return _hh_request(profile, "GET", path, params=params or {})


def _hh_post(profile: str, path: str, data: dict | None = None) -> Any:
    return _hh_request(profile, "POST", path, json=data or {})


def _hh_delete(profile: str, path: str) -> Any:
    return _hh_request(profile, "DELETE", path)


# ---------------------------------------------------------------------------
# Routes: inbox (сообщения от работодателей)
# ---------------------------------------------------------------------------

@app.get("/api/inbox")
def get_inbox(
    profile: str = Query("default"),
    status: str = Query(""),      # active, archived, discard, invitation, etc.
    page: int = Query(0),
    per_page: int = Query(20),
):
    """Список переписок с работодателями напрямую из HH API."""
    params: dict[str, Any] = {"page": page, "per_page": per_page}
    if status:
        params["status"] = status

    data = _hh_get(profile, "/negotiations", params)
    # Нормализуем поля для удобства фронтенда
    items = []
    for n in data.get("items", []):
        vacancy = n.get("vacancy") or {}
        employer = vacancy.get("employer") or {}
        last_msg = (n.get("messages_url") or "")
        items.append({
            "id": n.get("id"),
            "state": (n.get("state") or {}).get("id", ""),
            "state_name": (n.get("state") or {}).get("name", ""),
            "created_at": n.get("created_at"),
            "updated_at": n.get("updated_at"),
            "vacancy_id": vacancy.get("id"),
            "vacancy_name": vacancy.get("name"),
            "vacancy_url": vacancy.get("alternate_url"),
            "employer_id": employer.get("id"),
            "employer_name": employer.get("name"),
            "employer_logo": (employer.get("logo_urls") or {}).get("90"),
            "viewed_by_opponent": n.get("viewed_by_opponent"),
            "has_updates": n.get("has_updates", False),
            "messages_url": last_msg,
        })
    return {
        "items": items,
        "found": data.get("found", 0),
        "page": data.get("page", 0),
        "pages": data.get("pages", 0),
        "per_page": data.get("per_page", per_page),
    }


@app.get("/api/inbox/{neg_id}/messages")
def get_messages(neg_id: int, profile: str = Query("default")):
    """Получить историю сообщений переписки."""
    data = _hh_get(profile, f"/negotiations/{neg_id}/messages", {"per_page": 50})
    messages = []
    for m in data.get("items", []):
        author = m.get("author") or {}
        messages.append({
            "id": m.get("id"),
            "text": m.get("text", ""),
            "created_at": m.get("created_at"),
            "is_employer": author.get("participant_type") == "employer",
            "author_name": author.get("name", ""),
            "viewed": m.get("viewed_by_opponent", False),
        })
    return {"messages": messages, "found": data.get("found", 0)}


class ReplyRequest(BaseModel):
    message: str
    use_ai: bool = False
    profile: str = "default"
    vacancy_name: str = ""
    employer_name: str = ""


@app.post("/api/inbox/{neg_id}/reply")
def send_reply(neg_id: int, body: ReplyRequest):
    """Отправить сообщение в переписку."""
    text = body.message.strip()

    if body.use_ai and not text:
        # Генерируем ответ через AI
        cfg_path = _config_path(body.profile)
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            openai_cfg = cfg.get("openai") or {}
            api_key = openai_cfg.get("api_key")
            if api_key:
                import urllib.request
                system = (
                    "Ты помогаешь отвечать на сообщения от HR-специалистов в рамках поиска работы. "
                    "Пиши вежливо, профессионально, кратко. Язык: русский."
                )
                user = f"Напиши вежливый ответ HR по вакансии «{body.vacancy_name}» от компании «{body.employer_name}»."
                payload = json.dumps({
                    "model": openai_cfg.get("model", constants.OPENAI_DEFAULT_MODEL),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300,
                }).encode()
                req = urllib.request.Request(
                    f"{openai_cfg.get('base_url', constants.OPENAI_DEFAULT_BASE_URL).rstrip('/')}/chat/completions",
                    data=payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=20) as r:
                    result = json.load(r)
                text = result["choices"][0]["message"]["content"]

    if not text:
        raise HTTPException(400, "Сообщение не может быть пустым")

    _hh_post(body.profile, f"/negotiations/{neg_id}/messages", {"message": text})
    return {"ok": True, "sent": text}


# ---------------------------------------------------------------------------
# Routes: очистка отказов
# ---------------------------------------------------------------------------

@app.post("/api/inbox/clear-rejections")
def clear_rejections(
    profile: str = Query("default"),
    dry_run: bool = Query(False),
):
    """Скрыть все переписки со статусом 'discard' (отказ)."""
    data = _hh_get(profile, "/negotiations", {"status": "discard", "per_page": 50})
    total = data.get("found", 0)
    items = data.get("items", [])
    cleared = []
    errors = []

    for n in items:
        neg_id = n.get("id")
        if not neg_id:
            continue
        if dry_run:
            cleared.append(neg_id)
            continue
        try:
            _hh_delete(profile, f"/negotiations/active/{neg_id}")
            cleared.append(neg_id)
        except HTTPException as e:
            errors.append({"id": neg_id, "error": e.detail})

    return {
        "total_discards": total,
        "cleared": len(cleared),
        "cleared_ids": cleared,
        "errors": errors,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Routes: именованные шаблоны писем (хранятся в config.json → letter_templates)
# ---------------------------------------------------------------------------

@app.get("/api/letter-templates")
def list_letter_templates(profile: str = Query("default")):
    """Список всех шаблонов писем для профиля."""
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        return {"templates": {}, "default_templates": DEFAULT_LETTER_TEMPLATES}
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    return {
        "templates": cfg.get("letter_templates") or {},
        "default_templates": DEFAULT_LETTER_TEMPLATES,
    }


class LetterTemplateUpsert(BaseModel):
    name: str
    content: str
    profile: str = "default"


@app.post("/api/letter-templates")
def upsert_letter_template(body: LetterTemplateUpsert):
    """Создать или обновить именованный шаблон письма."""
    name = body.name.strip()
    if not name or not re.match(r"^[A-Za-z0-9_-]{1,64}$", name):
        raise HTTPException(400, "Имя шаблона: только буквы, цифры, _ и - (1-64 символа)")
    if len(body.content) > 10_000:
        raise HTTPException(400, "Шаблон слишком большой (>10KB)")
    cfg_path = _config_path(body.profile)
    if not cfg_path.exists():
        raise HTTPException(404, "Профиль не найден")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    templates = cfg.get("letter_templates") or {}
    templates[name] = body.content
    cfg["letter_templates"] = templates
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return {"ok": True, "name": name}


@app.delete("/api/letter-templates/{name}")
def delete_letter_template(name: str, profile: str = Query("default")):
    """Удалить шаблон письма."""
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "Профиль не найден")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    templates = cfg.get("letter_templates") or {}
    if name not in templates:
        raise HTTPException(404, f"Шаблон '{name}' не найден")
    del templates[name]
    cfg["letter_templates"] = templates
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return {"ok": True}


@app.post("/api/letter-templates/seed")
def seed_letter_templates(profile: str = Query("default"), overwrite: bool = Query(False)):
    """
    Заполнить шаблоны встроенными заготовками.
    По умолчанию не перезаписывает уже существующие.
    """
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        raise HTTPException(404, "Профиль не найден")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    templates = cfg.get("letter_templates") or {}
    added = []
    for name, content in DEFAULT_LETTER_TEMPLATES.items():
        if overwrite or name not in templates:
            templates[name] = content
            added.append(name)
    cfg["letter_templates"] = templates
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return {"ok": True, "added": added, "total": len(templates)}


def _resolve_letter_file(profile: str, template_name: str) -> Path | None:
    """
    Достаёт шаблон по имени из config.json и записывает во временный файл профиля.
    Возвращает путь к файлу или None если шаблон не найден.
    """
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        return None
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    # Ищем сначала в пользовательских шаблонах, потом в встроенных
    templates = cfg.get("letter_templates") or {}
    content = templates.get(template_name) or DEFAULT_LETTER_TEMPLATES.get(template_name)
    if not content:
        return None

    # Пишем во временный файл в директории профиля
    tmp_path = _profile_dir(profile) / "_letter_tmp.txt"
    tmp_path.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Routes: шаблон письма (letter.txt)
# ---------------------------------------------------------------------------

LETTER_FILE = PROJECT_ROOT / "letter.txt"


@app.get("/api/letter-template")
def get_letter_template():
    """Получить содержимое шаблона сопроводительного письма."""
    if not LETTER_FILE.exists():
        return {"content": "", "exists": False}
    content = LETTER_FILE.read_text(encoding="utf-8", errors="replace")
    return {"content": content, "exists": True}


class LetterTemplateUpdate(BaseModel):
    content: str


@app.put("/api/letter-template")
def update_letter_template(body: LetterTemplateUpdate):
    """Сохранить шаблон письма."""
    if len(body.content) > 50_000:
        raise HTTPException(400, "Шаблон слишком большой (>50KB)")
    LETTER_FILE.write_text(body.content, encoding="utf-8")
    return {"ok": True, "size": len(body.content)}


# ---------------------------------------------------------------------------
# Routes: полная форма запуска откликов
# ---------------------------------------------------------------------------

# Промпты по умолчанию для AI-генерации писем (лучше дефолтных в CLI)
DEFAULT_SYSTEM_PROMPT = (
    "Ты опытный специалист, помогающий писать сопроводительные письма для откликов на вакансии на hh.ru. "
    "Пиши живо, от первого лица, без шаблонных клише. "
    "Письмо должно быть персонализировано под конкретную вакансию и компанию. "
    "Объём: 3-4 предложения, не более 150 слов. Язык: русский. "
    "Не используй placeholder'ы — твой ответ отправляется напрямую."
)
DEFAULT_MESSAGE_PROMPT = (
    "Напиши краткое сопроводительное письмо от моего имени для вакансии"
)


class ApplyFullRequest(BaseModel):
    profile: str = "default"
    dry_run: bool = False
    # Поиск
    search: str = ""
    resume_id: str = ""
    # Фильтры
    experience: str = ""          # noExperience / between1And3 / between3And6 / moreThan6
    salary: int | None = None
    only_with_salary: bool = False
    schedule: list[str] = []      # fullDay, shift, flexible, remote, flyInFlyOut
    employment: list[str] = []    # full, part, project, volunteer, probation
    area: list[str] = []          # коды городов: "1" = Москва, "2" = СПб
    excluded_filter: str = ""     # regex для исключения по названию
    # AI
    ai_filter: str = ""           # "" | "light" | "heavy"
    use_ai: bool = False          # AI-генерация писем через OpenAI
    system_prompt: str = ""       # если пусто — используется DEFAULT_SYSTEM_PROMPT
    message_prompt: str = ""      # если пусто — используется DEFAULT_MESSAGE_PROMPT
    # Письмо
    force_message: bool = False   # всегда прикреплять письмо
    template_name: str = ""       # имя шаблона из letter_templates (если не use_ai)
    # Тесты
    skip_tests: bool = True
    # Контроль
    max_responses: int = 100
    response_delay: str = "1-3"
    per_page: int = 20
    total_pages: int = 10
    send_email: bool = False


def _build_apply_args(body: ApplyFullRequest) -> list[str]:
    """Собирает список аргументов CLI для apply-vacancies из ApplyFullRequest."""
    args: list[str] = []

    if body.dry_run:
        args.append("--dry-run")
    if body.search:
        args += ["--search", body.search]
    if body.resume_id:
        args += ["--resume-id", body.resume_id]
    if body.experience:
        args += ["--experience", body.experience]
    if body.salary is not None:
        args += ["--salary", str(body.salary)]
    if body.only_with_salary:
        args.append("--only-with-salary")
    for s in body.schedule:
        args += ["--schedule", s]
    for e in body.employment:
        args += ["--employment", e]
    for a in body.area:
        args += ["--area", a]
    if body.excluded_filter:
        args += ["--excluded-filter", body.excluded_filter]
    if body.ai_filter:
        args += ["--ai-filter", body.ai_filter]
    if body.use_ai:
        args.append("--use-ai")
        # Используем улучшенные промпты если пользователь не задал свои
        system_prompt = body.system_prompt or DEFAULT_SYSTEM_PROMPT
        message_prompt = body.message_prompt or DEFAULT_MESSAGE_PROMPT
        args += ["--system-prompt", system_prompt]
        args += ["--message-prompt", message_prompt]
    elif body.template_name:
        # Не AI: используем шаблон из библиотеки
        letter_path = _resolve_letter_file(body.profile, body.template_name)
        if letter_path:
            args += ["--letter-file", str(letter_path)]
        # Если шаблон не найден — продолжаем без него (будет дефолтное)
    if body.force_message:
        args.append("--force-message")
    if body.skip_tests:
        args.append("--skip-tests")
    if body.send_email:
        args.append("--send-email")
    args += ["--max-responses", str(body.max_responses)]
    args += ["--response-delay", body.response_delay]
    args += ["--per-page", str(body.per_page)]
    args += ["--total-pages", str(body.total_pages)]
    return args


@app.post("/api/run/apply-vacancies-full")
def run_apply_vacancies_full(body: ApplyFullRequest):
    """Запустить автоотклики со всеми параметрами."""
    req = RunRequest(profile=body.profile)
    return _run_operation("apply-vacancies", req, extra=_build_apply_args(body))


# ---------------------------------------------------------------------------
# Routes: token status + agent-friendly operations
# ---------------------------------------------------------------------------

def _get_token_info(profile: str) -> dict:
    """Возвращает состояние токена без сетевых запросов."""
    cfg_path = _config_path(profile)
    if not cfg_path.exists():
        return {"status": "no_config", "profile": profile}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as ex:
        return {"status": "read_error", "error": str(ex), "profile": profile}

    token = cfg.get("token") or {}
    access_token = token.get("access_token")
    refresh_token_val = token.get("refresh_token")
    expires_at = token.get("access_expires_at")

    if not access_token:
        return {"status": "no_token", "profile": profile, "can_refresh": False}

    now = time.time()
    expires_in = None
    expired = False
    if expires_at:
        expires_in = int(expires_at - now)
        expired = expires_in <= 0

    return {
        "status": "expired" if expired else "ok",
        "profile": profile,
        "expired": expired,
        "expires_in_seconds": expires_in,
        "can_refresh": bool(refresh_token_val),
        "has_access_token": bool(access_token),
        "has_refresh_token": bool(refresh_token_val),
    }


def _refresh_token_sync(profile: str, timeout: int = 30) -> dict:
    """Запускает refresh-token CLI и возвращает результат."""
    cmd = _build_local_cli_cmd(["--profile-id", profile, "--no-auto-auth", "refresh-token"])
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["CONFIG_DIR"] = str(_config_root())
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            env=env,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "refresh-token timeout", "returncode": -1}
    except Exception as ex:
        return {"ok": False, "error": str(ex), "returncode": -1}


@app.get("/api/token-status")
def get_token_status(profile: str = Query("default")):
    """
    Быстрая проверка токена без сетевых запросов.
    Возвращает: status (ok/expired/no_token/no_config), expires_in_seconds, can_refresh.
    Использовать перед запуском операций чтобы знать нужен ли refresh или re-auth.
    """
    return _get_token_info(_validate_profile_name(profile))


@app.get("/api/agent/preflight")
def agent_preflight(profile: str = Query("default")):
    """
    Pre-flight проверка для AI агента: всё ли готово чтобы запускать операции?
    Возвращает: ready (bool), нужен ли refresh, нужен ли full re-auth.
    """
    profile = _validate_profile_name(profile)
    token = _get_token_info(profile)

    cfg_path = _config_path(profile)
    db = _db_path(profile)

    return {
        "ready": token["status"] == "ok",
        "profile": profile,
        "token_status": token["status"],       # ok / expired / no_token / no_config
        "token_expires_in": token.get("expires_in_seconds"),
        "can_refresh": token.get("can_refresh", False),
        "needs_reauth": token["status"] in ("no_token", "no_config"),
        "needs_refresh": token["status"] == "expired" and token.get("can_refresh", False),
        "config_exists": cfg_path.exists(),
        "db_exists": db.exists(),
        "action": (
            "run"           if token["status"] == "ok" else
            "refresh"       if (token["status"] == "expired" and token.get("can_refresh")) else
            "reauth"        # нужна ручная авторизация
        ),
    }


class AgentRunRequest(BaseModel):
    """
    Запрос операции от AI агента.
    Агент вызывает этот endpoint — панель сама:
    1. Проверит токен
    2. Обновит если истёк (и есть refresh_token)
    3. Запустит операцию
    4. Вернёт op_id для polling статуса

    Для apply-vacancies можно передать apply_params вместо голых args —
    тогда шаблоны писем и промпты разрешаются автоматически.
    """
    profile: str = "default"
    operation: str = "apply-vacancies"   # apply-vacancies | update-resumes | refresh-token
    auto_refresh: bool = True            # попробовать refresh-token если истёк
    args: list[str] = Field(default_factory=list)   # дополнительные аргументы CLI
    # Удобный способ запустить apply-vacancies без ручного составления args
    apply_params: ApplyFullRequest | None = None


@app.post("/api/agent/run")
def agent_run(body: AgentRunRequest):
    """
    Единая точка входа для AI агента.
    Агент не должен думать о токенах — всё обрабатывается автоматически.
    """
    profile = _validate_profile_name(body.profile)
    allowed_ops = {"apply-vacancies", "update-resumes", "refresh-token"}
    if body.operation not in allowed_ops:
        raise HTTPException(400, f"Операция должна быть одной из: {', '.join(sorted(allowed_ops))}")

    token = _get_token_info(profile)

    # Если токен истёк и можно обновить — обновляем синхронно перед запуском
    refreshed = False
    if body.auto_refresh and token["status"] == "expired" and token.get("can_refresh"):
        refresh_result = _refresh_token_sync(profile)
        if refresh_result["ok"]:
            refreshed = True
            token = _get_token_info(profile)  # перечитать после refresh
        else:
            raise HTTPException(
                502,
                f"Не удалось обновить токен: {refresh_result.get('stderr', '')[:300]}. "
                "Нужна ручная авторизация: запустите 'python -m hh_applicant_tool auth' в терминале."
            )

    # Если токена нет вообще — нужна ручная авторизация
    if token["status"] in ("no_token", "no_config"):
        raise HTTPException(
            401,
            "Нет токена авторизации. Нужна ручная авторизация: "
            "запустите 'python -m hh_applicant_tool auth' в терминале. "
            "Это единственное что нельзя автоматизировать — ввод SMS-кода."
        )

    if token["status"] == "expired":
        raise HTTPException(
            401,
            "Токен истёк и нет refresh_token. "
            "Нужна ручная авторизация: запустите 'python -m hh_applicant_tool auth' в терминале."
        )

    # Если переданы apply_params — разворачиваем в args автоматически
    extra_args = list(body.args)
    if body.operation == "apply-vacancies" and body.apply_params:
        params = body.apply_params
        params.profile = profile  # синхронизируем профиль
        extra_args = _build_apply_args(params) + extra_args

    req = RunRequest(profile=profile, extra_args=extra_args)
    result = _run_operation(body.operation, req)
    result["refreshed_token"] = refreshed
    result["token_status"] = token["status"]
    return result


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin.app:app", host=constants.ADMIN_LOCALHOST, port=constants.ADMIN_DEFAULT_PORT, reload=True)
