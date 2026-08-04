# HH Applicant Tool

Утилита для автоматизации работы с [HeadHunter](https://hh.ru): отклики на вакансии, обновление резюме, review переговоров и локальное хранение состояния.

## 🚀 Быстрый старт для агента

**1. Проверка состояния:**
```bash
hh-applicant-tool whoami
hh-applicant-tool list-resumes
```

**2. Ежедневный workflow:**
```bash
# Поднять резюме
hh-applicant-tool boost-resume

# Отклики с AI-письмами: dry-run по умолчанию, live только явно
./scripts/apply.sh
./scripts/apply.sh --live

# Ответы работодателям: dry-run по умолчанию, live только явно
./scripts/reply.sh
./scripts/reply.sh --live
```

**3. Локальные переменные для персонализации:**
```bash
HH_NAME=Максим
HH_TELEGRAM=@maxxwway
```

`apply.sh`, `reply.sh` и `daily.sh` автоматически подхватывают их из `.env` в корне.

**📚 Полная документация:** [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md)

---

## Что Это

Проект лучше воспринимать как `automation worker` для HH:

- основная работа идёт через HH API и web endpoints;
- локальное состояние хранится в `config.json`, `cookies.txt` и SQLite;
- регулярные задачи можно запускать по cron;
- AI и агентный контур здесь вспомогательные, а не основной источник действий.

Это не browser-RPA и не “полностью автономный агент, который сам всё решает”.

## Основные возможности

- автоотклики через `apply-vacancies`
- обновление резюме через `update-resumes`
- review переписок и ручные/AI-ответы работодателям
- AI-фильтрация вакансий и AI-генерация писем
- локальная SQLite база
- web admin panel
- поддержка нескольких профилей
- Docker для VPS

## Быстрый старт

### Локально

```bash
# Python 3.11+
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[playwright,pillow]'
# Required to run the FastAPI admin panel and its TestClient tests.
python -m pip install -r admin/requirements.txt
```

Poetry users should install the same admin dependency set explicitly:

```bash
poetry install --with dev
poetry run python -m pip install --no-cache-dir -r admin/requirements.txt
```

Run the regular offline test suite with `make dev && make test`. The configured
AI-provider check is intentionally opt-in because it contacts local Ollama and
the configured provider:

```bash
RUN_AI_INTEGRATION=1 poetry run pytest tests/test_ai_letter_integration.py -m integration -v
```

### Через Docker

```bash
git clone https://github.com/s3rgeym/hh-applicant-tool
cd hh-applicant-tool
docker compose build
docker compose up -d
docker compose logs -f
```

## Где Хранятся Данные

В директории профиля:

- `config.json` — токены и настройки
- `data` — SQLite база
- `cookies.txt` — cookies
- `log.txt` — логи

В Docker-сценарии по умолчанию это `config/` проекта, смонтированная в `/app/config`.

## Multi-Profile Run

Создай `.profiles` в корне проекта:

```text
default
account2
```

Запуск:

```bash
./scripts/all-profiles.sh reply
./scripts/all-profiles.sh apply
./scripts/all-profiles.sh daily
./scripts/all-profiles.sh apply --live
```

Без `.profiles` используется один основной профиль `default`. Логи пишутся в
`/tmp/hh-profiles/<profile>-<command>.log`.

## Авторизация

```bash
hh-applicant-tool authorize '<email-or-phone>'
hh-applicant-tool whoami
```

Для первого входа нужен человек: логин, код подтверждения, иногда капча. После этого токен и cookies сохраняются локально.

## Безопасный Workflow

Рекомендуемый контур:

1. `authorize`
2. `whoami`
3. `list-resumes`
4. `apply-vacancies --dry-run`
5. проверить выдачу
6. только потом live batch

Пример safe dry-run:

```bash
./scripts/apply.sh --dry-run
# или напрямую:
hh-applicant-tool apply-vacancies \
  --search "React frontend developer" \
  --ai \
  --system-prompt prompts/cover_letter_frontend.txt \
  --force-message \
  --skip-tests \
  --excluded-filter 'junior|стажировк|bitrix|web3|crypto|blockchain|open\s*space|опенспейс|хакатон|конкурс|тестов\w+ задан' \
  --dry-run
```

Live запуск только после просмотра dry-run:

```bash
./scripts/apply.sh
# или напрямую:
hh-applicant-tool apply-vacancies \
  --search "React frontend developer" \
  --ai \
  --system-prompt prompts/cover_letter_frontend.txt \
  --force-message \
  --skip-tests \
  --excluded-filter 'junior|стажировк|bitrix|web3|crypto|blockchain|open\s*space|опенспейс|хакатон|конкурс|тестов\w+ задан'
```

## Основные CLI Команды

```bash
hh-applicant-tool authorize
hh-applicant-tool whoami
hh-applicant-tool list-resumes
hh-applicant-tool update-resumes
hh-applicant-tool apply-vacancies --dry-run
hh-applicant-tool reply-employers --dry-run
hh-applicant-tool clear-negotiations --dry-run
hh-applicant-tool config -p
hh-applicant-tool log -f
```

## AI

AI не обязателен и подключается отдельными секциями в `config.json`. Он нужен, если хочешь:

- генерировать сопроводительные письма (`apply-vacancies --ai`);
- генерировать персональные ответы работодателям (`reply-employers --use-ai`, инбокс админки);
- фильтровать вакансии через AI;
- распознавать капчу через vision-модель.

Подойдёт любой OpenAI-совместимый endpoint: **OpenAI, OpenRouter, Ollama** и др.
CLI и админка используют один и тот же клиент и одни и те же секции конфига.

Минимальный пример (письма):

```json
{
  "openai_cover_letter": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini"
  }
}
```

**📖 Полное руководство:** [docs/LLM_SETUP.md](docs/LLM_SETUP.md) — все секции
(`openai_cover_letter`, `openai_vacancy_filter`, `openai_captcha`, `openai_reply`),
провайдеры, локальный Ollama и troubleshooting.

## Web Admin / Agent Layer

Start the admin panel locally on loopback only:

```bash
CONFIG_DIR="$PWD/config" python -m uvicorn admin.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. To require HTTP Basic authentication, set both
credentials before starting it:

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD='use-a-long-random-password' \
CONFIG_DIR="$PWD/config" python -m uvicorn admin.app:app --host 127.0.0.1 --port 8000
```

When both `ADMIN_USERNAME` and `ADMIN_PASSWORD` are set, every UI/API route
except `/health` requires Basic Auth. When neither is set, the admin remains
unauthenticated for deliberately local-only deployments. Do not bind an
unauthenticated admin to a public interface. A configuration with only one of
the two variables is rejected at startup/request time to prevent an accidental
open deployment.

Docker Compose does not publish port 8000 by default. If you deliberately
expose the panel, use a loopback-only mapping and pass both credentials via a
Compose override or service environment:

```yaml
services:
  hh_applicant_tool:
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
```

The container can listen on `0.0.0.0` internally; the host-side loopback
mapping is what prevents public exposure.

Полезные endpoint’ы:

- `GET /api/agent/preflight`
- `POST /api/agent/run`
- `GET /api/agent/digest`
- `GET /api/agent/review-negotiations`
- `GET /api/inbox`
- `GET /api/inbox/{neg_id}/messages`
- `POST /api/inbox/{neg_id}/reply`

Рекомендуемая модель:

- cron запускает детерминированные команды;
- агент читает digest и review endpoint’ы;
- агент помогает с выбором search-контуров, разбором логов и follow-up;
- агент не должен бесконтрольно слать всё подряд.

### Dry-run and live actions

`--dry-run` is a read/preview mode for application and reply workflows. It may
read HH data and generate a preview, but it must not send an HH write, employer
email, or chat message, and it must not persist application/reply state.

In the admin, live applications, resume updates, batch replies, rejection
clearing, and message sends require an explicit confirmation. Live applications
also require one selected resume; external employer email needs a separate
confirmation. `apply.sh`, `reply.sh`, and `daily.sh` are dry-run by default.
`daily.sh --full --live` performs a preview before the explicitly requested
live workflow. Resume publishing through `all-profiles.sh boost|update` also
requires `--live`; unattended publishing is disabled in the shipped schedules.

## Что Автоматизировать, А Что Нет

Хорошо автоматизировать:

- `refresh-token`
- `update-resumes`
- safe `apply-vacancies`

Осторожно автоматизировать:

- `reply-employers`
- follow-up после тишины
- новые search-контуры

Не рекомендуется:

- запускать новый поиск сразу в live;
- давать агенту полный live-control без рамок;
- полагаться только на AI-фильтр;
- использовать слишком широкий `search`.

## Документация

- [LLM Setup](docs/LLM_SETUP.md) — подключение AI
- [Agent Guide](docs/AGENT_GUIDE.md)
- [Autonomous Agent Workflow](docs/AUTONOMOUS_AGENT_WORKFLOW.md)
- [Scheduling](docs/SCHEDULING.md) — автозапуск по cron
- [Deployment](docs/DEPLOYMENT.md)
- [Docs Index](docs/README.md)
