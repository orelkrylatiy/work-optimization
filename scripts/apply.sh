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

# Конфигурация
SEARCH_QUERY="${SEARCH_QUERY:-Frontend разработчик}"
LIMIT="${LIMIT:-100}"
LETTER_FILE="${LETTER_FILE:-./letter.txt}"
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
        --letter-file)
            LETTER_FILE="$2"
            shift 2
            ;;
        --excluded-filter)
            EXCLUDED_FILTER="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [--dry-run] [--search \"QUERY\"] [--limit N] [--letter-file FILE]"
            echo ""
            echo "Опции:"
            echo "  --dry-run           Пробный запуск без отправки"
            echo "  --search \"QUERY\"    Поисковый запрос (по умолчанию: \"Frontend разработчик\")"
            echo "  --limit N           Лимит вакансий (по умолчанию: 100)"
            echo "  --letter-file FILE  Файл с шаблоном письма (по умолчанию: ./letter.txt)"
            echo "  --excluded-filter   Фильтр исключений (regex)"
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
NC='\033[0m' # No Color

# Заголовок
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}          HH Applicant Tool — Отклики на вакансии${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Поисковый запрос:${NC} $SEARCH_QUERY"
echo -e "${YELLOW}Лимит вакансий:${NC} $LIMIT"
echo -e "${YELLOW}Файл письма:${NC} $LETTER_FILE"
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}Режим:${NC} ${RED}DRY-RUN (без отправки)${NC}"
else
    echo -e "${YELLOW}Режим:${NC} ${GREEN}LIVE${NC}"
fi
echo ""

# Проверка файла с письмом
if [[ ! -f "$LETTER_FILE" ]]; then
    echo -e "${RED}❌ Файл с письмом не найден: $LETTER_FILE${NC}"
    exit 1
fi

# Запуск откликов
echo -e "${GREEN}🚀 Запуск откликов...${NC}"
echo ""

hh-applicant-tool apply-vacancies \
    --search "$SEARCH_QUERY" \
    --letter-file "$LETTER_FILE" \
    --force-message \
    --excluded-filter "$EXCLUDED_FILTER" \
    --skip-tests \
    --per-page 50 \
    --total-pages "$(( (LIMIT + 49) / 50 ))" \
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
