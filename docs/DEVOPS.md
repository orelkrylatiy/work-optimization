# DevOps Guide для HH Applicant Tool

## 🎯 Обзор архитектуры

```
┌─────────────────────────────────────────────┐
│      GitHub Actions (CI/CD Pipeline)        │
│  ┌──────────────┬──────────┬──────────────┐ │
│  │   Lint       │ TypeCheck│    Tests     │ │
│  │  (Ruff)      │(Pyright) │   (Pytest)   │ │
│  └──────────────┴──────────┴──────────────┘ │
│              │              │
│              └──────────────┘
│                    │
│          ✅ Tests pass?
│                    │
│  ┌────────────────▼───────────────┐
│  │   Docker Build & Push          │
│  │   (Optional: Docker Hub)       │
│  └────────────────────────────────┘
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│         Production Deployment               │
│  ┌────────────────────────────────────────┐ │
│  │ Docker Container                       │ │
│  │ ┌──────────────┐    ┌──────────────┐  │ │
│  │ │ Cron Daemon  │    │ Admin Panel   │  │ │
│  │ │ (hh.ru jobs) │    │ (FastAPI)    │  │ │
│  │ └──────────────┘    └──────────────┘  │ │
│  └────────────────────────────────────────┘ │
│         + Volume mounts (config, logs)      │
└─────────────────────────────────────────────┘
```

## 📦 Структура файлов

```
.
├── .github/workflows/
│   ├── ci.yml              # ← NEW: CI pipeline (tests, lint, typecheck)
│   └── publish.yml         # Existing: PyPI publish
├── .pre-commit-config.yaml # ← NEW: Pre-commit hooks
├── Dockerfile              # Multi-stage build
├── docker-compose.yml
├── pyproject.toml          # Poetry dependencies
├── config/
│   ├── .gitkeep
│   └── config.example.yaml # ← NEW: Example config
├── src/hh_applicant_tool/
│   ├── main.py             # CLI entry point
│   ├── admin/              # FastAPI web admin
│   ├── operations/
│   ├── storage/
│   └── utils/
└── tests/                  # Pytest tests
```

## 🚀 Быстрый старт локально

### 1. Первая установка

```bash
# Клонируем репо
git clone <repo> && cd hh-applicant-tool

# Устанавливаем pre-commit hooks (опционально)
pip install pre-commit
pre-commit install

# Копируем example конфиги
cp config/config.example.yaml config/config.yaml
cp .env.example .env

# Заполняем свои значения (profile ID, пароли и т.д.)
nano .env
nano config/config.yaml
```

### 2. Локальная разработка с Docker

```bash
# Собираем образ
docker compose build

# Запускаем контейнер (crond + admin panel на port 8000)
docker compose up -d

# Смотрим логи
docker compose logs -f

# Проверяем health
curl http://localhost:8000/health

# Заходим в контейнер
docker compose exec hh_applicant_tool bash
```

### 3. Запуск тестов локально

```bash
# Без Docker (требует Python 3.11+)
poetry install
poetry run pytest tests/ -v

# С coverage
poetry run pytest tests/ -v --cov=src/hh_applicant_tool

# С Docker
docker compose run --rm hh_applicant_tool poetry run pytest tests/ -v
```

## 🔧 CI/CD Pipeline (GitHub Actions)

###触발(Trigger)

Pipeline запускается на:
- ✅ **Push** в `main` или `develop`
- ✅ **Pull Request** в `main` или `develop`
- ✅ **Tag push** формата `v*.*.*` (запускает publish в PyPI)

### Jobs

#### 1. `lint` - Проверка стиля кода
```bash
ruff check src/ tests/     # Основные правила PyCodeStyle + Pyflakes
isort --check-only src/    # Сортировка импортов
```

**Фиксирование локально:**
```bash
ruff check --fix src/
isort src/
poetry run pylint src/     # Дополнительная проверка
```

