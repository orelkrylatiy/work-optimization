#!/usr/bin/env bash
# setup-systemd-timer.sh — Настройка systemd timer для hh-applicant-tool
# Для Linux серверов с systemd

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Настройка systemd timer для HH Applicant Tool ===${NC}"
echo

# Проверка systemd
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}Ошибка: systemd не найден${NC}"
    echo "Этот скрипт только для Linux с systemd"
    exit 1
fi

# Пути
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
USER="${USER:-$SUDO_USER}"
HOME_DIR=$(eval echo ~$USER)

# Время запуска (по умолчанию 9:00)
RUN_TIME="${RUN_TIME:-09:00}"

echo "Директория проекта: $PROJECT_DIR"
echo "Время запуска: $RUN_TIME"
echo "Пользователь: $USER"
echo

# Создание директорий
mkdir -p "$HOME_DIR/.config/systemd/user"
mkdir -p "$PROJECT_DIR/logs"

# Путь к hh-applicant-tool
HH_TOOL="$PYTHON_BIN -m hh_applicant_tool"

# === Service файл ===
SERVICE_FILE="$HOME_DIR/.config/systemd/user/hh-boost.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=HH Applicant Tool - Boost Resume
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=$HH_TOOL boost-resume
Environment=PATH=/usr/local/bin:/usr/bin:/bin
StandardOutput=append:$PROJECT_DIR/logs/boost.log
StandardError=append:$PROJECT_DIR/logs/boost.log

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}✓ Создан service: $SERVICE_FILE${NC}"

# === Timer файл ===
TIMER_FILE="$HOME_DIR/.config/systemd/user/hh-boost.timer"
cat > "$TIMER_FILE" << EOF
[Unit]
Description=Run HH boost daily at $RUN_TIME
Requires=hh-boost.service

[Timer]
OnCalendar=*-*-* $RUN_TIME
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Создан timer: $TIMER_FILE${NC}"

# === Apply service ===
APPLY_SERVICE_FILE="$HOME_DIR/.config/systemd/user/hh-apply.service"
cat > "$APPLY_SERVICE_FILE" << EOF
[Unit]
Description=HH Applicant Tool - Apply Vacancies
After=network.target hh-boost.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=$HH_TOOL apply-vacancies --search "Frontend разработчик" --letter-file $PROJECT_DIR/letter.txt --force-message --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" --skip-tests --per-page 50 --total-pages 3
Environment=PATH=/usr/local/bin:/usr/bin:/bin
StandardOutput=append:$PROJECT_DIR/logs/apply.log
StandardError=append:$PROJECT_DIR/logs/apply.log

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}✓ Создан apply service: $APPLY_SERVICE_FILE${NC}"

# === Apply timer ===
APPLY_TIMER_FILE="$HOME_DIR/.config/systemd/user/hh-apply.timer"
APPLY_TIME=$(echo "$RUN_TIME" | awk -F: '{printf "%02d:%02d", $1, $2+15}')
cat > "$APPLY_TIMER_FILE" << EOF
[Unit]
Description=Run HH apply daily at $APPLY_TIME
Requires=hh-apply.service

[Timer]
OnCalendar=*-*-* $APPLY_TIME
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Создан apply timer: $APPLY_TIMER_FILE${NC}"
echo

# Подтверждение
read -p "Активировать таймеры? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Отменено${NC}"
    exit 0
fi

# Перезагрузка daemon и активация
systemctl --user daemon-reload
systemctl --user enable hh-boost.timer
systemctl --user enable hh-apply.timer
systemctl --user start hh-boost.timer
systemctl --user start hh-apply.timer

echo
echo -e "${GREEN}✓ Таймеры активированы!${NC}"
echo
echo -e "${YELLOW}Проверка статуса:${NC}"
echo "  systemctl --user list-timers | grep hh-"
echo
echo -e "${YELLOW}Просмотр логов:${NC}"
echo "  tail -f $PROJECT_DIR/logs/boost.log"
echo "  tail -f $PROJECT_DIR/logs/apply.log"
echo
echo -e "${YELLOW}Для отмены:${NC}"
echo "  systemctl --user disable --now hh-boost.timer hh-apply.timer"
