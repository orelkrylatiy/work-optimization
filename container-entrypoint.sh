#!/bin/bash
set -euo pipefail

touch /var/log/cron.log
chown docker:docker /var/log/cron.log
mkdir -p /app/logs /app/config
chown -R docker:docker /app/logs /app/config

# Cron runs the deterministic workers; the admin panel remains the foreground
# process so container health and lifecycle are easy to observe.
cron

exec su -s /bin/bash docker -c "cd /app && exec python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000"
