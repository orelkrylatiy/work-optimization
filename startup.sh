#!/bin/bash
set -euo pipefail

mkdir -p /app/logs /app/config

echo "[$(date -Is)] work-optimization startup"
echo "[$(date -Is)] scheduled HH actions are controlled by HH_AUTOMATION_MODE and cron"

# Do not refresh tokens, publish resumes, apply, or reply on container restart.
# The API client refreshes credentials on authenticated requests, and external
# writes belong to the explicit scheduled jobs. This avoids duplicate batches
# after an unexpected container restart.
