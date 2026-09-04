#!/usr/bin/env bash
# Install the same production schedule used by the container crontab.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="${PROJECT_DIR:-$PROJECT_ROOT}"

if ! command -v crontab >/dev/null 2>&1; then
    echo "crontab command not found" >&2
    exit 1
fi

mkdir -p "$PROJECT_DIR/logs"

APPLY_TIME="${APPLY_TIME:-09:10}"
REPLY_START_HOUR="${REPLY_START_HOUR:-9}"
REPLY_END_HOUR="${REPLY_END_HOUR:-21}"
BOOST_TIME="${BOOST_TIME:-09:00}"

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

read -r BOOST_MIN BOOST_HOUR < <(parse_time "$BOOST_TIME")
read -r APPLY_MIN APPLY_HOUR < <(parse_time "$APPLY_TIME")

if (( REPLY_START_HOUR < 0 || REPLY_START_HOUR > 23 || REPLY_END_HOUR < REPLY_START_HOUR || REPLY_END_HOUR > 23 )); then
    echo "Invalid reply hour range: $REPLY_START_HOUR-$REPLY_END_HOUR" >&2
    exit 2
fi

MARKER="# work-optimization autonomous HH jobs"
BOOST_JOB="$BOOST_MIN $BOOST_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/cron-job.sh boost >> $PROJECT_DIR/logs/cron.log 2>&1"
APPLY_JOB="$APPLY_MIN $APPLY_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/cron-job.sh apply >> $PROJECT_DIR/logs/cron.log 2>&1"
REPLY_JOB="25 $REPLY_START_HOUR-$REPLY_END_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/cron-job.sh reply >> $PROJECT_DIR/logs/cron.log 2>&1"

TMP_CRON="$(mktemp)"
cleanup() {
    rm -f "$TMP_CRON"
}
trap cleanup EXIT

crontab -l 2>/dev/null | awk -v marker="$MARKER" '
    $0 == marker {skip=3; next}
    skip > 0 {skip--; next}
    {print}
' > "$TMP_CRON" || true

{
    cat "$TMP_CRON"
    echo "$MARKER"
    echo "$BOOST_JOB"
    echo "$APPLY_JOB"
    echo "$REPLY_JOB"
} | crontab -

cat <<EOF
Cron installed:
  boost: $BOOST_TIME
  apply: $APPLY_TIME
  reply: hourly at :25, $REPLY_START_HOUR-$REPLY_END_HOUR

Actual writes are controlled by $PROJECT_DIR/.env:
  HH_AUTOMATION_MODE=off      # disabled
  HH_AUTOMATION_MODE=dry-run  # inspect only
  HH_AUTOMATION_MODE=live     # send/publish
EOF
