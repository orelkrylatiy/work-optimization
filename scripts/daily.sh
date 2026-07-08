#!/usr/bin/env bash
#
# daily.sh — Ежедневный workflow: подъём резюме + отклики + ответы
#
# Использование:
#   ./scripts/daily.sh [--apply-only] [--reply-only] [--full]
#
# Примеры:
#   ./scripts/daily.sh                  # Полный workflow (resume + apply + reply)
#   ./scripts/daily.sh --apply-only     # Только отклики
#   ./scripts/daily.sh --reply-only     # Только ответы
#   ./scripts/daily.sh --full           # Полный с dry-run сначала
#

set -euo pipefail

# Конфигурация
SEARCH_QUERY="${SEARCH_QUERY:-Frontend разработчик}"
APPLY_LIMIT="${APPLY_LIMIT:-100}"
REPLY_ITERATIONS="${REPLY_ITERATIONS:-6}"
REPLY_CHATS="${REPLY_CHATS:-50}"

# Флаги
APPLY_ONLY=false
REPLY_ONLY=false
FULL=false
DRY_RUN_FIRST=false

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --apply-only)
            APPLY_ONLY=true
            shift
            ;;
        --reply-only)
            REPLY_ONLY=true
            shift
            ;;
        --full)
            FULL=true
            DRY_RUN_FIRST=true
            shift
            ;;
        --dry-run)
            DRY_RUN_FIRST=true
            shift
            ;;
        --search)
            SEARCH_QUERY="$2"
            shift 2
            ;;
        --limit)
            APPLY_LIMIT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--apply-only] [--reply-only] [--full] [--dry-run]"
            echo ""
            echo "Опции:"
            echo "  --apply-only    Только отклики на вакансии"
            echo "  --reply-only    Только ответы работодателям"
            echo "  --full          Полный workflow с dry-run сначала"
            echo "  --dry-run       Запустить dry-run перед live"
            echo "  --search        Поисковый запрос для откликов"
            echo "  --limit         Лимит вакансий"
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
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Функция для печати заголовка
print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Функция для печати подзаголовка
print_step() {
    echo -e "${CYAN}▶ $1${NC}"
    echo ""
}

# ============================================================================
# Полный workflow
# ============================================================================

if [[ "$APPLY_ONLY" == false && "$REPLY_ONLY" == false ]]; then
    print_header "Ежедневный workflow — Подъём резюме + Отклики + Ответы"
    
    # Шаг 1: Подъём резюме
    print_step "Шаг 1/3 — Подъём резюме в топ"
    hh-applicant-tool boost-resume
    echo ""
    
    # Шаг 2: Отклики
    print_step "Шаг 2/3 — Отклики на вакансии"
    if [[ "$DRY_RUN_FIRST" == true ]]; then
        echo -e "${YELLOW}🧪 Сначала dry-run...${NC}"
        "$SCRIPT_DIR/apply.sh" --dry-run --search "$SEARCH_QUERY" --limit "$APPLY_LIMIT"
        echo ""
        echo -e "${YELLOW}⏸  Пауза 5 секунд перед live запуском...${NC}"
        sleep 5
        echo ""
    fi
    "$SCRIPT_DIR/apply.sh" --search "$SEARCH_QUERY" --limit "$APPLY_LIMIT"
    echo ""
    
    # Шаг 3: Ответы
    print_step "Шаг 3/3 — Ответы работодателям"
    "$SCRIPT_DIR/reply.sh" --iterations "$REPLY_ITERATIONS" --chats "$REPLY_CHATS"
    echo ""
    
    print_header "✅ Ежедневный workflow завершён!"
    exit 0
fi

# ============================================================================
# Только отклики
# ============================================================================

if [[ "$APPLY_ONLY" == true ]]; then
    print_header "Отклики на вакансии"
    
    if [[ "$DRY_RUN_FIRST" == true ]]; then
        echo -e "${YELLOW}🧪 Сначала dry-run...${NC}"
        "$SCRIPT_DIR/apply.sh" --dry-run --search "$SEARCH_QUERY" --limit "$APPLY_LIMIT"
        echo ""
        echo -e "${YELLOW}⏸  Пауза 5 секунд перед live запуском...${NC}"
        sleep 5
        echo ""
    fi
    
    "$SCRIPT_DIR/apply.sh" --search "$SEARCH_QUERY" --limit "$APPLY_LIMIT"
    exit 0
fi

# ============================================================================
# Только ответы
# ============================================================================

if [[ "$REPLY_ONLY" == true ]]; then
    print_header "Ответы работодателям"
    
    "$SCRIPT_DIR/reply.sh" --iterations "$REPLY_ITERATIONS" --chats "$REPLY_CHATS"
    exit 0
fi