#### 2. `typecheck` - Проверка типов
```bash
basedpyright src/ tests/   # Основан на Microsoft Pyright
```

**Конфиг:** в `pyproject.toml` под `[tool.pyright]`

#### 3. `test` - Запуск тестов
- **Матрица версий:** Python 3.11, 3.12, 3.13
- **Framework:** pytest + coverage
- **Отправка метрик:** Codecov (опционально)

```bash
poetry run pytest tests/ -v --cov=src/hh_applicant_tool
```

#### 4. `build-docker` - Сборка Docker образа
- Использует Docker BuildKit для оптимизации слоёв
- Кэширует слои через GitHub Actions cache
- **Не пушит** в registry (только если явно настроишь)

## 🐳 Docker

### Структура Dockerfile (Multi-stage)

```
Stage 1: base
  ├─ Python 3.13-slim базовый образ
  ├─ Системные зависимости (gcc, cron, tzdata)
  └─ Создание непривилегированного пользователя `docker`

Stage 2: builder
  ├─ Копирование pyproject.toml
  ├─ Установка playwright + chromium браузер
  ├─ Установка зависимостей приложения
  └─ Pip кэшируется отдельно

Stage 3: runtime (финальный образ)
  ├─ Копирование только необходимого из builder
  ├─ Конфигурация крона
  ├─ Health check
  └─ Запуск как непривилегированный пользователь
```

**Размер:** ~2.5 GB (из-за Chromium в Playwright)

### Переменные окружения (в контейнере)

```env
HH_PROFILE_ID=xxxxx           # ✅ ОБЯЗАТЕЛЬНО
CONFIG_DIR=/app/config        # Where to read config files
LOG_DIR=/app/config           # Where to write logs
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
ADMIN_ENABLED=true            # Run FastAPI admin panel
ADMIN_USERNAME=admin          # Basic auth user
ADMIN_PASSWORD=change_me      # ⚠️ Change this!
TZ=Europe/Moscow              # Timezone
```

### docker-compose.yml

```yaml
services:
  hh_applicant_tool:
    image: hh_applicant_tool:latest
    environment:
      - CONFIG_DIR=/app/config
      - HH_PROFILE_ID=${HH_PROFILE_ID}          # Из .env
    volumes:
      - ./config:/app/config:rw                 # Конфиги & логи
      - /etc/localtime:/etc/localtime:ro        # Синхронизация времени
    restart: unless-stopped
    ports:
      - "8000:8000"                             # Admin panel
```

### Запуск в production

```bash
# Вариант 1: docker-compose (рекомендуется для простоты)
export HH_PROFILE_ID="12345"
docker-compose up -d

# Вариант 2: Docker только контейнер
docker run -d \
  --name hh-tool \
  -e HH_PROFILE_ID=12345 \
  -e ADMIN_PASSWORD="secure_password" \
  -e TZ=Europe/Moscow \
  -v /data/hh-config:/app/config \
  hh_applicant_tool:latest

# Проверка статуса
docker compose ps
docker compose logs hh_applicant_tool

# Остановка
docker compose down
```

## ⚙️ Конфигурация

### Способы конфигурации (приоритет)

1. **Environment variables** - самый высокий приоритет
   ```bash
   export HH_PROFILE_ID=12345
   export LOG_LEVEL=DEBUG
   ```

2. **config/config.yaml** - основной конфиг
   ```yaml
   hh:
     profile_id: "12345"
     delays:
       between_applies: 5
   ```

3. **Defaults в коде** - если ничего не задано
   ```python
   DEFAULT_PROFILE_ID = os.getenv("HH_PROFILE_ID")
   ```

### Полный пример конфига

Смотрите `config/config.example.yaml`

## 📊 Monitoring & Logs

### Где логи?

```
Внутри контейнера:
  /app/config/app.log         # Основные логи приложения
  Также stdout/stderr → docker logs

На хосте (если volume примонтирован):
  ./config/app.log            # Синхронизированные логи
```

### Health Check

