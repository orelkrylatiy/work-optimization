# HH Applicant Tool — Руководство для AI агента

Этот документ описывает как AI агент (Claude или другой) должен работать с инструментом автономно: запускать отклики, отвечать на сообщения от работодателей, управлять токенами.

Базовый URL панели: `http://127.0.0.1:8000`

---

## Что агент может делать самостоятельно

| Задача | Возможно? | Примечание |
|---|---|---|
| Запустить рассылку откликов | ✅ | Через `/api/agent/run` |
| Отправить сопроводительное письмо | ✅ | AI генерирует через OpenAI |
| Обновить резюме | ✅ | Поднимает в поиске |
| Проверить и ответить на сообщения | ✅ | Через `/api/inbox` |
| Обновить токен (refresh) | ✅ | Автоматически при истечении |
| Первичная авторизация (новый аккаунт) | ❌ | Требует SMS-код от человека |

**Единственное что требует человека:** первый вход в аккаунт. После этого агент работает полностью автономно.

---

## Шаг 0 — Первичная авторизация (один раз, руками)

Выполняется один раз при настройке аккаунта:

```bash
python -m hh_applicant_tool auth
# Откроется браузер → войти на hh.ru → ввести SMS-код
# После этого токен сохраняется и агент не нужна помощь
```

После этого шага агент сам обновляет токен через `refresh_token` при необходимости.

---

## Шаг 1 — Pre-flight проверка (всегда перед операцией)

Перед любой операцией агент обязан проверить готовность:

```
GET /api/agent/preflight?profile=default
```

Ответ:
```json
{
  "ready": true,
  "action": "run",
  "token_status": "ok",
  "token_expires_in": 85200,
  "can_refresh": true,
  "needs_reauth": false,
  "needs_refresh": false
}
```

**Что делать по значению `action`:**

| `action` | Что сделать |
|---|---|
| `run` | Запускать операцию немедленно |
| `refresh` | Токен истёк, нужен refresh (агент справится сам через `/api/agent/run` с `auto_refresh: true`) |
| `reauth` | Нет токена → уведомить человека, самому не продолжать |

---

## Шаг 2 — Запуск откликов с сопроводительными письмами

### Простой запуск (рекомендуется)

```
POST /api/agent/run
```

```json
{
  "profile": "default",
  "operation": "apply-vacancies",
  "auto_refresh": true,
  "args": [
    "--search", "Python разработчик",
    "--force-message",
    "--use-ai",
    "--ai-filter", "light",
    "--skip-tests",
    "--max-responses", "50",
    "--response-delay", "2-5"
  ]
}
```

**Ключевые параметры для максимальной конверсии:**

| Параметр | Значение | Смысл |
|---|---|---|
| `--force-message` | флаг | Всегда прикреплять сопроводительное письмо |
| `--use-ai` | флаг | Генерировать письмо через OpenAI под каждую вакансию |
| `--ai-filter light` | строка | AI отсеивает явно неподходящие вакансии |
| `--skip-tests` | флаг | Пропускать вакансии с тестовыми заданиями |
| `--response-delay 2-5` | строка | Случайная пауза 2–5 сек между откликами (защита от бана) |
| `--max-responses 50` | число | Ограничение за один прогон |

### Расширенный запуск (с фильтрами)

```json
{
  "profile": "default",
  "operation": "apply-vacancies",
  "auto_refresh": true,
  "args": [
    "--search", "Backend developer",
    "--experience", "between3And6",
    "--schedule", "remote",
    "--salary", "150000",
    "--only-with-salary",
    "--force-message",
    "--use-ai",
    "--ai-filter", "heavy",
    "--skip-tests",
    "--max-responses", "30",
    "--response-delay", "3-7",
    "--area", "1",
    "--area", "2"
  ]
}
```

Значения для `--experience`: `noExperience`, `between1And3`, `between3And6`, `moreThan6`  
Значения для `--schedule`: `remote`, `fullDay`, `flexible`, `shift`  
Коды `--area`: `1` = Москва, `2` = Санкт-Петербург

### Ответ и ожидание результата

```json
{
  "op_id": "a3f2c1b0",
  "stdout": "Операция запущена в фоне...",
  "refreshed_token": false,
  "token_status": "ok"
}
```

Далее агент опрашивает статус каждые 10–15 секунд:

```
GET /api/operation-status/a3f2c1b0
```

Пока работает:
```json
{ "op_id": "a3f2c1b0", "running": true, "pid": 12345 }
```

После завершения:
```json
{
  "op_id": "a3f2c1b0",
  "running": false,
  "returncode": 0,
  "stdout": "✅️ Закончили рассылку откликов для резюме: Python разработчик\n...",
  "stderr": ""
}
```

---

## Шаг 3 — Обновление резюме (поднять в поиске)

```
POST /api/agent/run
```

```json
{
  "profile": "default",
  "operation": "update-resumes",
  "auto_refresh": true
}
```

Рекомендуется запускать раз в 4 часа (резюме поднимается в поиске).

---

## Шаг 4 — Итеративная работа с входящими сообщениями

Это **ключевая задача для регулярного запуска** (раз в 15–30 минут). Работодатели отвечают в разное время, поэтому нужен цикл.

### 4.1 — Получить список переписок

```
GET /api/inbox?profile=default&per_page=20
```

