#!/usr/bin/env bash
#
# check.sh — Проверка состояния аккаунта HH.ru
#
# Использование:
#   ./scripts/check.sh
#

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_header "Проверка состояния аккаунта HH.ru"

# 1. Проверка авторизации
echo -e "${CYAN}▶ Проверка авторизации...${NC}"
WHOAMI_OUTPUT=$(hh-applicant-tool whoami 2>&1) || true

if echo "$WHOAMI_OUTPUT" | grep -q "Требуется авторизация"; then
    echo -e "${RED}❌ Не авторизован${NC}"
    echo -e "${YELLOW}Запустите: ${NC}hh-applicant-tool authorize"
    exit 1
else
    echo -e "${GREEN}✅ Авторизован${NC}"
    echo "$WHOAMI_OUTPUT" | grep -v "^\[" | head -5
fi
echo ""

# 2. Проверка резюме
echo -e "${CYAN}▶ Проверка резюме...${NC}"
hh-applicant-tool list-resumes
echo ""

# 3. Проверка активных переговоров
echo -e "${CYAN}▶ Активные переговоры...${NC}"
NEGOTIATIONS=$(hh-applicant-tool call-api "/negotiations?status=active&per_page=5" 2>/dev/null) || true

if [[ -n "$NEGOTIATIONS" ]]; then
    TOTAL=$(echo "$NEGOTIATIONS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('items', [])))" 2>/dev/null || echo "?")
    echo -e "${GREEN}Всего активных переговоров: ${TOTAL}${NC}"
    
    # Последние 5
    echo "$NEGOTIATIONS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('items', [])[:5]
for i, item in enumerate(items, 1):
    vacancy = item.get('vacancy', {}).get('name', '???')
    employer = item.get('vacancy', {}).get('employer', {}).get('name', '???')
    state = item.get('state', {}).get('name', 'active')
    print(f'  {i}. {vacancy[:50]} — {employer[:30]} ({state})')
" 2>/dev/null || echo "  (не удалось распарсить)"
else
    echo -e "${YELLOW}Нет активных переговоров${NC}"
fi
echo ""

# 4. Проверка Ollama
echo -e "${CYAN}▶ Проверка Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✅ Ollama установлена${NC}"
    ollama list 2>/dev/null | grep -E "qwen|llama" || echo -e "${YELLOW}⚠️  Модели не найдены${NC}"
else
    echo -e "${RED}❌ Ollama не установлена${NC}"
    echo -e "${YELLOW}Установите: https://ollama.ai${NC}"
fi
echo ""

# 5. Проверка скриптов
echo -e "${CYAN}▶ Проверка скриптов...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for script in apply.sh reply.sh daily.sh; do
    if [[ -x "$SCRIPT_DIR/$script" ]]; then
        echo -e "${GREEN}✅ $script${NC}"
    else
        echo -e "${YELLOW}⚠️  $script (не исполняемый)${NC}"
        chmod +x "$SCRIPT_DIR/$script" 2>/dev/null || true
    fi
done
echo ""

print_header "✅ Проверка завершена!"
