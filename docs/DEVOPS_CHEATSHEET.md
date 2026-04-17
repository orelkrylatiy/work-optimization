# 🚀 Быстрая шпаргалка DevOps

## Запуск локально (5 минут)

```bash
# 1. Клон + установка
git clone <repo> && cd hh-applicant-tool
make setup-config        # Создает .env и config/config.yaml

# 2. Заполни свои значения
nano .env               # Добавь свой HH_PROFILE_ID
nano config/config.yaml

# 3. Запусти в Docker
make docker-build       # Собираем образ
make docker-run         # Стартуем контейнер

# 4. Проверь
make docker-logs        # Смотрим логи
curl http://localhost:8000/health  # Admin панель работает?
```

---

## Разработка (без Docker)

```bash
# Первый раз
poetry install --with dev
pre-commit install

# Запуск тестов
make test               # Быстрая проверка
make test-cov           # С coverage отчетом

# Проверка качества
make lint               # Все style checks
make format             # Auto-fix проблемы
make typecheck          # Проверка типов

# Запуск всего CI locally
make ci                 # lint + typecheck + test
```

---

## GitHub Actions (автоматически)

### При Push/PR в main:

```
✅ Lint (ruff, isort)
✅ Type Check (pyright)
✅ Tests (pytest на 3 версиях Python)
✅ Build Docker (без push)
```

**Если CI fails:**
```bash
# Локально скопируй ошибку и запусти:
make lint     # Сначала форматируй
make format   # Auto-fix
make ci       # Проверь всё ещё раз
```

---

## Production Deployment

### Способ 1: Docker Compose (простой)

```bash
# На сервере:
cd /opt/apps
git clone <repo> hh-applicant-tool
cd hh-applicant-tool

# Подготовка
cp .env.example .env
nano .env  # Заполняем HH_PROFILE_ID и ADMIN_PASSWORD

cp config/config.example.yaml config/config.yaml
nano config/config.yaml

# Запуск
docker-compose up -d

# Проверка
docker-compose logs -f
curl http://localhost:8000/health
```

### Способ 2: Kubernetes (если нужен масштаб)

Будет добавлено позже. Требуется:
- StatefulSet для состояния (SQLite volume)
- Service для доступа
- Ingress для внешнего доступа

---

## Структура файлов

```
./.github/workflows/
├── ci.yml ..................... CI pipeline (tests, lint)
└── publish.yml ................ PyPI publish (на tag)

./                          
├── .env.example ............... "Credentials template"
├── .env ........................ "Real credentials (в .gitignore!)"
├── Makefile ................... "Dev commands"
├── Dockerfile ................. "Multi-stage build"
├── docker-compose.yml ......... "Local dev setup"
├── DEVOPS.md .................. "Full documentation"
└── dev-setup.sh ............... "Quick setup script"

./config/
├── config.example.yaml ........ "App config template"
├── config.yaml ................ "Real config (в .gitignore!)"
├── app.log .................... "Logs (volume mount)"
└── .gitkeep

./src/hh_applicant_tool/
└── admin/app.py ............... "FastAPI админ панель" → :8000

./tests/
├── conftest.py
└── test_*.py .................. "Pytest тесты"
```

---

## Переменные окружения

| Variable | Default | Обязательный | Описание |
|----------|---------|-------------|---------|
| `HH_PROFILE_ID` | - | ✅ YES | Твой ID профиля на hh.ru |
| `CONFIG_DIR` | `/app/config` | Нет | Папка конфигов |
| `LOG_LEVEL` | `INFO` | Нет | DEBUG/INFO/WARNING/ERROR |
| `ADMIN_ENABLED` | `true` | Нет | Запускать ли админ панель? |
| `ADMIN_PASSWORD` | `change_me` | ⚠️ | Поменяй в production! |
| `TZ` | UTC | Нет | Таймзона (Europe/Moscow) |

Все в `.env` файле!

---

## Здоровье контейнера

```bash
# Health check (нужно внутри контейнера или localhost если изолирован)
curl http://localhost:8000/health

# Admin панель
http://localhost:8000/
# Логин: admin@admin.com
# Пароль: из ADMIN_PASSWORD в .env
```

---

## Если что-то сломалось

| Проблема | Решение |
|----------|---------|
| Контейнер не стартует | `docker-compose logs` + смотри ошибку |
| Tests не проходят локально | `make format` + `make lint` |
| Git commit fails | `pre-commit run --all-files` |
| Docker не собирается | `docker compose build --no-cache` |
| Admin недоступна | Проверь `docker-compose ps` + `docker-compose logs` |
| Config не загружается | Проверь path в DEVOPS.md → Конфигурация |

---

## Дальнейшие улучшения

- 📊 Добавить Prometheus метрики
- 🔔 Slack/Telegram alerts при ошибках
- 🐳 Push в Docker Hub (CI job)
- ☸️  Kubernetes deployment
- 📝 API docs (Swagger)
- 🔐 OAuth вместо Basic Auth

---

> **Pro Tip:** Используй `make help` чтобы увидеть все команды!
