#!/bin/bash
set -e

touch /var/log/cron.log

# Запускаем cron в фоне, а admin panel оставляем foreground-процессом контейнера.
cron

exec su - docker -c "cd /app && python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000"