```bash
# Admin panel должна отвечать на /health
curl http://localhost:8000/health

# Ответ:
# {"status": "healthy", "timestamp": "2026-04-16T10:00:00Z"}
```

## 🔐 Security Best Practices

```bash
# ❌ НЕТ
docker run -e HH_PROFILE_ID=12345 -e ADMIN_PASSWORD=admin ...

# ✅ ДА
# 1. Использовать .env файл (в .gitignore)
cat > .env <<EOF
HH_PROFILE_ID=12345
ADMIN_PASSWORD=$(openssl rand -base64 16)
EOF

# 2. Использовать secrets (для production)
docker run --env-file .env ...

# 3. Непривилегированный пользователь (уже в Dockerfile)
# 4. Читай-только volumes где возможно
docker run -v config/:/app/config:ro ...
```

## 📝 Pre-commit Hooks

Локально перед commit'ом автоматически:
- Форматирует код (ruff)
- Сортирует импорты (isort)
- Проверяет YAML/JSON
- Удаляет trailing whitespace

```bash
# Первая установка
pre-commit install

# Ручной запуск на всех файлах
pre-commit run --all-files

# Пропустить (если нужно срочно)
git commit --no-verify
```

## 🚢 Deployment Pipeline

### На VPS/Server

```bash
# 1. SSH на сервер
ssh user@server.com

# 2. Склонировать репо
cd /opt/apps
git clone <repo> hh-applicant-tool
cd hh-applicant-tool

# 3. Подготовить окружение
cp .env.example .env
nano .env  # Заполнить HH_PROFILE_ID и пароль

cp config/config.example.yaml config/config.yaml
nano config/config.yaml

# 4. Запустить
docker-compose up -d

# 5. Проверить
docker-compose logs -f
```

### CI/CD с push в Docker Registry (если настроишь)

```yaml
# В .github/workflows/ci.yml добавить:
- name: Push to DockerHub
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  uses: docker/build-push-action@v5
  with:
    push: true
    tags: your-org/hh-applicant-tool:latest
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}
```

## ✅ Checklist перед production

- [ ] Изменен пароль admin в `.env`
- [ ] Добавлен `HH_PROFILE_ID` в `.env`
- [ ] Заполнен `config/config.yaml`
- [ ] `.env` и `config/config.yaml` в `.gitignore` ✅ (уже есть)
- [ ] Все тесты проходят: `poetry run pytest tests/`
- [ ] Нет warning'ов от ruff и mypy
- [ ] Проверен цронгер в `crontab` файле
- [ ] Настроен volume mount для `/app/config` (для persistence)
- [ ] Проверен health check: `curl localhost:8000/health`

## 🛠️ Troubleshooting

### Контейнер крашит при старте

```bash
# Смотрим логи
docker compose logs -f

# Проверяем, что HH_PROFILE_ID установлен
docker compose exec hh_applicant_tool env | grep HH_PROFILE_ID

# Пересобираем образ
docker compose down
docker compose build --no-cache
docker compose up
```

### Crond не запускается

```bash
# Проверяем crontab в контейнере
docker compose exec hh_applicant_tool crontab -l

# Собираем логи crond
docker compose logs | grep cron
```

### Admin panel недоступна

```bash
# Проверяем, что она запущена
docker compose exec hh_applicant_tool ps aux | grep admin

# Проверяем port
docker compose exec hh_applicant_tool ss -lntp | grep 8000

# Проверяем с самого контейнера
docker compose exec hh_applicant_tool curl localhost:8000/health
```

---

## Дальго разработка & улучшения

1. **Kubernetes** - если нужен orchestration для multiple instances
2. **Prometheus + Grafana** - мониторинг метрик
3. **Sentry** - трекинг ошибок в production
4. **Slack/Telegram alerts** - оповещения при ошибках
5. **Database persistence** - сейчас используется SQLite в volume
6. **API authentication** - сейчас Basic Auth, можно добавить JWT/OAuth
