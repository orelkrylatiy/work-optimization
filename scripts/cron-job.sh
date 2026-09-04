#!/usr/bin/env bash
# Deterministic entrypoint for scheduled HH automation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi
if [[ -f /tmp/hh-runtime.env ]]; then
    # Docker/compose environment intentionally overrides values from .env.
    # shellcheck disable=SC1091
    source /tmp/hh-runtime.env
fi

MODE="${HH_AUTOMATION_MODE:-off}"
JOB="${1:-}"

case "$MODE" in
    off)
        echo "$(date -Is) automation disabled (HH_AUTOMATION_MODE=off)"
        exit 0
        ;;
    dry-run)
        MODE_FLAG="--dry-run"
        ;;
    live)
        MODE_FLAG="--live"
        ;;
    *)
        echo "Invalid HH_AUTOMATION_MODE='$MODE' (expected off, dry-run, live)" >&2
        exit 2
        ;;
esac

case "$JOB" in
    apply|reply|boost) ;;
    *)
        echo "Usage: $0 apply|reply|boost" >&2
        exit 2
        ;;
esac

LOCK_DIR="${HH_AUTOMATION_LOCK_DIR:-/tmp/hh-autonomy.lock}"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$(date -Is) another HH automation job is active; skipping $JOB"
    exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

echo "$(date -Is) starting job=$JOB mode=$MODE"

case "$JOB" in
    apply)
        "$SCRIPT_DIR/all-profiles.sh" apply "$MODE_FLAG" \
            --limit "${APPLY_LIMIT:-100}" \
            --pages "${APPLY_PAGES:-20}" \
            --per-page "${APPLY_PER_PAGE:-50}"
        ;;
    reply)
        "$SCRIPT_DIR/all-profiles.sh" reply "$MODE_FLAG" \
            --chats "${REPLY_CHATS:-100}"
        ;;
    boost)
        if [[ "$MODE" != "live" ]]; then
            echo "$(date -Is) boost skipped outside live mode"
            exit 0
        fi
        "$SCRIPT_DIR/all-profiles.sh" boost --live
        ;;
esac
