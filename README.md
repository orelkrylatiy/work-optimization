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
pip install '.[playwright]'
cp .env.example .env 2>/dev/null || touch .env
```

Проверка установки:

```bash
hh-applicant-tool --help
hh-applicant-tool whoami
hh-applicant-tool list-resumes
```

Рабочие скрипты используют `.venv` в корне проекта и автоматически читают
`.env`. Минимальная персонализация:

```dotenv
HH_NAME=Максим
HH_TELEGRAM=@username
```

Также в `config/config.json` должен быть настроен AI-провайдер для
сопроводительных писем и автоответов. Проверить конфигурацию можно так:

```bash
.venv/bin/python scripts/check_ai.py
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

## Несколько HH-аккаунтов

Каждый аккаунт хранится в отдельном профиле внутри общей директории
`config/`. Имя профиля передаётся глобальным флагом `--profile-id` или через
`HH_PROFILE_ID`.

Авторизация первого аккаунта:

```bash
.venv/bin/hh-applicant-tool --profile-id default authorize '+7XXXXXXXXXX'
.venv/bin/hh-applicant-tool --profile-id default whoami
```

Добавление следующего аккаунта:

```bash
.venv/bin/hh-applicant-tool --profile-id account2 authorize '+7YYYYYYYYYY'
.venv/bin/hh-applicant-tool --profile-id account2 whoami
```

После успешной авторизации создай `.profiles` в корне проекта — по одному
профилю на строку:

```text
default
account2
# комментарии и пустые строки разрешены
```

Проверка каждого аккаунта отдельно:

```bash
.venv/bin/hh-applicant-tool --profile-id default list-resumes
.venv/bin/hh-applicant-tool --profile-id account2 list-resumes
./scripts/apply.sh --profile account2 --dry-run
./scripts/reply.sh --profile account2 --dry-run
./scripts/all-profiles.sh reply
./scripts/all-profiles.sh apply
./scripts/all-profiles.sh daily
./scripts/all-profiles.sh apply --live
```

Параллельный запуск по всем профилям из `.profiles`:

```bash
./scripts/all-profiles.sh boost
./scripts/all-profiles.sh apply --dry-run
./scripts/all-profiles.sh apply
./scripts/all-profiles.sh reply --dry-run
./scripts/all-profiles.sh reply
./scripts/all-profiles.sh cleanup
./scripts/all-profiles.sh daily --dry-run
./scripts/all-profiles.sh daily
```

`all-profiles.sh` запускает аккаунты параллельно, но не запускает две операции
одновременно для одного профиля. Для этого используются lock-директории в
`/tmp/hh-profile-locks`. Без `.profiles` работает только профиль `default`.
Логи отдельных запусков находятся в
`/tmp/hh-profiles/<profile>-<command>.log`.

Чтобы временно задать список без файла:

```bash
PROFILES="default account2" ./scripts/all-profiles.sh reply --dry-run
```

Не копируй токены и cookies между профилями: у каждого аккаунта должна быть
своя авторизация и своё состояние.

## Автоотклики

Безопасная последовательность для одного профиля:

```bash
./scripts/apply.sh --profile default --dry-run
./scripts/apply.sh --profile default
```

Для всех аккаунтов:

```bash
./scripts/all-profiles.sh apply --dry-run
./scripts/all-profiles.sh apply
```

По умолчанию `apply.sh` проходит несколько frontend-запросов, использует
AI-сопроводительное письмо, пропускает вакансии с тестовыми заданиями и
исключает нежелательные направления регулярным выражением. Полезные параметры:

```bash
./scripts/apply.sh \
  --profile default \
  --search "React TypeScript developer" \
  --limit 50 \
  --dry-run
```

- `--search` заменяет набор стандартных запросов одним указанным запросом;
- `--limit` задаёт размер обрабатываемой выдачи на запрос, а не гарантированное
  число отправленных откликов;
- `--excluded-filter` переопределяет regex исключений;
- без `--dry-run` отклики отправляются реально.

## Автоответы работодателям

`reply.sh` обрабатывает входящие чаты итерациями, генерирует ответ через AI и
учитывает историю переписки. Контактные данные подставляются в промпт из
`HH_NAME` и `HH_TELEGRAM`.

Сначала всегда запускай проверку без отправки:

```bash
./scripts/reply.sh --profile default --dry-run
./scripts/reply.sh --profile default --iterations 3 --chats 20 --dry-run
```

Live-запуск:

```bash
./scripts/reply.sh --profile default
./scripts/all-profiles.sh reply
```

Параметры:

- `--iterations N` — максимум проходов по входящим чатам;
- `--chats N` — максимум чатов за один проход;
- `--telegram @username` — контакт для текущего запуска;
- `--dry-run` — сформировать решения, но ничего не отправлять.

Состояние обработанных диалогов хранится отдельно по профилям в
`config/reply-state/<profile>.json`. Перед ответами `daily.sh` запускает
`cleanup.sh`, который скрывает отказы из активных переговоров; он не добавляет
работодателей в blacklist.

## Полный ежедневный цикл

```bash
# Один аккаунт
./scripts/daily.sh --profile default --dry-run
./scripts/daily.sh --profile default

# Все аккаунты
./scripts/all-profiles.sh daily --dry-run
./scripts/all-profiles.sh daily
```

Полный цикл выполняет четыре шага:

1. поднимает резюме;
2. отправляет отклики;
3. убирает отказы из активных чатов;
4. отвечает работодателям.

Дополнительные режимы: `--apply-only`, `--reply-only`, `--full` (сначала
dry-run откликов, затем live).

## Автозапуск: PM2 и cron

На сервере используется PM2 с расписанием из `ecosystem.config.cjs`. Все часы
указаны в UTC, только по будням:

| Задача | UTC | Команда |
|---|---:|---|
| Подъём резюме | 05:00 | `all-profiles.sh boost` |
| Первая волна откликов | 05:15 | `all-profiles.sh apply` |
| Проверка и ответы | каждый час 06:00–13:00 | `all-profiles.sh reply` |
| Очистка отказов | 14:15 | `all-profiles.sh cleanup` |

Установка или обновление расписания:

```bash
mkdir -p logs
pm2 startOrReload ecosystem.config.cjs
pm2 save
pm2 list
```

PM2 показывает cron-задачи как `stopped` между запусками — это нормально:
`autorestart` отключён, процесс стартует только по расписанию. Первый
регистрационный запуск также безопасен: `scripts/pm2-job.sh` проверяет текущий
UTC-слот и вне расписания ничего не отправляет.

Полезная диагностика:

```bash
pm2 list
pm2 describe hh-reply-hourly
pm2 logs hh-apply --lines 100
tail -n 100 logs/hh-reply-hourly.log
tail -n 100 /tmp/hh-profiles/default-reply.log
```

Все cron-задачи используют общий `flock` в `config/pm2-hh.lock`: если
предыдущая HH-операция ещё работает, новый слот пропускается, чтобы процессы
не конфликтовали за одну сессию.

Если PM2 не нужен, эквивалентный системный cron можно задать вручную:

```cron
0 5 * * 1-5 cd /path/to/work-optimization && ./scripts/all-profiles.sh boost
15 5 * * 1-5 cd /path/to/work-optimization && ./scripts/all-profiles.sh apply
0 6-13 * * 1-5 cd /path/to/work-optimization && ./scripts/all-profiles.sh reply
15 14 * * 1-5 cd /path/to/work-optimization && ./scripts/all-profiles.sh cleanup
```

Не включай одновременно PM2 и системный cron с одинаковым расписанием — это
создаст дублирующиеся попытки запуска.

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
