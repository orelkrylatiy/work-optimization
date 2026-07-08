#!/usr/bin/env bash
#
# reply.sh — Ответы работодателям (итеративные AI-ответы)
#
# Использование:
#   ./scripts/reply.sh [--dry-run] [--iterations N] [--chats N]
#
# Примеры:
#   ./scripts/reply.sh --dry-run              # Пробный запуск
#   ./scripts/reply.sh                        # Live запуск (6 итераций по 50 чатов)
#   ./scripts/reply.sh --iterations 3         # 3 итерации
#   ./scripts/reply.sh --chats 100            # 100 чатов за итерацию
#

set -euo pipefail

# Конфигурация
MAX_ITERATIONS="${ITERATIONS:-6}"
CHATS_PER_ITERATION="${CHATS:-50}"
TELEGRAM="${TELEGRAM:-@wavemax6}"

# Парсинг аргументов
DRY_RUN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
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
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--dry-run] [--iterations N] [--chats N] [--telegram @USER]"
            echo ""
            echo "Опции:"
            echo "  --dry-run           Пробный запуск без отправки"
            echo "  --iterations N      Максимум итераций (по умолчанию: 6)"
            echo "  --chats N           Чатов за итерацию (по умолчанию: 50)"
            echo "  --telegram @USER    Telegram для связи (по умолчанию: @wavemax6)"
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

# Заголовок
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Итеративные AI-ответы работодателям${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Telegram для связи:${NC} $TELEGRAM"
echo -e "${YELLOW}Максимум итераций:${NC} $MAX_ITERATIONS"
echo -e "${YELLOW}Чатов за итерацию:${NC} $CHATS_PER_ITERATION"
echo -e "${YELLOW}Модель AI:${NC} qwen2.5:14b (Ollama)"
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}Режим:${NC} ${RED}DRY-RUN (без отправки)${NC}"
else
    echo -e "${YELLOW}Режим:${NC} ${GREEN}LIVE${NC}"
fi
echo ""

# Проверка Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama не установлена. Установите: https://ollama.ai${NC}"
    exit 1
fi

# Проверка доступности модели
echo -e "${CYAN}🔍 Проверка модели Ollama...${NC}"
if ! ollama list 2>/dev/null | grep -q "qwen2.5"; then
    echo -e "${YELLOW}⚠️  Модель qwen2.5 не найдена. Скачивание...${NC}"
    ollama pull qwen2.5:14b
fi

# Экспорт переменных для скрипта
export TELEGRAM

# Запуск скрипта
echo -e "${GREEN}🚀 Запуск итеративных ответов...${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/reply_iterative_ai.py" $DRY_RUN

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${GREEN}✅ Dry-run завершён. Проверьте вывод выше.${NC}"
    echo -e "${YELLOW}Для live запуска запустите: ${NC}./scripts/reply.sh"
else
    echo -e "${GREEN}✅ Ответы завершены!${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
