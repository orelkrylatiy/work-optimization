# Скрипты автоматизации HH.ru

## 📋 Доступные скрипты

| Скрипт | Описание | Команда |
|--------|----------|---------|
| `check.sh` | Проверка состояния аккаунта | `./scripts/check.sh` |
| `apply.sh` | Отклики на вакансии | `./scripts/apply.sh` |
| `reply.sh` | Ответы работодателям (AI) | `./scripts/reply.sh` |
| `daily.sh` | Полный ежедневный workflow | `./scripts/daily.sh` |
| `all-profiles.sh` | Параллельный запуск по всем профилям | `./scripts/all-profiles.sh daily` |

---

## 🚀 Быстрый старт

### 1. Проверка состояния
```bash
./scripts/check.sh
```

### 2. Отклики на вакансии
```bash
# Пробный запуск (без отправки)
./scripts/apply.sh --dry-run

# Live запуск
./scripts/apply.sh
```

### 3. Ответы работодателям
```bash
# Пробный запуск
./scripts/reply.sh --dry-run

# Live запуск (6 итераций по 50 чатов)
./scripts/reply.sh
```

### 4. Полный ежедневный workflow
```bash
# Всё сразу: резюме + отклики + ответы
./scripts/daily.sh

# Только безопасная проверка, без последующего live
./scripts/daily.sh --dry-run
```

### 5. Несколько профилей сразу
```bash
# .profiles в корне проекта:
# default
# account2

./scripts/all-profiles.sh reply
./scripts/all-profiles.sh apply
./scripts/all-profiles.sh daily
./scripts/all-profiles.sh reply --dry-run
```

Без `.profiles` используется один основной профиль `default`. Логи пишутся в
`/tmp/hh-profiles/<profile>-<command>.log`.

---

## 📖 Подробная документация

### `check.sh` — Проверка состояния

Проверяет авторизацию, резюме, активные переговоры и Ollama.

```bash
./scripts/check.sh
```

**Что проверяет:**
- ✅ Авторизация на HH.ru
- ✅ Список резюме и их статус
- ✅ Активные переговоры (последние 5)
- ✅ Ollama и модели
- ✅ Доступность скриптов

---

### `apply.sh` — Отклики на вакансии

**Базовое использование:**
```bash
./scripts/apply.sh [--dry-run] [--search "QUERY"] [--limit N]
```

**Опции:**
- `--dry-run` — пробный запуск без отправки
- `--search "QUERY"` — поисковый запрос (по умолчанию: "Frontend разработчик")
- `--limit N` — лимит вакансий (по умолчанию: 100)
- `--system-prompt FILE` — системный промпт для AI
- `--excluded-filter` — фильтр исключений (regex)

**Примеры:**
```bash
# Dry-run
./scripts/apply.sh --dry-run

# Свой поисковый запрос
./scripts/apply.sh --search "React TypeScript"

# Больше вакансий
./scripts/apply.sh --limit 200

# Только удалёнка
./scripts/apply.sh --search "Frontend remote"
```

**Переменные окружения:**
```bash
SEARCH_QUERY="React Developer" ./scripts/apply.sh
LIMIT=200 ./scripts/apply.sh
```

---

### `reply.sh` — Ответы работодателям (AI)

Итеративные AI-ответы с анализом истории переписки.

**Базовое использование:**
```bash
./scripts/reply.sh [--dry-run] [--iterations N] [--chats N]
```

**Опции:**
- `--dry-run` — пробный запуск без отправки
- `--iterations N` — максимум итераций (по умолчанию: 6)
- `--chats N` — чатов за итерацию (по умолчанию: 50)
- `--telegram @USER` — Telegram для связи (по умолчанию: `HH_TELEGRAM` из `.env`)

**Примеры:**
```bash
# Dry-run
./scripts/reply.sh --dry-run

# Меньше итераций
./scripts/reply.sh --iterations 3

# Больше чатов за итерацию
./scripts/reply.sh --chats 100
```

**Что делает:**
- 5-6 итераций по 50 чатов
- Генерирует ответы через AI-провайдер из `config.json`
- Анализирует историю переписки
- Rate limiting: 2 сек между запросами
- Пауза 2 мин между итерациями

---

### `daily.sh` — Полный ежедневный workflow

Автоматизирует весь ежедневный процесс.

**Базовое использование:**
```bash
./scripts/daily.sh [--apply-only] [--reply-only] [--full] [--dry-run]
```

**Опции:**
- `--apply-only` — только отклики
- `--reply-only` — только ответы
- `--full` — полный workflow с dry-run сначала
- `--dry-run` — только dry-run, без live-действий
- `--search` — поисковый запрос для откликов
- `--limit` — лимит вакансий

**Примеры:**
```bash
# Полный workflow
./scripts/daily.sh

# Только отклики
./scripts/daily.sh --apply-only

# Только ответы
./scripts/daily.sh --reply-only

# Полный с dry-run
./scripts/daily.sh --full
```

**Шаги полного workflow:**
1. **Подъём резюме** — `boost-resume`
2. **Отклики** — 80-120 вакансий
3. **Ответы** — 6 итераций по 50 чатов

---

## ⚙️ Настройка

### Переменные окружения

Можно настроить в `.env` или в shell profile:

```bash
# Имя и контакт для промптов
export HH_NAME="Максим"
export HH_TELEGRAM="@maxxwway"

# Поисковый запрос по умолчанию
export SEARCH_QUERY="Frontend React TypeScript"

# Лимит вакансий
export APPLY_LIMIT=150

# Итерации ответов
export REPLY_ITERATIONS=6
export REPLY_CHATS=50

# Telegram для связи (override)
export TELEGRAM="@maxxwway"
```

### Кастомизация фильтров

В `apply.sh` измените `EXCLUDED_FILTER`:
```bash
EXCLUDED_FILTER="junior|стажир|bitrix|web3|crypto|blockchain"
```

---

## 🔧 Troubleshooting

### "Требуется авторизация"
```bash
hh-applicant-tool authorize
```

### "Лимит откликов достигнут"
HH.ru ограничивает ~100-150 откликов в сутки. Подождите до завтра.

### "AI не генерирует текст"
```bash
python3 ./scripts/check_ai.py
```

---

## 📊 Рекомендуемый график

| Время | Задача | Команда |
|-------|--------|---------|
| 09:00 | Подъём резюме + отклики | `./scripts/daily.sh --apply-only` |
| 12:00 | Проверка ответов | `./scripts/check.sh` |
| 15:00 | Ответы работодателям | `./scripts/reply.sh` |
| 18:00 | Вечерние отклики | `./scripts/apply.sh --limit 50` |

---

## 📝 Логи

Все скрипты выводят подробную статистику:
- ✅ Успешные операции
- ⏭️ Пропущенные (не требуют ответа)
- 🚫 Отклонённые/закрытые
- ❌ Ошибки с деталями
