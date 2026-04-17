# ðŸš€ Ð‘Ñ‹ÑÑ‚Ñ€Ð°Ñ ÑˆÐ¿Ð°Ñ€Ð³Ð°Ð»ÐºÐ° DevOps

## Ð—Ð°Ð¿ÑƒÑÐº Ð»Ð¾ÐºÐ°Ð»ÑŒÐ½Ð¾ (5 Ð¼Ð¸Ð½ÑƒÑ‚)

```bash
# 1. ÐšÐ»Ð¾Ð½ + ÑƒÑÑ‚Ð°Ð½Ð¾Ð²ÐºÐ°
git clone <repo> && cd hh-applicant-tool
make setup-config        # Ð¡Ð¾Ð·Ð´Ð°ÐµÑ‚ .env Ð¸ config/config.yaml

# 2. Ð—Ð°Ð¿Ð¾Ð»Ð½Ð¸ ÑÐ²Ð¾Ð¸ Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ñ
nano .env               # Ð”Ð¾Ð±Ð°Ð²ÑŒ ÑÐ²Ð¾Ð¹ HH_PROFILE_ID
nano config/config.yaml

# 3. Ð—Ð°Ð¿ÑƒÑÑ‚Ð¸ Ð² Docker
make docker-build       # Ð¡Ð¾Ð±Ð¸Ñ€Ð°ÐµÐ¼ Ð¾Ð±Ñ€Ð°Ð·
make docker-run         # Ð¡Ñ‚Ð°Ñ€Ñ‚ÑƒÐµÐ¼ ÐºÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€

# 4. ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ
make docker-logs        # Ð¡Ð¼Ð¾Ñ‚Ñ€Ð¸Ð¼ Ð»Ð¾Ð³Ð¸
curl http://localhost:8000/health  # Admin Ð¿Ð°Ð½ÐµÐ»ÑŒ Ñ€Ð°Ð±Ð¾Ñ‚Ð°ÐµÑ‚?
```

---

## Ð Ð°Ð·Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ° (Ð±ÐµÐ· Docker)

```bash
# ÐŸÐµÑ€Ð²Ñ‹Ð¹ Ñ€Ð°Ð·
poetry install --with dev
pre-commit install

# Ð—Ð°Ð¿ÑƒÑÐº Ñ‚ÐµÑÑ‚Ð¾Ð²
make test               # Ð‘Ñ‹ÑÑ‚Ñ€Ð°Ñ Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐºÐ°
make test-cov           # Ð¡ coverage Ð¾Ñ‚Ñ‡ÐµÑ‚Ð¾Ð¼

# ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° ÐºÐ°Ñ‡ÐµÑÑ‚Ð²Ð°
make lint               # Ð’ÑÐµ style checks
make format             # Auto-fix Ð¿Ñ€Ð¾Ð±Ð»ÐµÐ¼Ñ‹
make typecheck          # ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ñ‚Ð¸Ð¿Ð¾Ð²

# Ð—Ð°Ð¿ÑƒÑÐº Ð²ÑÐµÐ³Ð¾ CI locally
make ci                 # lint + typecheck + test
```

---

## GitHub Actions (Ð°Ð²Ñ‚Ð¾Ð¼Ð°Ñ‚Ð¸Ñ‡ÐµÑÐºÐ¸)

### ÐŸÑ€Ð¸ Push/PR Ð² main:

```
âœ… Lint (ruff, isort)
âœ… Type Check (pyright)
âœ… Tests (pytest Ð½Ð° 3 Ð²ÐµÑ€ÑÐ¸ÑÑ… Python)
âœ… Build Docker (Ð±ÐµÐ· push)
```

**Ð•ÑÐ»Ð¸ CI fails:**
```bash
# Ð›Ð¾ÐºÐ°Ð»ÑŒÐ½Ð¾ ÑÐºÐ¾Ð¿Ð¸Ñ€ÑƒÐ¹ Ð¾ÑˆÐ¸Ð±ÐºÑƒ Ð¸ Ð·Ð°Ð¿ÑƒÑÑ‚Ð¸:
make lint     # Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ð¸Ñ€ÑƒÐ¹
make format   # Auto-fix
make ci       # ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ Ð²ÑÑ‘ ÐµÑ‰Ñ‘ Ñ€Ð°Ð·
```

---

## Production Deployment

