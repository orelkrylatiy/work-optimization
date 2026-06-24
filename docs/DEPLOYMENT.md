# Deployment Guide

## Рекомендуемый Способ

Для VPS рекомендуется `Docker Compose`.

Почему:

- проект уже содержит `Dockerfile` и `docker-compose.yml`
- SQLite, токены и логи лежат в одной persistent директории
- cron внутри контейнера уже предусмотрен
- operational контур проще поддерживать

## Базовый Сценарий

```bash
git clone https://github.com/s3rgeym/hh-applicant-tool
cd hh-applicant-tool
docker compose build
docker compose up -d
docker compose logs -f
```

## Что Проверить После Старта

```bash
docker compose ps
curl http://localhost:8000/health
docker exec -it hh_applicant_tool ls -la /app/config
```

## Где Хранятся Данные

По умолчанию:

- `/app/config/config.json`
- `/app/config/data`
- `/app/config/cookies.txt`
- `/app/config/log.txt`

На хосте это соответствует `config/` проекта.

## Recommended Production Model

Автоматизировать по расписанию стоит:

- `refresh-token`
- `update-resumes`
- safe `apply-vacancies`

Остальное лучше держать под review:

- `reply-employers`
- follow-up
- новые search-контуры

## Без Docker

Можно запустить и без Docker, но тогда придётся отдельно поддерживать:

- Python окружение
- scheduler
- сервис
- права на файлы профиля

Для большинства VPS случаев это менее удобно, чем Docker.
