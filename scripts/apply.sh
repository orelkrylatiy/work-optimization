#!/usr/bin/env bash
# apply.sh — bounded HH vacancy applications with AI cover letters.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$PROJECT_ROOT/.env"
    set +a
fi

SEARCH_QUERY="${SEARCH_QUERY:-Frontend разработчик}"
MAX_RESPONSES="${APPLY_LIMIT:-${LIMIT:-100}}"
PER_PAGE="${APPLY_PER_PAGE:-50}"
TOTAL_PAGES="${APPLY_PAGES:-20}"
SYSTEM_PROMPT="${SYSTEM_PROMPT:-$PROJECT_ROOT/prompts/cover_letter_frontend.txt}"
EXCLUDED_FILTER="${EXCLUDED_FILTER:-junior|стажир|bitrix|web3|crypto|blockchain|golang|python|java|1c|продакт|менеджер|pm|дизайнер|qa|тестировщик|devops|аналитик|data|sales|продаж|рекрутер|hr|без опыта|trainee|казань|спб|минск|open\s*space|опенспейс}"
RUN_MODE="dry-run"
RUN_MODE_EXPLICIT=""
PROFILE_ID="${HH_PROFILE_ID:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            [[ "$RUN_MODE_EXPLICIT" == "live" ]] && { echo "Cannot combine --dry-run and --live" >&2; exit 1; }
            RUN_MODE="dry-run"
            RUN_MODE_EXPLICIT="dry-run"
            shift
            ;;
        --live)
            [[ "$RUN_MODE_EXPLICIT" == "dry-run" ]] && { echo "Cannot combine --dry-run and --live" >&2; exit 1; }
            RUN_MODE="live"
            RUN_MODE_EXPLICIT="live"
            shift
            ;;
        --search)
            [[ $# -ge 2 ]] || { echo "--search requires a value" >&2; exit 2; }
            SEARCH_QUERY="$2"
            shift 2
            ;;
        --limit|--max-responses)
            [[ $# -ge 2 ]] || { echo "$1 requires a value" >&2; exit 2; }
            MAX_RESPONSES="$2"
            shift 2
            ;;
        --per-page)
            [[ $# -ge 2 ]] || { echo "--per-page requires a value" >&2; exit 2; }
            PER_PAGE="$2"
            shift 2
            ;;
        --pages)
            [[ $# -ge 2 ]] || { echo "--pages requires a value" >&2; exit 2; }
            TOTAL_PAGES="$2"
            shift 2
            ;;
        --system-prompt)
            [[ $# -ge 2 ]] || { echo "--system-prompt requires a value" >&2; exit 2; }
            SYSTEM_PROMPT="$2"
            shift 2
            ;;
        --excluded-filter)
            [[ $# -ge 2 ]] || { echo "--excluded-filter requires a value" >&2; exit 2; }
            EXCLUDED_FILTER="$2"
            shift 2
            ;;
        --profile)
            [[ $# -ge 2 ]] || { echo "--profile requires a value" >&2; exit 2; }
            PROFILE_ID="$2"
            export HH_PROFILE_ID="$2"
            shift 2
            ;;
        -h|--help)
            cat <<'EOF'
Usage: apply.sh [--dry-run|--live] [options]

  --live                 Send real applications. Default is dry-run.
  --search QUERY         Search query.
  --limit N              Maximum successful applications for this run.
  --per-page N           Search results per page (default: 50).
  --pages N              Maximum search pages (default: 20).
  --system-prompt FILE   AI system prompt template.
  --excluded-filter REGEX
  --profile ID

The scan depth is intentionally independent from --limit. This lets the worker
skip irrelevant/already-applied vacancies and continue until it reaches the
successful-application quota or exhausts the configured pages.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
done

for value_name in MAX_RESPONSES PER_PAGE TOTAL_PAGES; do
    value="${!value_name}"
    if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "$value_name must be a positive integer: $value" >&2
        exit 2
    fi
done
if (( PER_PAGE > 100 )); then
    echo "PER_PAGE cannot exceed 100" >&2
    exit 2
fi

if [[ ! -f "$SYSTEM_PROMPT" ]]; then
    echo "Cover-letter prompt not found: $SYSTEM_PROMPT" >&2
    exit 1
fi
if ! command -v envsubst >/dev/null 2>&1; then
    echo "envsubst is required (package gettext/gettext-base)" >&2
    exit 1
fi

RENDERED_SYSTEM_PROMPT="$(mktemp "${TMPDIR:-/tmp}/hh-apply-prompt.XXXXXX")"
cleanup() {
    rm -f "$RENDERED_SYSTEM_PROMPT"
}
trap cleanup EXIT

envsubst '${HH_NAME} ${HH_TELEGRAM}' < "$SYSTEM_PROMPT" > "$RENDERED_SYSTEM_PROMPT"

CHECK_ARGS=(--purpose cover-letter)
if [[ -n "$PROFILE_ID" ]]; then
    CHECK_ARGS+=(--profile "$PROFILE_ID")
fi
python3 "$SCRIPT_DIR/check_ai.py" "${CHECK_ARGS[@]}"

HH_CMD=(hh-applicant-tool --no-auto-auth)
if [[ -n "$PROFILE_ID" ]]; then
    HH_CMD+=(--profile-id "$PROFILE_ID")
fi

MODE_ARGS=()
if [[ "$RUN_MODE" == "dry-run" ]]; then
    MODE_ARGS+=(--dry-run)
fi

echo "HH apply: mode=$RUN_MODE query='$SEARCH_QUERY' max_responses=$MAX_RESPONSES scan=$TOTAL_PAGES*$PER_PAGE"

"${HH_CMD[@]}" apply-vacancies \
    --search "$SEARCH_QUERY" \
    --ai \
    --system-prompt "$RENDERED_SYSTEM_PROMPT" \
    --force-message \
    --excluded-filter "$EXCLUDED_FILTER" \
    --skip-tests \
    --max-responses "$MAX_RESPONSES" \
    --per-page "$PER_PAGE" \
    --total-pages "$TOTAL_PAGES" \
    "${MODE_ARGS[@]}"