### Ð¡Ð¿Ð¾ÑÐ¾Ð± 1: Docker Compose (Ð¿Ñ€Ð¾ÑÑ‚Ð¾Ð¹)

```bash
# ÐÐ° ÑÐµÑ€Ð²ÐµÑ€Ðµ:
cd /opt/apps
git clone <repo> hh-applicant-tool
cd hh-applicant-tool

# ÐŸÐ¾Ð´Ð³Ð¾Ñ‚Ð¾Ð²ÐºÐ°
cp .env.example .env
nano .env  # Ð—Ð°Ð¿Ð¾Ð»Ð½ÑÐµÐ¼ HH_PROFILE_ID Ð¸ ADMIN_PASSWORD

cp config/config.example.yaml config/config.yaml
nano config/config.yaml

# Ð—Ð°Ð¿ÑƒÑÐº
docker-compose up -d

# ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ°
docker-compose logs -f
curl http://localhost:8000/health
```

### Ð¡Ð¿Ð¾ÑÐ¾Ð± 2: Kubernetes (ÐµÑÐ»Ð¸ Ð½ÑƒÐ¶ÐµÐ½ Ð¼Ð°ÑÑˆÑ‚Ð°Ð±)

Ð‘ÑƒÐ´ÐµÑ‚ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾ Ð¿Ð¾Ð·Ð¶Ðµ. Ð¢Ñ€ÐµÐ±ÑƒÐµÑ‚ÑÑ:
- StatefulSet Ð´Ð»Ñ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸Ñ (SQLite volume)
- Service Ð´Ð»Ñ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°
- Ingress Ð´Ð»Ñ Ð²Ð½ÐµÑˆÐ½ÐµÐ³Ð¾ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°

---

## Ð¡Ñ‚Ñ€ÑƒÐºÑ‚ÑƒÑ€Ð° Ñ„Ð°Ð¹Ð»Ð¾Ð²

```
./.github/workflows/
â”œâ”€â”€ ci.yml ..................... CI pipeline (tests, lint)
â””â”€â”€ publish.yml ................ PyPI publish (Ð½Ð° tag)

./
â”œâ”€â”€ .env.example ............... "Credentials template"
â”œâ”€â”€ .env ........................ "Real credentials (Ð² .gitignore!)"
â”œâ”€â”€ Makefile ................... "Dev commands"
â”œâ”€â”€ Dockerfile ................. "Multi-stage build"
â”œâ”€â”€ docker-compose.yml ......... "Local dev setup"
â”œâ”€â”€ DEVOPS.md .................. "Full documentation"
â””â”€â”€ dev-setup.sh ............... "Quick setup script"

./config/
â”œâ”€â”€ config.example.yaml ........ "App config template"
â”œâ”€â”€ config.yaml ................ "Real config (Ð² .gitignore!)"
â”œâ”€â”€ app.log .................... "Logs (volume mount)"
â””â”€â”€ .gitkeep

./src/hh_applicant_tool/
â””â”€â”€ admin/app.py ............... "FastAPI Ð°Ð´Ð¼Ð¸Ð½ Ð¿Ð°Ð½ÐµÐ»ÑŒ" â†’ :8000

./tests/
â”œâ”€â”€ conftest.py
â””â”€â”€ test_*.py .................. "Pytest Ñ‚ÐµÑÑ‚Ñ‹"
```

---

## ÐŸÐµÑ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ðµ Ð¾ÐºÑ€ÑƒÐ¶ÐµÐ½Ð¸Ñ

| Variable | Default | ÐžÐ±ÑÐ·Ð°Ñ‚ÐµÐ»ÑŒÐ½Ñ‹Ð¹ | ÐžÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ |
|----------|---------|-------------|---------|
| `HH_PROFILE_ID` | - | âœ… YES | Ð¢Ð²Ð¾Ð¹ ID Ð¿Ñ€Ð¾Ñ„Ð¸Ð»Ñ Ð½Ð° hh.ru |
| `CONFIG_DIR` | `/app/config` | ÐÐµÑ‚ | ÐŸÐ°Ð¿ÐºÐ° ÐºÐ¾Ð½Ñ„Ð¸Ð³Ð¾Ð² |
| `LOG_LEVEL` | `INFO` | ÐÐµÑ‚ | DEBUG/INFO/WARNING/ERROR |
| `ADMIN_ENABLED` | `true` | ÐÐµÑ‚ | Ð—Ð°Ð¿ÑƒÑÐºÐ°Ñ‚ÑŒ Ð»Ð¸ Ð°Ð´Ð¼Ð¸Ð½ Ð¿Ð°Ð½ÐµÐ»ÑŒ? |
| `ADMIN_PASSWORD` | `change_me` | âš ï¸ | ÐŸÐ¾Ð¼ÐµÐ½ÑÐ¹ Ð² production! |
| `TZ` | UTC | ÐÐµÑ‚ | Ð¢Ð°Ð¹Ð¼Ð·Ð¾Ð½Ð° (Europe/Moscow) |

