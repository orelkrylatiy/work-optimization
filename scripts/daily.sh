#!/usr/bin/env bash
#
# daily.sh — Ежедневный workflow: подъём резюме + отклики + ответы
#
# Использование:
#   ./scripts/daily.sh [--apply-only] [--reply-only] [--full] [--dry-run|--live]
#
# Примеры:
#   ./scripts/daily.sh                  # Полный dry-run workflow (по умолчанию)
#   ./scripts/daily.sh --apply-only     # Только dry-run отклики
#   ./scripts/daily.sh --reply-only     # Только dry-run ответы
#   ./scripts/daily.sh --full --live    # Dry-run, затем реальный полный workflow
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
APPLY_LIMIT="${APPLY_LIMIT:-100}"
REPLY_ITERATIONS="${REPLY_ITERATIONS:-6}"
REPLY_CHATS="${REPLY_CHATS:-50}"

# Флаги
APPLY_ONLY=false
REPLY_ONLY=false
FULL=false
RUN_MODE="dry-run"
RUN_MODE_EXPLICIT=""

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
            shift
            ;;
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
        --search)
            SEARCH_QUERY="$2"
            shift 2
            ;;
        --limit)
            APPLY_LIMIT="$2"
            shift 2
            ;;
        --profile)
            export HH_PROFILE_ID="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--apply-only] [--reply-only] [--full] [--dry-run|--live] [--profile ID]"
            echo ""
            echo "Опции:"
            echo "  --apply-only    Только отклики на вакансии"
            echo "  --reply-only    Только ответы работодателям"
            echo "  --full          Сначала выполнить dry-run; live только вместе с --live"
            echo "  --dry-run       Только проверка без live-действий (по умолчанию)"
            echo "  --live          Разрешить реальные действия"
            echo "  --search        Поисковый запрос для откликов"
            echo "  --limit         Лимит вакансий"
            echo "  --profile ID    Профиль аккаунта (по умолчанию: один основной аккаунт)"
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

if [[ "$APPLY_ONLY" == true && "$REPLY_ONLY" == true ]]; then
    echo "Нельзя использовать --apply-only и --reply-only одновременно" >&2
    exit 1
fi

run_apply() {
    local mode="$1"
    "$SCRIPT_DIR/apply.sh" "$mode" --search "$SEARCH_QUERY" --limit "$APPLY_LIMIT"
}

run_reply() {
    local mode="$1"
    "$SCRIPT_DIR/reply.sh" "$mode" --iterations "$REPLY_ITERATIONS" --chats "$REPLY_CHATS"
}

run_preview_workflow() {
    if [[ "$APPLY_ONLY" == false && "$REPLY_ONLY" == false ]]; then
        print_step "Подъём резюме в топ"
        echo -e "${YELLOW}🧪 Dry-run: подъём резюме пропущен${NC}"
        echo ""
    fi

    if [[ "$REPLY_ONLY" == false ]]; then
        print_step "Отклики на вакансии (dry-run)"
        run_apply --dry-run
        echo ""
    fi

    if [[ "$APPLY_ONLY" == false ]]; then
        print_step "Ответы работодателям (dry-run)"
        run_reply --dry-run
        echo ""
    fi
}

run_live_workflow() {
    if [[ "$APPLY_ONLY" == false && "$REPLY_ONLY" == false ]]; then
        print_step "Подъём резюме в топ (live)"
        HH_CMD=(hh-applicant-tool --no-auto-auth)
        if [[ -n "${HH_PROFILE_ID:-}" ]]; then
            HH_CMD+=(--profile-id "$HH_PROFILE_ID")
        fi
        "${HH_CMD[@]}" boost-resume
        echo ""
    fi

    if [[ "$REPLY_ONLY" == false ]]; then
        print_step "Отклики на вакансии (live)"
        run_apply --live
        echo ""
    fi

    if [[ "$APPLY_ONLY" == false ]]; then
        print_step "Ответы работодателям (live)"
        run_reply --live
        echo ""
    fi
}

if [[ "$RUN_MODE" == "dry-run" || "$FULL" == true ]]; then
    if [[ "$FULL" == true && "$RUN_MODE" == "live" ]]; then
        print_header "Dry-run перед явно подтверждённым live workflow"
    else
        print_header "Ежедневный workflow — Dry-run (live-действия отключены)"
    fi
    run_preview_workflow

    if [[ "$RUN_MODE" == "dry-run" ]]; then
        print_header "✅ Dry-run завершён. Live-действия не выполнялись."
        echo -e "${YELLOW}Для реального запуска используйте: ${NC}$0 --live"
        exit 0
    fi

    echo -e "${YELLOW}⚠️  --live указан явно: запускаем live workflow после dry-run.${NC}"
    echo ""
fi

print_header "Ежедневный workflow — LIVE"
run_live_workflow
print_header "✅ Ежедневный workflow завершён!"
