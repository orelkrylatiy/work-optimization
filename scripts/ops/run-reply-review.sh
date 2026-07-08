#!/usr/bin/env bash
set -euo pipefail

PERIOD_DAYS="${PERIOD_DAYS:-7}"
USE_AI="${USE_AI:-1}"
ONLY_INVITATIONS="${ONLY_INVITATIONS:-0}"

cmd=(
  /usr/local/bin/python -m hh_applicant_tool
  --no-auto-auth
  --json
  reply-employers
  --dry-run
  --period "${PERIOD_DAYS}"
)

if [[ "${USE_AI}" == "1" ]]; then
  cmd+=(--use-ai)
fi

if [[ "${ONLY_INVITATIONS}" == "1" ]]; then
  cmd+=(--only-invitations)
fi

printf 'Running command:\n'
printf ' %q' "${cmd[@]}"
printf '\n'

exec "${cmd[@]}"
