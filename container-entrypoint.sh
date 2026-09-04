#!/bin/bash
set -euo pipefail

touch /var/log/cron.log
chown docker:docker /var/log/cron.log
mkdir -p /app/logs /app/config
chown -R docker:docker /app/logs /app/config

# Cron has a deliberately small environment. Persist only the non-secret
# scheduler knobs that scheduled jobs need, using shell-safe quoting.
RUNTIME_ENV=/tmp/hh-runtime.env
{
    printf 'export HH_AUTOMATION_MODE=%q\n' "${HH_AUTOMATION_MODE:-off}"
    printf 'export CONFIG_DIR=%q\n' "${CONFIG_DIR:-/app/config}"
    printf 'export TZ=%q\n' "${TZ:-Europe/Moscow}"
    printf 'export APPLY_LIMIT=%q\n' "${APPLY_LIMIT:-100}"
    printf 'export APPLY_PER_PAGE=%q\n' "${APPLY_PER_PAGE:-50}"
    printf 'export APPLY_PAGES=%q\n' "${APPLY_PAGES:-20}"
    printf 'export REPLY_CHATS=%q\n' "${REPLY_CHATS:-100}"
} > "$RUNTIME_ENV"
chown docker:docker "$RUNTIME_ENV"
chmod 0600 "$RUNTIME_ENV"

# Cron runs the deterministic workers; the admin panel remains the foreground
# process so container health and lifecycle are easy to observe.
cron

exec su -s /bin/bash docker -c "cd /app && exec python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000"
