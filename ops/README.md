# Daily ops snapshots

`ops/` хранит небольшие агрегированные runtime-снапшоты HH automation, которые удобно разбирать через GitHub/ChatGPT после сбоев или при анализе воронки.

Архитектура повторяет рабочую схему из `profi-agent`, но метрики адаптированы под этот репозиторий:

```text
raw runtime
├── config/<profile>/log.txt*      Python RotatingFileHandler
├── logs/profiles/*.log            apply/reply/boost wrapper history
├── logs/cron.log                  scheduler output
└── config/<profile>/data          SQLite
            │
            ▼
scripts/ops/daily_report.py
            │
            ├── ops/daily/YYYY-MM-DD.json
            └── ops/latest.json
```

В Git попадает **только агрегированный JSON**. `logs/`, profile config, cookies и SQLite остаются локальными.

## Почему не коммитим raw logs

Даже если большая часть вакансий публична, runtime-лог может содержать данные, которые публичными не являются: текст переписки с работодателем, имя/контакты кандидата или рекрутера, URL с техническими идентификаторами, HTTP diagnostics, proxy/config values и traceback context.

Поэтому collector работает по allow-list и сохраняет только счётчики/статусы. Это ещё и делает отчёты гораздо удобнее для сравнения по дням.

Privacy contract в каждом JSON явно фиксирует, что не включены:

- raw log lines;
- chat text;
- vacancy/employer names;
- URLs и ids;
- cookies, tokens, API keys и другие secrets.

## Что собирается

### Runs

`scripts/all-profiles.sh` пишет persistent wrapper logs в:

```text
logs/profiles/<profile>-<command>.log
```

Каждый запуск окружён machine-readable markers:

```text
[2026-09-09 09:10:00] HH_RUN_START profile=account1 command=apply mode=live
...
[2026-09-09 09:13:42] HH_RUN_END profile=account1 command=apply mode=live status=0
```

По ним snapshot считает для каждого профиля и command:

- сколько запусков началось;
- сколько завершилось ошибкой;
- сколько было пропущено из-за занятого per-profile lock;
- live/dry-run/utility mode.

### Apply

Из bounded apply run считаются:

- реальные успешные отклики;
- `dry-run` planned responses;
- число cover-letter AI errors из итогового сообщения операции;
- captcha required / captcha failed;
- достижение application quota.

Ни название вакансии, ни URL в snapshot не копируются.

### Reply

`reply_iterative_ai.py` уже печатает итоговый JSON run-а. Collector забирает только числовые поля:

- `candidates`;
- `planned`;
- `sent`;
- `stale`;
- `skipped`;
- `errors`;
- `fallback`.

Текст диалога и сгенерированный ответ не сохраняются.

### Technical events

Из логов считаются заранее разрешённые сигнатуры:

- auth errors;
- LLM/config errors;
- captcha required/failed;
- rejected reply by humanizer;
- reply send failures;
- HH CLI/JSON errors;
- rate limits;
- timeouts;
- `database is locked`;
- traceback occurrences;
- busy profile skips;
- common network errors.

Это **occurrence counters**, а не дедуплицированные incidents: одна проблема может проявиться в нескольких слоях логирования.

### SQLite

Для каждого найденного profile DB collector открывает SQLite только в read-only mode и публикует row counts для allow-listed tables:

- `vacancies`;
- `negotiations`;
- `skipped_vacancies`;
- `employers`;
- `resumes`.

Содержимое строк не выгружается.

## Ручной запуск

Из корня репозитория:

```bash
python3 scripts/ops/daily_report.py --date today
python3 scripts/ops/daily_report.py --date yesterday
python3 scripts/ops/daily_report.py --date 2026-09-09
```

По умолчанию timezone берётся из `OPS_TIMEZONE`, затем `TZ`, затем `Europe/Moscow`.

Можно указать явно:

```bash
python3 scripts/ops/daily_report.py --date yesterday --timezone Europe/Moscow
```

Результат:

```text
ops/daily/YYYY-MM-DD.json
ops/latest.json
```

## Автоматический collector внутри Docker

Контейнерный `crontab` в `02:20` каждый день запускает:

```bash
python3 scripts/ops/daily_report.py --date yesterday
```

Он выполняется независимо от `HH_AUTOMATION_MODE`, потому что не вызывает HH или LLM и ничего не отправляет наружу.

Raw scheduler output хранится в:

```text
logs/ops-daily.log
```

## Автоматически с обычными git-коммитами

В репозитории есть `githooks/pre-commit`. Активировать один раз в конкретном clone:

```bash
git config core.hooksPath githooks
```

После этого перед обычным commit hook:

1. запускает существующие quality hooks из `.pre-commit-config.yaml`, если `pre-commit` доступен;
2. строит snapshot за `today`;
3. делает `git add ops/latest.json ops/daily`;
4. snapshot попадает в тот же commit.

Ошибка snapshot collector **не блокирует commit**. Ошибка lint/format pre-commit checks, наоборот, остаётся blocking.

Merge commits не снапшотятся.

## Автоматический commit + push на runtime host/VPS

Если нужен ежедневный Git history даже когда код никто не коммитит, на чистом clone с настроенными git credentials запускай:

```bash
bash scripts/ops/daily_publish.sh yesterday
```

Publisher:

1. требует ожидаемую branch (`main` по умолчанию);
2. отказывается работать при tracked/staged изменениях вне `ops/`;
3. делает `git pull --ff-only`;
4. строит snapshot;
5. коммитит только `ops/daily/YYYY-MM-DD.json` и `ops/latest.json`;
6. делает `git push`.

Переменные:

```text
OPS_TIMEZONE=Europe/Moscow
OPS_PUBLISH_BRANCH=main
OPS_PYTHON=python3
```

Пример host cron в `02:30`, после container collector:

```cron
30 2 * * * cd /path/to/work-optimization && OPS_TIMEZONE=Europe/Moscow bash scripts/ops/daily_publish.sh yesterday >> logs/ops-publish.log 2>&1
```

Этот publisher нужно запускать **там, где доступны runtime `logs/`/`config/` и git credentials**. GitHub Actions сам по себе production logs не видит, поэтому scheduled CI не заменяет runtime publisher.

## Анализ через ChatGPT

После публикации можно просить, например:

```text
Посмотри ops/latest.json в work-optimization. Разбери, почему упали отклики или ответы: какие профили/джобы падали, были ли LLM errors, rate limits, captcha, stale replies и fallback.
```

Или сравнить несколько файлов `ops/daily/*.json`, чтобы увидеть, когда именно началась деградация.
