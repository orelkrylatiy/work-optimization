# Механизм инициализации авторизации

## Описание

При первом запуске любой операции, требующей авторизации, приложение автоматически:

1. **Проверяет наличие токенов** — ищет `access_token` в конфиге
2. **Пытается обновить через refresh_token** — если есть refresh_token, пытается получить новый access_token
3. **Предлагает авторизацию** — если токены отсутствуют, предлагает пользователю авторизоваться через Playwright

## Как это работает

### Проверка авторизации в методе `run()`

```python
# Список операций, которые НЕ требуют авторизации
no_auth_operations = {
    "authorize", "authenticate", "auth", "login",
    "config", "settings", "install", "uninstall",
    "migrate-db", "log"
}

# Для всех остальных операций:
if needs_auth and not self.api_client.access_token:
    # Пытаемся обновить через refresh_token
    # Если не получилось - запускаем процесс авторизации
```

### Входные точки для авторизации

Авторизация может быть инициирована:

1. **Автоматически перед операцией** — если нет токена
2. **Явно пользователем** — команда `authorize` или `auth`
3. **Через refresh_token** — если он есть в конфиге

## Примеры использования

### Первый запуск (нет токенов)

```bash
$ hh-applicant-tool apply-vacancies
⚠️  Требуется авторизация для работы приложения
======================================================

Перед запуском основной операции необходимо авторизоваться.
Будет открыт браузер для ввода учетных данных HH.ru.

Хотите авторизоваться сейчас? (y/n): y

# Откроется браузер для входа в HH.ru
# После входа токен будет сохранен в конфиге
```

### Повторный запуск (токен истек)

```bash
$ hh-applicant-tool apply-vacancies

# Приложение автоматически обновит токен через refresh_token
# и продолжит выполнение операции
```

### Явная авторизация

```bash
$ hh-applicant-tool authorize
$ hh-applicant-tool auth      # алиас
$ hh-applicant-tool login     # алиас
```

## Сохранение токенов

После успешной авторизации токены сохраняются в:

- **Linux/Mac**: `~/.config/hh-applicant-tool/config.json`
- **Windows**: `%APPDATA%\hh-applicant-tool\config.json`
- **Docker** (с volume): `/home/docker/.config/hh-applicant-tool/config.json`

Структура конфига:

```json
{
  "token": {
    "access_token": "USER...",
    "refresh_token": "...",
    "access_expires_at": 1234567890
  },
  "client_id": "...",
  "client_secret": "..."
}
```

## Для Docker

### Вариант 1: Volume с конфигом

```bash
docker run -v ~/.config/hh-applicant-tool:/home/docker/.config/hh-applicant-tool \
  hh-applicant-tool apply-vacancies
```

### Вариант 2: Инициализация при первом запуске

```bash
docker run -it hh-applicant-tool authorize

# Потом обычный запуск:
docker run -v ~/.config/hh-applicant-tool:/home/docker/.config/hh-applicant-tool \
  hh-applicant-tool apply-vacancies
```

### Вариант 3: Передача токенов через ENV (опционально - требует расширения)

Можно добавить поддержку подобно:

```bash
docker run -e HH_ACCESS_TOKEN="..." \
  -e HH_REFRESH_TOKEN="..." \
  hh-applicant-tool apply-vacancies
```

## Переменные окружения для CONFIG_DIR

В Docker используется `CONFIG_DIR=/app/config` по умолчанию (из `.env.example`).

Для использования custom конфига:

```bash
docker run -e CONFIG_DIR=/custom/config \
  -v ~/.config/hh-applicant-tool:/custom/config \
  hh-applicant-tool apply-vacancies
```

## Обработка ошибок

- **Ошибка 403 при refresh_token** — автоматически инициирует полную авторизацию
- **Пользователь отказывает авторизацию** — операция отменяется с кодом `1`
- **Ошибка при авторизации** — выводится сообщение об ошибке, попробуйте снова

## Операции, не требующие авторизации

### Без авторизации вообще
- `authorize` / `auth` / `login` / `authenticate` — сам процесс авторизации
- `config` — управление конфигом
- `settings` — параметры приложения
- `log` — просмотр логов
- `install` / `uninstall` — установка/удаление
- `migrate-db` — миграция базы данных

### Требуют авторизации, но без инициализации браузера
Эти операции требуют токена, но при его отсутствии выводят ошибку вместо открытия браузера:
- `whoami` / `id` — проверка текущего пользователя (быстрая диагностика)

**Использование для проверки авторизации:**
```bash
$ hh-applicant-tool whoami
# Если токена нет → Требуется авторизация. Запустите: hh-applicant-tool authorize

$ hh-applicant-tool authorize  # → Открывается браузер для входа
```
