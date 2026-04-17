#!/bin/bash
# HH Applicant Tool - Production Deployment Script
# Используется для развёртывания на Linux VPS

set -e

echo "🚀 Deploying HH Applicant Tool..."

# Конфигурация
REPO_URL="https://github.com/s3rgeym/hh-applicant-tool.git"
DEPLOY_DIR="/opt/hh-applicant-tool"
VENV_DIR="$DEPLOY_DIR/.venv"
SERVICE_NAME="hh-applicant-tool"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 1. Проверяем Python
log "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed. Please install it first."
fi
PYTHON_VERSION=$(python3 --version)
log "Found: $PYTHON_VERSION"

# 2. Проверяем git
if ! command -v git &> /dev/null; then
    error "Git is not installed. Please install it first."
fi

# 3. Создаём директорию для проекта
if [ ! -d "$DEPLOY_DIR" ]; then
    log "Creating deployment directory: $DEPLOY_DIR"
    mkdir -p "$DEPLOY_DIR"
fi

# 4. Клонируем или обновляем репозиторий
if [ -d "$DEPLOY_DIR/.git" ]; then
    log "Repository exists. Pulling latest changes..."
    cd "$DEPLOY_DIR"
    git fetch origin
    git reset --hard origin/main
else
    log "Cloning repository..."
    git clone "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# 5. Создаём виртуальное окружение
if [ ! -d "$VENV_DIR" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 6. Активируем виртуальное окружение и устанавливаем зависимости
log "Activating virtual environment and installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt 2>/dev/null || pip install poetry && poetry install --no-dev

# 7. Проверяем конфиги
log "Checking configuration files..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    warning ".env file not found. Copying from .env.example..."
    if [ -f "$DEPLOY_DIR/.env.example" ]; then
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        echo "⚠️  Please edit $DEPLOY_DIR/.env with your credentials"
    fi
fi

# 8. Запускаем миграции БД (если нужны)
log "Initializing database..."
cd "$DEPLOY_DIR"
python3 -m hh_applicant_tool.storage.utils 2>/dev/null || true

# 9. Проверяем admin панель
log "Checking admin panel..."
if [ ! -f "$DEPLOY_DIR/admin/app.py" ]; then
    error "Admin panel not found!"
fi

# 10. Создаём systemd сервис для admin панели
log "Setting up systemd service..."
ADMIN_SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME-admin.service"
if [ ! -f "$ADMIN_SERVICE_FILE" ]; then
    log "Creating systemd service for admin panel..."
    sudo tee "$ADMIN_SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=HH Applicant Tool Admin Panel
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$DEPLOY_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="CONFIG_DIR=$DEPLOY_DIR/config"
ExecStart=$VENV_DIR/bin/python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME-admin"
fi

# 11. Запускаем сервис
log "Starting admin panel service..."
sudo systemctl restart "$SERVICE_NAME-admin"
sudo systemctl status "$SERVICE_NAME-admin" --no-pager

# 12. Проверяем статус
log "Verifying deployment..."
sleep 2
if curl -s http://localhost:8000/health | grep -q '"ok":true'; then
    log "✅ Admin panel is running and healthy!"
else
    warning "Admin panel might not be responding yet. Check with: sudo systemctl status $SERVICE_NAME-admin"
fi

log "🎉 Deployment complete!"
log "Admin panel URL: http://$(hostname -I | awk '{print $1}'):8000"
log "Logs: sudo journalctl -u $SERVICE_NAME-admin -f"