Ð’ÑÐµ Ð² `.env` Ñ„Ð°Ð¹Ð»Ðµ!

---

## Ð—Ð´Ð¾Ñ€Ð¾Ð²ÑŒÐµ ÐºÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€Ð°

```bash
# Health check (Ð½ÑƒÐ¶Ð½Ð¾ Ð²Ð½ÑƒÑ‚Ñ€Ð¸ ÐºÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€Ð° Ð¸Ð»Ð¸ localhost ÐµÑÐ»Ð¸ Ð¸Ð·Ð¾Ð»Ð¸Ñ€Ð¾Ð²Ð°Ð½)
curl http://localhost:8000/health

# Admin Ð¿Ð°Ð½ÐµÐ»ÑŒ
http://localhost:8000/
# Ð›Ð¾Ð³Ð¸Ð½: admin@admin.com
# ÐŸÐ°Ñ€Ð¾Ð»ÑŒ: Ð¸Ð· ADMIN_PASSWORD Ð² .env
```

---

## Ð•ÑÐ»Ð¸ Ñ‡Ñ‚Ð¾-Ñ‚Ð¾ ÑÐ»Ð¾Ð¼Ð°Ð»Ð¾ÑÑŒ

| ÐŸÑ€Ð¾Ð±Ð»ÐµÐ¼Ð° | Ð ÐµÑˆÐµÐ½Ð¸Ðµ |
|----------|---------|
| ÐšÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€ Ð½Ðµ ÑÑ‚Ð°Ñ€Ñ‚ÑƒÐµÑ‚ | `docker-compose logs` + ÑÐ¼Ð¾Ñ‚Ñ€Ð¸ Ð¾ÑˆÐ¸Ð±ÐºÑƒ |
| Tests Ð½Ðµ Ð¿Ñ€Ð¾Ñ…Ð¾Ð´ÑÑ‚ Ð»Ð¾ÐºÐ°Ð»ÑŒÐ½Ð¾ | `make format` + `make lint` |
| Git commit fails | `pre-commit run --all-files` |
| Docker Ð½Ðµ ÑÐ¾Ð±Ð¸Ñ€Ð°ÐµÑ‚ÑÑ | `docker compose build --no-cache` |
| Admin Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð° | ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ `docker-compose ps` + `docker-compose logs` |
| Config Ð½Ðµ Ð·Ð°Ð³Ñ€ÑƒÐ¶Ð°ÐµÑ‚ÑÑ | ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ path Ð² DEVOPS.md â†’ ÐšÐ¾Ð½Ñ„Ð¸Ð³ÑƒÑ€Ð°Ñ†Ð¸Ñ |

---

## Ð”Ð°Ð»ÑŒÐ½ÐµÐ¹ÑˆÐ¸Ðµ ÑƒÐ»ÑƒÑ‡ÑˆÐµÐ½Ð¸Ñ

- ðŸ“Š Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ Prometheus Ð¼ÐµÑ‚Ñ€Ð¸ÐºÐ¸
- ðŸ”” Slack/Telegram alerts Ð¿Ñ€Ð¸ Ð¾ÑˆÐ¸Ð±ÐºÐ°Ñ…
- ðŸ³ Push Ð² Docker Hub (CI job)
- â˜¸ï¸  Kubernetes deployment
- ðŸ“ API docs (Swagger)
- ðŸ” OAuth Ð²Ð¼ÐµÑÑ‚Ð¾ Basic Auth

---

> **Pro Tip:** Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹ `make help` Ñ‡Ñ‚Ð¾Ð±Ñ‹ ÑƒÐ²Ð¸Ð´ÐµÑ‚ÑŒ Ð²ÑÐµ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹!
