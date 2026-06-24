#!/usr/bin/env bash
# setup-cron.sh — Настройка cron для hh-applicant-tool
# Запускает ежедневный workflow в заданное время

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Настройка cron для HH Applicant Tool ===${NC}"
echo

# Проверка пути к проекту
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
echo "Директория проекта: $PROJECT_DIR"

# Проверка пути к Python
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo -e "${RED}Ошибка: python3 не найден${NC}"
    exit 1
fi
echo "Python: $PYTHON_BIN"

# Проверка пути к hh-applicant-tool
HH_TOOL="${HH_TOOL:-$PYTHON_BIN -m hh_applicant_tool}"
echo "HH Tool: $HH_TOOL"
echo

# Время запуска (по умолчанию 9:00)
RUN_TIME="${RUN_TIME:-09:00}"
RUN_HOUR=$(echo "$RUN_TIME" | cut -d: -f1)
RUN_MIN=$(echo "$RUN_TIME" | cut -d: -f2)

echo -e "${YELLOW}Время запуска: $RUN_TIME (MSK)${NC}"
echo

# Создание crontab
CRON_JOB="$RUN_MIN $RUN_HOUR * * * cd $PROJECT_DIR && $HH_TOOL boost-resume >> $PROJECT_DIR/logs/boost.log 2>&1"
CRON_JOB2="$((RUN_MIN + 15)) $RUN_HOUR * * * cd $PROJECT_DIR && $HH_TOOL apply-vacancies --search 'Frontend разработчик' --letter-file $PROJECT_DIR/letter.txt --force-message --excluded-filter 'junior|стажир|bitrix|web3|crypto|blockchain' --skip-tests --per-page 50 --total-pages 3 >> $PROJECT_DIR/logs/apply.log 2>&1"

echo -e "${YELLOW}Добавляем задачи в cron:${NC}"
echo "1. Поднятие резюме: $CRON_JOB"
echo "2. Отклики: $CRON_JOB2"
echo

# Подтверждение
read -p "Продолжить? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Отменено${NC}"
    exit 0
fi

# Создание директории для логов
mkdir -p "$PROJECT_DIR/logs"

# Добавление в crontab
(crontab -l 2>/dev/null | grep -v "hh-applicant-tool" || true; echo "$CRON_JOB"; echo "$CRON_JOB2") | crontab -

echo -e "${GREEN}✓ Cron настроен успешно!${NC}"
echo
echo -e "${YELLOW}Проверка:${NC}"
crontab -l | grep "hh-applicant-tool" || crontab -l | grep "$PROJECT_DIR"
echo
echo -e "${YELLOW}Логи будут в: $PROJECT_DIR/logs/${NC}"
echo
echo -e "${YELLOW}Для отмены выполните:${NC}"
echo "  crontab -e  # и удалите строки с hh-applicant-tool"
