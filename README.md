# Work Optimization / HH Applicant Tool

Automation worker для работы соискателя на HH.ru: поиск и фильтрация вакансий, ограниченные batch-отклики, AI-сопроводительные, безопасные автоответы работодателям, multi-profile, локальное состояние и cron/Docker deployment.

Проект построен как детерминированный worker, а не как свободно действующий LLM-агент:

```text
cron / manual command
        ↓
scripts/*.sh
        ↓
hh-applicant-tool CLI
        ↓
HH API + локальное состояние
        ↓
LLM только там, где нужен текст
```

Для ежедневного цикла MCP не требуется. Скрипты уже дают стабильную command surface для cron, CI и внешнего агента.

## Что Автоматизировано

- отклики на вакансии через `apply-vacancies`;
- AI-сопроводительные письма;
- пропуск вакансий с тестовыми заданиями в autonomous path;
- лимит именно по успешным откликам, а не по числу просмотренных вакансий;
- автоответы через актуальный `/common/chats` API HH;
- повторная проверка чата перед отправкой ответа;
- idempotency key для защиты от дублей при retry;
- multi-profile с bounded concurrency и per-profile locks;
- ежедневный cron batch откликов и почасовые проверки чатов;
- Docker + web admin panel;
- SQLite/локальное состояние профилей;
- blocking CI для нового automation layer, тесты, Ruff, formatter, basedpyright, ShellCheck и Docker build.

## Безопасность Автономного Режима

Все scheduled jobs выключены после установки:

```dotenv
HH_AUTOMATION_MODE=off
```

Режимы:

```text
off      cron ничего не делает
dry-run  читает данные и строит preview без внешних действий
live     разрешает реальные отклики, ответы и boost
```

Не переключай в `live`, пока не прошли AI probe и ручные dry-run.

## Быстрый Старт

Требуется Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[playwright,pillow]'
pip install -r admin/requirements.txt
cp .env.example .env
```

Для browser-авторизации:

```bash
python -m playwright install chromium
```

Проверка CLI:

```bash
hh-applicant-tool --help
hh-applicant-tool whoami
hh-applicant-tool list-resumes
```

Если аккаунт ещё не авторизован:

```bash
hh-applicant-tool --profile-id default authorize '<phone-or-email>'
hh-applicant-tool --profile-id default whoami
```

Первичная авторизация может потребовать человека: код подтверждения и иногда капчу. После этого токены/cookies сохраняются в профиле.

## Профили И Данные

В директории каждого профиля находятся:

- `config.json` — токены и настройки;
- `data` — SQLite;
- `cookies.txt` — web cookies;
- `log.txt` — CLI log.

Для нескольких аккаунтов создай `.profiles`:

```text
default
account2
```

Проверка:

```bash
hh-applicant-tool --profile-id default whoami
hh-applicant-tool --profile-id account2 whoami
```

Batch по всем профилям:

```bash
./scripts/all-profiles.sh apply --dry-run
./scripts/all-profiles.sh reply --dry-run
```

Параллелизм ограничен:

```dotenv
HH_PROFILE_PARALLELISM=2
```

Это защищает HH и LLM provider от резкого умножения RPS при нескольких аккаунтах.

## AI Конфигурация

Для live-откликов нужен `openai_cover_letter`. Для ответов используется:

```text
openai_reply -> openai_cover_letter -> STOP
```

Пример `config.json` профиля:

```json
{
  "openai_cover_letter": {
    "api_key": "...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.35,
    "timeout": 45
  },
  "openai_reply": {
    "api_key": "...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.35,
    "timeout": 45
  }
}
```

Подойдёт любой OpenAI-compatible provider, включая OpenRouter и OpenAI-compatible режим Ollama.

Static preflight:

```bash
python scripts/check_ai.py --purpose cover-letter --profile default
python scripts/check_ai.py --purpose reply --profile default
```

Реальный model probe:

```bash
python scripts/check_ai.py --purpose cover-letter --profile default --probe
python scripts/check_ai.py --purpose reply --profile default --probe
```

Подробности: [docs/LLM_SETUP.md](docs/LLM_SETUP.md).

## Отклики

Preview:

```bash
./scripts/apply.sh \
  --profile default \
  --search 'React TypeScript developer' \
  --limit 20 \
  --pages 5 \
  --dry-run
```

Live:

```bash
./scripts/apply.sh \
  --profile default \
  --search 'React TypeScript developer' \
  --limit 20 \
  --pages 5 \
  --live
