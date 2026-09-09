#!/usr/bin/env bash
# Install only the daily ops snapshot publisher on the runtime host.
# This intentionally does NOT install HH apply/reply/boost jobs, so it is safe
# to use next to the Docker container that already owns the HH scheduler.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$PROJECT_ROOT}"
OPS_PUBLISH_TIME="${OPS_PUBLISH_TIME:-02:30}"
OPS_TIMEZONE="${OPS_TIMEZONE:-${TZ:-Europe/Moscow}}"
OPS_PUBLISH_BRANCH="${OPS_PUBLISH_BRANCH:-main}"
OPS_PYTHON="${OPS_PYTHON:-python3}"

if ! command -v crontab >/dev/null 2>&1; then
    echo "crontab command not found" >&2
    exit 1
fi
if ! command -v git >/dev/null 2>&1; then
    echo "git command not found" >&2
    exit 1
fi
if ! command -v "$OPS_PYTHON" >/dev/null 2>&1; then
    echo "Python not found: $OPS_PYTHON" >&2
    exit 1
fi

parse_time() {
    local value="$1"
    local hour minute
    IFS=: read -r hour minute <<< "$value"
    if [[ ! "$hour" =~ ^([01]?[0-9]|2[0-3])$ || ! "$minute" =~ ^[0-5]?[0-9]$ ]]; then
        echo "Invalid time: $value (expected HH:MM)" >&2
        exit 2
    fi
    printf '%d %d\n' "$((10#$minute))" "$((10#$hour))"
}

read -r PUBLISH_MIN PUBLISH_HOUR < <(parse_time "$OPS_PUBLISH_TIME")
mkdir -p "$PROJECT_DIR/logs"

MARKER="# work-optimization ops publisher"
PROJECT_Q="$(printf '%q' "$PROJECT_DIR")"
TIMEZONE_Q="$(printf '%q' "$OPS_TIMEZONE")"
BRANCH_Q="$(printf '%q' "$OPS_PUBLISH_BRANCH")"
PYTHON_Q="$(printf '%q' "$OPS_PYTHON")"
PUBLISHER_Q="$(printf '%q' "$PROJECT_DIR/scripts/ops/daily_publish.sh")"
LOG_Q="$(printf '%q' "$PROJECT_DIR/logs/ops-publish.log")"
JOB="$PUBLISH_MIN $PUBLISH_HOUR * * * cd $PROJECT_Q && OPS_TIMEZONE=$TIMEZONE_Q OPS_PUBLISH_BRANCH=$BRANCH_Q OPS_PYTHON=$PYTHON_Q /bin/bash $PUBLISHER_Q yesterday >> $LOG_Q 2>&1"

TMP_CRON="$(mktemp)"
cleanup() {
    rm -f "$TMP_CRON"
}
trap cleanup EXIT

crontab -l 2>/dev/null | awk -v marker="$MARKER" '
    $0 == marker {skip=1; next}
    skip > 0 {skip--; next}
    {print}
' > "$TMP_CRON" || true

{
    cat "$TMP_CRON"
    echo "$MARKER"
    echo "$JOB"
} | crontab -

cat <<EOF
Ops publisher cron installed:
  time:       $OPS_PUBLISH_TIME
  timezone:   $OPS_TIMEZONE
  branch:     $OPS_PUBLISH_BRANCH
  repository: $PROJECT_DIR

It installs ONLY the ops publisher and does not schedule HH apply/reply/boost.
The runtime host must be able to run `git pull` and `git push` non-interactively.
Publisher log: $PROJECT_DIR/logs/ops-publish.log
EOF
