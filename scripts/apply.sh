#!/usr/bin/env bash
#
# apply.sh — Отклики на вакансии HH.ru
#
# Использование:
#   ./scripts/apply.sh [--dry-run] [--search "QUERY"] [--limit N]
#
# Примеры:
#   ./scripts/apply.sh --dry-run                    # Пробный запуск
#   ./scripts/apply.sh                              # Live запуск
#   ./scripts/apply.sh --search "React Developer"   # Свой поисковый запрос
#   ./scripts/apply.sh --limit 100                  # Лимит вакансий
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Конфигурация
SEARCH_QUERY="${SEARCH_QUERY:-Frontend разработчик}"
LIMIT="${LIMIT:-100}"
SYSTEM_PROMPT="${SYSTEM_PROMPT:-$PROJECT_ROOT/prompts/cover_letter_frontend.txt}"
EXCLUDED_FILTER="${EXCLUDED_FILTER:-junior|стажир|bitrix|web3|crypto|blockchain|golang|python|java|1c|продакт|менеджер|pm|дизайнер|qa|тестировщик|devops|аналитик|data|sales|продаж|рекрутер|hr|без опыта|trainee|казань|спб|минск|open\s*space|опенспейс}"

# Парсинг аргументов
DRY_RUN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --search)
            SEARCH_QUERY="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --system-prompt)
            SYSTEM_PROMPT="$2"
            shift 2
            ;;
        --excluded-filter)
            EXCLUDED_FILTER="$2"
            shift 2
            ;;
        --profile)
            export HH_PROFILE_ID="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--dry-run] [--search \"QUERY\"] [--limit N] [--system-prompt FILE] [--profile ID]"
            echo ""
            echo "Опции:"
            echo "  --dry-run              Пробный запуск без отправки"
            echo "  --search \"QUERY\"       Поисковый запрос (по умолчанию: \"Frontend разработчик\")"
            echo "  --limit N              Лимит вакансий (по умолчанию: 100)"
            echo "  --system-prompt FILE   Системный промпт для AI"
            echo "  --excluded-filter      Фильтр исключений (regex)"
            echo "  --profile ID           Профиль аккаунта (или HH_PROFILE_ID=...)"
            exit 0
            ;;
        *)
            echo "Неизвестная опция: $1"
            exit 1
            ;;
    esac
done

if [[ ! "$LIMIT" =~ ^[1-9][0-9]*$ ]]; then
    echo "Лимит должен быть положительным целым числом: $LIMIT" >&2
    exit 1
fi

PER_PAGE=$((LIMIT < 50 ? LIMIT : 50))
TOTAL_PAGES=$(((LIMIT + PER_PAGE - 1) / PER_PAGE))

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

RENDERED_SYSTEM_PROMPT=""

cleanup_rendered_files() {
    if [[ -n "${RENDERED_SYSTEM_PROMPT:-}" && -f "$RENDERED_SYSTEM_PROMPT" ]]; then
        rm -f "$RENDERED_SYSTEM_PROMPT"
    fi
    return 0
}

render_prompt_template() {
    local template_path="$1"
    local rendered_path

    if [[ ! -f "$template_path" ]]; then
        echo -e "${RED}❌ Файл промпта не найден: $template_path${NC}" >&2
        exit 1
    fi
    if ! command -v envsubst >/dev/null 2>&1; then
        echo -e "${RED}❌ envsubst не найден. Установите gettext.${NC}" >&2
        exit 1
    fi

    rendered_path="$(mktemp "${TMPDIR:-/tmp}/hh-apply-prompt.XXXXXX")"
    envsubst '${HH_NAME} ${HH_TELEGRAM}' < "$template_path" > "$rendered_path"
    printf '%s\n' "$rendered_path"
}

trap cleanup_rendered_files EXIT

# Заголовок
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}          HH Applicant Tool — Отклики на вакансии${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Поисковый запрос:${NC} $SEARCH_QUERY"
echo -e "${YELLOW}Лимит вакансий:${NC} $LIMIT"
echo -e "${YELLOW}Системный промпт:${NC} $SYSTEM_PROMPT"
echo -e "${YELLOW}Режим писем:${NC} AI (config-driven provider)"
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}Режим:${NC} ${RED}DRY-RUN (без отправки)${NC}"
else
    echo -e "${YELLOW}Режим:${NC} ${GREEN}LIVE${NC}"
fi
echo ""

RENDERED_SYSTEM_PROMPT="$(render_prompt_template "$SYSTEM_PROMPT")"

echo -e "${YELLOW}Проверка AI-конфига:${NC}"
python3 "$SCRIPT_DIR/check_ai.py"
echo ""

# Запуск откликов
echo -e "${GREEN}🚀 Запуск откликов с AI-письмами...${NC}"
echo ""

HH_CMD=(hh-applicant-tool --no-auto-auth)
if [[ -n "${HH_PROFILE_ID:-}" ]]; then
    HH_CMD+=(--profile-id "$HH_PROFILE_ID")
fi

"${HH_CMD[@]}" apply-vacancies \
    --search "$SEARCH_QUERY" \
    --ai \
    --system-prompt "$RENDERED_SYSTEM_PROMPT" \
    --force-message \
    --excluded-filter "$EXCLUDED_FILTER" \
    --skip-tests \
    --per-page "$PER_PAGE" \
    --total-pages "$TOTAL_PAGES" \
    $DRY_RUN

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${GREEN}✅ Dry-run завершён. Проверьте вывод выше.${NC}"
    echo -e "${YELLOW}Для live запуска запустите: ${NC}./scripts/apply.sh"
else
    echo -e "${GREEN}✅ Отклики завершены!${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
