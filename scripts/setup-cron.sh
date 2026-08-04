#!/usr/bin/env bash
# setup-cron.sh — Настройка cron для hh-applicant-tool
# Запускает ежедневный workflow в заданное время

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Настройка cron для HH Applicant Tool ===${NC}"
echo

# Проверка пути к проекту
PROJECT_DIR="${PROJECT_DIR:-$PROJECT_ROOT}"
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

if [[ ! "$RUN_HOUR" =~ ^([01]?[0-9]|2[0-3])$ || ! "$RUN_MIN" =~ ^[0-5]?[0-9]$ ]]; then
    echo -e "${RED}Ошибка: RUN_TIME должен быть в формате HH:MM${NC}"
    exit 1
fi

APPLY_TOTAL_MINUTES=$((10#$RUN_HOUR * 60 + 10#$RUN_MIN + 15))
REPLY_TOTAL_MINUTES=$((10#$RUN_HOUR * 60 + 10#$RUN_MIN + 30))
APPLY_HOUR=$((APPLY_TOTAL_MINUTES / 60 % 24))
APPLY_MIN=$((APPLY_TOTAL_MINUTES % 60))
REPLY_HOUR=$((REPLY_TOTAL_MINUTES / 60 % 24))
REPLY_MIN=$((REPLY_TOTAL_MINUTES % 60))

echo -e "${YELLOW}Время запуска: $RUN_TIME (локальное время сервера)${NC}"
echo

# Создание crontab. Публикация резюме — необратимое внешнее действие, поэтому
# расписание для неё создаётся только явным opt-in через переменную окружения.
ENABLE_LIVE_RESUME_PUBLISHING="${ENABLE_LIVE_RESUME_PUBLISHING:-false}"
CRON_JOB=""
if [[ "$ENABLE_LIVE_RESUME_PUBLISHING" == "true" ]]; then
    CRON_JOB="$RUN_MIN $RUN_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/all-profiles.sh boost --live >> $PROJECT_DIR/logs/boost.log 2>&1"
fi
CRON_JOB2="$APPLY_MIN $APPLY_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/all-profiles.sh apply --dry-run >> $PROJECT_DIR/logs/apply.log 2>&1"
CRON_JOB3="$REPLY_MIN $REPLY_HOUR * * * cd $PROJECT_DIR && /bin/bash $PROJECT_DIR/scripts/all-profiles.sh reply --dry-run >> $PROJECT_DIR/logs/reply.log 2>&1"

echo -e "${YELLOW}Добавляем задачи в cron:${NC}"
if [[ -n "$CRON_JOB" ]]; then
    echo "1. Поднятие резюме (live): $CRON_JOB"
else
    echo "1. Поднятие резюме: отключено (set ENABLE_LIVE_RESUME_PUBLISHING=true to opt in)"
fi
echo "2. Отклики (dry-run): $CRON_JOB2"
echo "3. Ответы (dry-run): $CRON_JOB3"
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
(
    crontab -l 2>/dev/null | grep -v "$PROJECT_DIR" || true
    [[ -n "$CRON_JOB" ]] && echo "$CRON_JOB"
    echo "$CRON_JOB2"
    echo "$CRON_JOB3"
) | crontab -

echo -e "${GREEN}✓ Cron настроен успешно!${NC}"
echo
echo -e "${YELLOW}Проверка:${NC}"
crontab -l | grep "hh-applicant-tool" || crontab -l | grep "$PROJECT_DIR"
echo
echo -e "${YELLOW}Логи будут в: $PROJECT_DIR/logs/${NC}"
echo
echo -e "${YELLOW}Для отмены выполните:${NC}"
echo "  crontab -e  # и удалите строки с hh-applicant-tool"