Фильтры статуса: `active`, `invitation` (приглашение), `phone_interview`, `discard` (отказ)

```json
{
  "items": [
    {
      "id": 123456,
      "state": "active",
      "state_name": "Активный отклик",
      "vacancy_name": "Python разработчик",
      "employer_name": "ООО Рога и Копыта",
      "has_updates": true,
      "viewed_by_opponent": true
    }
  ],
  "found": 12
}
```

### 4.2 — Читать сообщения переписки где `has_updates: true`

```
GET /api/inbox/123456/messages?profile=default
```

```json
{
  "messages": [
    {
      "id": 789,
      "text": "Здравствуйте! Хотели бы пригласить вас на собеседование...",
      "created_at": "2025-04-24T10:30:00",
      "is_employer": true,
      "author_name": "Мария Иванова"
    },
    {
      "id": 788,
      "text": "Добрый день! Направляю резюме...",
      "is_employer": false
    }
  ]
}
```

### 4.3 — Отправить ответ (AI или вручную)

**Вариант A — AI генерирует ответ:**

```
POST /api/inbox/123456/reply
```

```json
{
  "profile": "default",
  "message": "",
  "use_ai": true,
  "vacancy_name": "Python разработчик",
  "employer_name": "ООО Рога и Копыта"
}
```

**Вариант B — конкретный текст:**

```json
{
  "profile": "default",
  "message": "Здравствуйте! Спасибо за приглашение. Готов обсудить детали — когда вам удобно?"
}
```

### 4.4 — Алгоритм итеративного обхода (псевдокод)

```
каждые 20-30 минут:
  1. GET /api/agent/preflight → проверить токен
  2. GET /api/inbox?profile=default&per_page=50
  3. для каждого item где has_updates == true:
       a. GET /api/inbox/{id}/messages
       b. найти последнее сообщение от работодателя (is_employer=true)
       c. если оно новее последнего ответа нашего (is_employer=false):
            POST /api/inbox/{id}/reply { use_ai: true, ... }
  4. GET /api/inbox?status=discard — если много отказов:
       POST /api/inbox/clear-rejections → убрать из активных
```

---

## Шаг 5 — Управление токеном

### Проверка без сетевых запросов

```
GET /api/token-status?profile=default
```

```json
{
  "status": "ok",
  "expires_in_seconds": 85200,
  "can_refresh": true,
  "has_refresh_token": true
}
```

Статусы: `ok`, `expired`, `no_token`, `no_config`

### Если `status == "expired"` — обновить вручную

```
POST /api/agent/run
{ "profile": "default", "operation": "refresh-token", "auto_refresh": false }
```

Или просто запустить любую операцию с `auto_refresh: true` — панель обновит токен автоматически.

### Если `status == "no_token"` — нужен человек

Агент должен остановиться и уведомить: *"Требуется авторизация. Запустите `python -m hh_applicant_tool auth` в терминале."*

---

## Полный рабочий цикл агента (рекомендуемый)

```
[каждые 4 часа]
  1. preflight → ok?
  2. update-resumes (поднять резюме)
  3. apply-vacancies --force-message --use-ai (новые отклики)

[каждые 20-30 минут]
  1. preflight → ok?
  2. проверить inbox на новые сообщения
  3. ответить на сообщения от работодателей через AI
  4. если много отказов — clear-rejections

[при получении invitation/phone_interview]
  → ответить немедленно, зафиксировать
```

---

## Работа с несколькими профилями

Все endpoint-ы принимают `?profile=<name>` или поле `profile` в теле.

```
GET /api/profiles
→ { "profiles": ["default", "senior-dev", "freelance"] }
```

Для каждого профиля — отдельный токен, база данных, настройки. Операции выполняются независимо.

---

## Обработка ошибок

| HTTP код | Причина | Действие агента |
|---|---|---|
| `401` | Нет токена или истёк без refresh | Уведомить человека о необходимости авторизации |
| `400` | Неверные параметры | Исправить запрос |
| `502` | Не удалось обновить токен | То же — уведомить человека |
| `504` | Таймаут операции | Повторить позже |
| `returncode != 0` в operation-status | Ошибка CLI | Проверить `stderr` для диагностики |

---

## Настройка OpenAI для писем и ответов

Чтобы AI генерировал сопроводительные письма и ответы, в `config.json` профиля должно быть:

```json
{
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1"
  }
}
```

Обновить через API:

```
PUT /api/config?profile=default
{ "data": { "openai": { "api_key": "sk-...", "model": "gpt-4o-mini" } } }
```

Поддерживаются любые OpenAI-совместимые API (LM Studio, Ollama с OpenAI-proxy, Together AI и т.д.).

---

## Быстрая сводка endpoint-ов для агента

```
GET  /api/agent/preflight?profile=   # проверить готовность
POST /api/agent/run                  # запустить операцию
GET  /api/token-status?profile=      # статус токена
GET  /api/operation-status/{op_id}   # статус фоновой операции
GET  /api/inbox?profile=             # список переписок
GET  /api/inbox/{id}/messages        # сообщения переписки
POST /api/inbox/{id}/reply           # отправить ответ
POST /api/inbox/clear-rejections     # убрать отказы
GET  /api/profiles                   # список профилей
GET  /api/stats?profile=             # статистика откликов
```
