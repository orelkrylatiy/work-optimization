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

# Отклики с AI-письмами (dry-run → live)
./scripts/apply.sh --dry-run
./scripts/apply.sh

# Ответы работодателям (итеративно, AI, с учётом кто первый написал)
./scripts/reply.sh --dry-run
./scripts/reply.sh
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
python -m venv venv
. venv/bin/activate
pip install '.[playwright]'
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
./scripts/all-profiles.sh reply --dry-run
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

Админка запускается на `http://127.0.0.1:8000`.

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