```

Ключевое различие:

- `--limit` — максимум **успешных** откликов;
- `--pages × --per-page` — максимальная глубина сканирования.

Поэтому worker может пройти значительно больше 20 вакансий, чтобы реально набрать 20 подходящих откликов после фильтрации и пропуска уже обработанных вакансий.

По умолчанию autonomous path использует `--skip-tests`: бот не должен угадывать ответы на тестовые задания.

Весь batch дополнительно ограничен `APPLY_RUN_TIMEOUT` (default 3600 секунд), чтобы зависший legacy HTML-request не удержал scheduled lock навсегда.

## Автоответы В Чатах

Preview без отправки и без вызова LLM:

```bash
./scripts/reply.sh --profile default --chats 20 --dry-run
```

Live:

```bash
./scripts/reply.sh --profile default --chats 20 --live
```

Worker использует current common-chat flow:

```text
GET /common/chats
GET /common/chats/{chat_id}/messages
LLM generation
GET /common/chats/{chat_id}/messages   # revalidate
POST /common/chats/{chat_id}/messages  # idempotent
```

Ответ отправляется только когда:

- чат относится к negotiation;
- чат не заблокирован;
- HH разрешает запись;
- последнее сообщение от работодателя;
- за время генерации последнее сообщение не изменилось.

Если человек ответил вручную или работодатель прислал ещё одно сообщение, старый AI-ответ не отправляется.

Каждый employer turn получает deterministic UUID `idempotency_key`. Retry использует тот же ключ; дополнительно worker перечитывает чат после сомнительного POST, чтобы не отправить дубль при потерянном HTTP-ответе.

## Humanizer

Шаблоны:

- `prompts/cover_letter_frontend.txt`;
- `prompts/reply_employer.txt`.

Они запрещают длинные тире, placeholder'ы, канцелярит, типовые AI-клише и слишком гладкий рекламный стиль. Для autonomous replies действует ещё runtime validator: плохой ответ отклоняется, модель получает одну попытку исправления, после повторной неудачи сообщение пропускается.

Telegram не дописывается программно в каждый ответ. Он используется только когда это уместно по истории диалога.

## Расписание

Container `crontab` по умолчанию:

| Время | Действие |
|---|---|
| 09:00 | boost резюме, только `live` |
| 09:10 | один application batch |
| каждый час 09:25–21:25 | один bounded pass по чатам |

Время берётся из timezone контейнера/сервера (`TZ`).

Пример `.env`:

```dotenv
TZ=Europe/Moscow
HH_AUTOMATION_MODE=dry-run
SEARCH_QUERY=Frontend разработчик
APPLY_LIMIT=100
APPLY_PER_PAGE=50
APPLY_PAGES=20
APPLY_RUN_TIMEOUT=3600
REPLY_CHATS=100
HH_PROFILE_PARALLELISM=2
```

После проверки:

```dotenv
HH_AUTOMATION_MODE=live
```

Для установки аналогичного cron вне Docker:

```bash
./scripts/setup-cron.sh
```

## Docker

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

Admin panel публикуется только на localhost:

```text
127.0.0.1:8000
```

Если нужен внешний доступ, лучше проксировать через HTTPS и обязательно настроить:

```dotenv
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
```

## Ручной One-shot Workflow

```bash
# Полный preview
./scripts/daily.sh --profile default --dry-run

# Один live pass: apply + reply
./scripts/daily.sh --profile default --live

# Только отклики
./scripts/daily.sh --profile default --apply-only --dry-run

# Только чаты
./scripts/daily.sh --profile default --reply-only --dry-run

# Boost не выполняется автоматически этим one-shot без отдельного подтверждения
./scripts/daily.sh --profile default --live --with-boost
```

Scheduled production path использует не `daily.sh`, а отдельные `cron-job.sh apply/reply/boost`, чтобы падение одного типа работы не смешивалось с другим.

## Проверки Разработки

Blocking CI проверяет новый automation layer и весь test suite. Локально:

```bash
pytest tests/
ruff check src/hh_applicant_tool/automation scripts/reply_iterative_ai.py scripts/check_ai.py
ruff format --check src/hh_applicant_tool/automation scripts/reply_iterative_ai.py scripts/check_ai.py
basedpyright src/hh_applicant_tool/automation
shellcheck scripts/apply.sh scripts/reply.sh scripts/cron-job.sh scripts/daily.sh scripts/all-profiles.sh scripts/setup-cron.sh
```

Полный upstream код содержит legacy lint/type debt; CI отдельно показывает его как report-only, не маскируя ошибки в новом critical automation path.

## Что Не Делать Автономно

- не включать решение vacancy tests;
- не менять search/filters сразу в live без preview;
- не запускать одновременно несколько scheduler'ов для одной установки;
- не копировать token/cookies между профилями;
- не обходить `HH_AUTOMATION_MODE` и locks внешним параллельным cron;
- не выставлять admin panel в интернет без auth/TLS.

## Документация

- [docs/AUTONOMOUS_AGENT_WORKFLOW.md](docs/AUTONOMOUS_AGENT_WORKFLOW.md) — production automation и safety model;
- [docs/LLM_SETUP.md](docs/LLM_SETUP.md) — LLM config/fallbacks/probe;
- [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md) — CLI и agent-oriented use cases;
- [docs/SCHEDULING.md](docs/SCHEDULING.md) — дополнительные варианты запуска;
- [docs/development/TESTING.md](docs/development/TESTING.md) — тестирование;
- [docs/PRODUCTION_REVIEW_2026-09-04.md](docs/PRODUCTION_REVIEW_2026-09-04.md) — результаты hardening review.
