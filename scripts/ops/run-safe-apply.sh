#!/usr/bin/env bash
set -euo pipefail

SEARCH_QUERY="${SEARCH_QUERY:-}"
LETTER_FILE="${LETTER_FILE:-/app/letter.txt}"
EXCLUDED_FILTER="${EXCLUDED_FILTER:-junior|стажировк|bitrix|ddd|web3|crypto|blockchain|дружн\\w+коллектив|полиграф|open\\s*space|опенспейс|хакатон|конкурс|тестов\\w+ задан|soft skill}"
RESPONSE_DELAY="${RESPONSE_DELAY:-2-5}"
PER_PAGE="${PER_PAGE:-50}"
TOTAL_PAGES="${TOTAL_PAGES:-5}"
USE_AI="${USE_AI:-0}"
AI_FILTER="${AI_FILTER:-}"
DRY_RUN="${DRY_RUN:-0}"

if [[ -z "${SEARCH_QUERY}" ]]; then
  echo "SEARCH_QUERY is required"
  echo "Example:"
  echo "  SEARCH_QUERY='React frontend developer' scripts/ops/run-safe-apply.sh"
  exit 1
fi

cmd=(
  /usr/local/bin/python -m hh_applicant_tool
  --no-auto-auth
  apply-vacancies
  --search "${SEARCH_QUERY}"
  --force-message
  --letter-file "${LETTER_FILE}"
  --skip-tests
  --excluded-filter "${EXCLUDED_FILTER}"
  --response-delay "${RESPONSE_DELAY}"
  --per-page "${PER_PAGE}"
  --total-pages "${TOTAL_PAGES}"
)

if [[ "${USE_AI}" == "1" ]]; then
  cmd+=(--use-ai)
fi

if [[ -n "${AI_FILTER}" ]]; then
  cmd+=(--ai-filter "${AI_FILTER}")
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  cmd+=(--dry-run)
fi

printf 'Running command:\n'
printf ' %q' "${cmd[@]}"
printf '\n'

exec "${cmd[@]}"
