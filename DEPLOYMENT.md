# Production Deployment Guide

## 🚀 Quick Start Deployment

### 1. SSH в сервер
```bash
ssh root@209.250.237.182
```

### 2. Загрузить и запустить deploy скрипт
```bash
cd /tmp
wget https://raw.githubusercontent.com/s3rgeym/hh-applicant-tool/main/deploy.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

### 3. Настроить конфигурацию
```bash
nano /opt/hh-applicant-tool/.env
nano /opt/hh-applicant-tool/config/config.yaml
```

### 4. Перезагрузить сервис
```bash
sudo systemctl restart hh-applicant-tool-admin
```

---

## 📋 Manual Deployment (если deploy.sh не подходит)

### Предпосылки
- Python 3.11+
- Git
- Supervisor или systemd (для управления процессами)
- Nginx (опционально для reverse proxy)

### Шаги

#### 1. Подготовка сервера
```bash
# Обновляем пакеты
sudo apt-get update
sudo apt-get upgrade -y

# Устанавливаем зависимости
sudo apt-get install -y python3-pip python3-venv git supervisor nginx
```

#### 2. Клонируем репозиторий
```bash
sudo mkdir -p /opt/hh-applicant-tool
sudo chown $USER:$USER /opt/hh-applicant-tool
cd /opt/hh-applicant-tool
git clone https://github.com/s3rgeym/hh-applicant-tool.git .
```

#### 3. Создаём виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# или если используется poetry:
pip install poetry
poetry install --no-dev
```

#### 4. Конфигурируем приложение
```bash
cp .env.example .env
cp config/config.example.yaml config/config.yaml

# Отредактируйте конфиги
nano .env
nano config/config.yaml
```

#### 5. Инициализируем БД
```bash
python3 -m hh_applicant_tool.storage.utils
```

#### 6. Настраиваем Supervisor для admin панели

Создаём файл `/etc/supervisor/conf.d/hh-admin.conf`:
```ini
[program:hh-applicant-tool-admin]
command=/opt/hh-applicant-tool/.venv/bin/python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000
directory=/opt/hh-applicant-tool
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/hh-admin.log
environment=PATH="/opt/hh-applicant-tool/.venv/bin",CONFIG_DIR="/opt/hh-applicant-tool/config"
```

Запускаем:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start hh-applicant-tool-admin
```

#### 7. Настраиваем Nginx (опционально)

Создаём файл `/etc/nginx/sites-available/hh-admin`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включаем сайт:
```bash
sudo ln -s /etc/nginx/sites-available/hh-admin /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔧 Полезные команды

### Проверить статус
```bash
sudo systemctl status hh-applicant-tool-admin
# или для supervisor:
sudo supervisorctl status hh-applicant-tool-admin
```

### Просмотреть логи
```bash
sudo journalctl -u hh-applicant-tool-admin -f
# или для supervisor:
sudo tail -f /var/log/hh-admin.log
```

### Перезагрузить сервис
```bash
sudo systemctl restart hh-applicant-tool-admin
# или для supervisor:
sudo supervisorctl restart hh-applicant-tool-admin
```

### Обновить код
```bash
cd /opt/hh-applicant-tool
git fetch origin
git reset --hard origin/main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart hh-applicant-tool-admin
```

---

## 🔒 SSL/HTTPS (с Let's Encrypt)

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 📊 Мониторинг

Рекомендуется использовать:
- **Systemd Journal**: `journalctl`
- **Supervisor logs**: `/var/log/hh-admin.log`
- **Nginx logs**: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

---

## ⚠️ Troubleshooting

### Порт уже занят
```bash
sudo lsof -i :8000
# Убить процесс:
sudo kill -9 <PID>
```

### Ошибки подключения БД
- Проверьте `.env` и `config/config.yaml`
- Убедитесь, что БД инициализирована
- Проверьте права доступа к папке

### Nginx 502 Bad Gateway
- Проверьте статус admin панели: `sudo systemctl status hh-applicant-tool-admin`
- Посмотрите логи: `sudo journalctl -u hh-applicant-tool-admin -n 50`

---

## 📱 Тестирование мобильной версии

После развёртывания проверьте, что админ-панель корректно сжимается на мобильных:
- На узком экране (<768px) боковая панель сжимается до 60px
- Иконки остаются видимыми и интерактивными
- Текстовые ярлыки скрыты, но не исчезают полностью

Откройте на мобильном: `http://yourdomain.com` (или IP:8000)
