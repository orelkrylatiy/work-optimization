#!/usr/bin/env bash
#
# reply.sh — Ответы работодателям (итеративные AI-ответы)
#
# Использование:
#   ./scripts/reply.sh [--dry-run|--live] [--iterations N] [--chats N]
#
# Примеры:
#   ./scripts/reply.sh                        # Пробный запуск (по умолчанию)
#   ./scripts/reply.sh --live                 # Live запуск (6 итераций по 50 чатов)
#   ./scripts/reply.sh --iterations 3         # 3 итерации
#   ./scripts/reply.sh --chats 100            # 100 чатов за итерацию
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
MAX_ITERATIONS="${ITERATIONS:-6}"
CHATS_PER_ITERATION="${CHATS:-50}"
TELEGRAM="${HH_TELEGRAM:-${TELEGRAM:-@maxxwway}}"
REPLY_PROMPT_TEMPLATE="${REPLY_PROMPT_TEMPLATE:-$PROJECT_ROOT/prompts/reply_employer.txt}"
# Мультиаккаунт: HH_PROFILE_ID берётся из окружения или --profile флага

# Парсинг аргументов
RUN_MODE="dry-run"
RUN_MODE_EXPLICIT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            if [[ "$RUN_MODE_EXPLICIT" == "live" ]]; then
                echo "Нельзя использовать --dry-run и --live одновременно" >&2
                exit 1
            fi
            RUN_MODE="dry-run"
            RUN_MODE_EXPLICIT="dry-run"
            shift
            ;;
        --live)
            if [[ "$RUN_MODE_EXPLICIT" == "dry-run" ]]; then
                echo "Нельзя использовать --dry-run и --live одновременно" >&2
                exit 1
            fi
            RUN_MODE="live"
            RUN_MODE_EXPLICIT="live"
            shift
            ;;
        --iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        --chats)
            CHATS_PER_ITERATION="$2"
            shift 2
            ;;
        --telegram)
            TELEGRAM="$2"
            export HH_TELEGRAM="$2"
            shift 2
            ;;
        --profile)
            export HH_PROFILE_ID="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--dry-run|--live] [--iterations N] [--chats N] [--profile ID]"
            echo ""
            echo "Опции:"
            echo "  --dry-run           Пробный запуск без отправки (по умолчанию)"
            echo "  --live              Разрешить реальную отправку сообщений"
            echo "  --iterations N      Максимум итераций (по умолчанию: 6)"
            echo "  --chats N           Чатов за итерацию (по умолчанию: 50)"
            echo "  --profile ID        Профиль аккаунта (или HH_PROFILE_ID=...)"
            exit 0
            ;;
        *)
            echo "Неизвестная опция: $1"
            exit 1
            ;;
    esac
done

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

REPLY_SYSTEM_PROMPT_FILE=""

cleanup_rendered_files() {
    if [[ -n "${REPLY_SYSTEM_PROMPT_FILE:-}" && -f "$REPLY_SYSTEM_PROMPT_FILE" ]]; then
        rm -f "$REPLY_SYSTEM_PROMPT_FILE"
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

    rendered_path="$(mktemp "${TMPDIR:-/tmp}/hh-reply-prompt.XXXXXX")"
    envsubst '${HH_NAME} ${HH_TELEGRAM}' < "$template_path" > "$rendered_path"
    printf '%s\n' "$rendered_path"
}

trap cleanup_rendered_files EXIT

# Заголовок
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Итеративные AI-ответы работодателям${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Telegram для связи:${NC} $TELEGRAM"
echo -e "${YELLOW}Максимум итераций:${NC} $MAX_ITERATIONS"
echo -e "${YELLOW}Чатов за итерацию:${NC} $CHATS_PER_ITERATION"
echo -e "${YELLOW}Промпт ответов:${NC} $REPLY_PROMPT_TEMPLATE"
if [[ "$RUN_MODE" == "dry-run" ]]; then
    echo -e "${YELLOW}Режим:${NC} ${RED}DRY-RUN (без отправки)${NC}"
else
    echo -e "${YELLOW}Режим:${NC} ${GREEN}LIVE (явно включён через --live)${NC}"
fi
echo ""

echo -e "${CYAN}🔍 Проверка AI-конфига...${NC}"
python3 "$SCRIPT_DIR/check_ai.py"

# Экспорт переменных для скрипта
export TELEGRAM
export HH_TELEGRAM="$TELEGRAM"
export ITERATIONS="$MAX_ITERATIONS"
export CHATS="$CHATS_PER_ITERATION"
REPLY_SYSTEM_PROMPT_FILE="$(render_prompt_template "$REPLY_PROMPT_TEMPLATE")"
export REPLY_SYSTEM_PROMPT_FILE

# Запуск скрипта
echo -e "${GREEN}🚀 Запуск итеративных ответов...${NC}"
echo ""

REPLY_MODE_ARGS=()
if [[ "$RUN_MODE" == "live" ]]; then
    REPLY_MODE_ARGS+=(--live)
else
    REPLY_MODE_ARGS+=(--dry-run)
fi
python3 "$SCRIPT_DIR/reply_iterative_ai.py" "${REPLY_MODE_ARGS[@]}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [[ "$RUN_MODE" == "dry-run" ]]; then
    echo -e "${GREEN}✅ Dry-run завершён. Проверьте вывод выше.${NC}"
    echo -e "${YELLOW}Для live запуска запустите: ${NC}./scripts/reply.sh --live"
else
    echo -e "${GREEN}✅ Ответы завершены!${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
