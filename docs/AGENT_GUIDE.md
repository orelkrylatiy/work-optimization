# HH Applicant Tool — Руководство для AI агента

Этот документ описывает как AI агент (Claude или другой) должен работать с инструментом автономно: запускать отклики, отвечать на сообщения от работодателей, управлять токенами.

Базовый URL панели: `http://127.0.0.1:8000`

---

## Что агент может делать самостоятельно

| Задача | Возможно? | Примечание |
|---|---|---|
| Запустить рассылку откликов | ✅ | Через `/api/agent/run` |
| Отправить сопроводительное письмо (AI) | ✅ | OpenAI генерирует под каждую вакансию |
| Отправить письмо по шаблону | ✅ | 5 встроенных шаблонов + свои |
| Обновить резюме | ✅ | Поднимает в поиске |
| Проверить и ответить на сообщения | ✅ | Через `/api/inbox` |
| Обновить токен (refresh) | ✅ | Автоматически при истечении |
| Первичная авторизация (новый аккаунт) | ❌ | Требует SMS-код от человека |

**Единственное что требует человека:** первый вход в аккаунт. После этого агент работает полностью автономно.

---

## Шаг 0 — Первичная авторизация (один раз, руками)

```bash
python -m hh_applicant_tool auth
# Откроется браузер → войти на hh.ru → ввести SMS-код
# Токен сохраняется — дальше агент работает сам
```

После этого шага агент сам обновляет токен через `refresh_token` при необходимости.

---

## Шаг 0.5 — Первоначальная настройка шаблонов (один раз)

Заполнить библиотеку шаблонов писем встроенными заготовками:

```
POST /api/letter-templates/seed?profile=default
```

Ответ:
```json
{ "ok": true, "added": ["universal", "short", "motivated", "remote", "experienced"], "total": 5 }
```

Это нужно сделать один раз. Шаблоны сохраняются в `config.json` профиля и доступны при каждом запуске откликов.

---

## Шаг 1 — Pre-flight проверка (всегда перед операцией)

```
GET /api/agent/preflight?profile=default
```

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
| `refresh` | Токен истёк — запустить `/api/agent/run` с `auto_refresh: true`, он обновит сам |
| `reauth` | Нет токена → уведомить человека, не продолжать |

---

## Шаг 2 — Запуск откликов с сопроводительными письмами

Используй `apply_params` внутри `/api/agent/run` — так удобнее чем собирать `args` вручную.

### Вариант A — AI письмо (если есть OpenAI API key, лучшая конверсия)

```
POST /api/agent/run
```

```json
{
  "profile": "default",
  "operation": "apply-vacancies",
  "auto_refresh": true,
  "apply_params": {
    "search": "Python разработчик",
    "use_ai": true,
    "force_message": true,
    "ai_filter": "light",
    "skip_tests": true,
    "max_responses": 50,
    "response_delay": "2-5",
    "schedule": ["remote"],
    "experience": "between3And6"
  }
}
```

AI сгенерирует уникальное письмо для каждой вакансии — персонализировано под название и работодателя.

### Вариант B — Шаблон (без OpenAI)

```json
{
  "profile": "default",
  "operation": "apply-vacancies",
  "auto_refresh": true,
  "apply_params": {
    "search": "Backend developer",
    "template_name": "motivated",
    "force_message": true,
    "skip_tests": true,
    "max_responses": 50,
    "response_delay": "2-4"
  }
}
```

Доступные встроенные шаблоны: `universal`, `short`, `motivated`, `remote`, `experienced`.

Шаблоны используют синтаксис `{вариант1|вариант2}` для рандомизации и плейсхолдеры:
- `%(first_name)s` — имя кандидата
- `%(last_name)s` — фамилия
- `%(vacancy_name)s` — название вакансии
- `%(employer_name)s` — компания
- `%(resume_title)s` — название резюме

### Параметры поиска (`apply_params`)

| Поле | Тип | Пример | Описание |
|---|---|---|---|
| `search` | str | `"Python"` | Строка поиска |
| `use_ai` | bool | `true` | AI-генерация письма под каждую вакансию |
| `template_name` | str | `"short"` | Шаблон письма (если не use_ai) |
| `force_message` | bool | `true` | Всегда прикреплять письмо |
| `ai_filter` | str | `"light"` | Фильтровать вакансии через AI (`light`/`heavy`) |
| `skip_tests` | bool | `true` | Пропускать вакансии с тестами |
| `max_responses` | int | `50` | Макс откликов за прогон |
| `response_delay` | str | `"2-5"` | Задержка между откликами в сек |
| `experience` | str | `"between3And6"` | Опыт (noExperience/between1And3/between3And6/moreThan6) |
| `schedule` | list | `["remote"]` | Тип занятости (remote/fullDay/flexible) |
| `employment` | list | `["full"]` | Формат (full/part/project) |
| `area` | list | `["1","2"]` | Регионы (1=Москва, 2=СПб) |
| `salary` | int | `150000` | Минимальная зарплата |
| `only_with_salary` | bool | `true` | Только вакансии с указанной зарплатой |
| `excluded_filter` | str | `"junior\|стажир"` | Regex исключения по названию |
| `dry_run` | bool | `true` | Тестовый режим без отправки |

### Получение op_id и ожидание результата

```json
{ "op_id": "a3f2c1b0", "refreshed_token": false, "token_status": "ok" }
```

Опрашивать каждые 10–15 секунд:

```
GET /api/operation-status/a3f2c1b0
```

Завершено:
```json
{
  "running": false,
  "returncode": 0,
  "stdout": "✅️ Закончили рассылку откликов для резюме: Python разработчик\n..."
}
```

---

## Шаг 3 — Обновление резюме (поднять в поиске)

```
POST /api/agent/run
```
```json
{ "profile": "default", "operation": "update-resumes", "auto_refresh": true }
```

Рекомендуется запускать раз в 4 часа.

---

## Шаг 4 — Итеративная работа с входящими сообщениями

Это задача для регулярного запуска (каждые 15–30 минут). Работодатели отвечают в разное время.

### 4.1 — Получить список переписок

```
GET /api/inbox?profile=default&per_page=50
```

Смотреть на поле `has_updates: true` — это переписки с новыми сообщениями от работодателей.

```json
{
  "items": [
    {
      "id": 123456,
      "state": "active",
      "state_name": "Активный отклик",
      "vacancy_name": "Python разработчик",
      "employer_name": "ООО Рога и Копыта",
      "has_updates": true
    }
  ]
}
```

### 4.2 — Читать сообщения переписки

```
GET /api/inbox/123456/messages?profile=default
```

```json
{
  "messages": [
    { "id": 789, "text": "Приглашаем на собеседование...", "is_employer": true, "created_at": "2025-04-25T10:00:00" },
    { "id": 788, "text": "Здравствуйте! Направляю резюме...", "is_employer": false }
  ]
}
```

Нужно отвечать если: последнее сообщение `is_employer: true` и мы ещё не ответили после него.

### 4.3 — Отправить AI-ответ

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

AI напишет вежливый профессиональный ответ. Или можно передать конкретный текст в `message`.

### 4.4 — Очистить отказы

Если накопилось много отказов:

```
POST /api/inbox/clear-rejections?profile=default&dry_run=true
```
Сначала `dry_run=true` — посмотреть сколько будет удалено, потом без `dry_run`.

### 4.5 — Алгоритм цикла (псевдокод)

```
каждые 20 минут:
  1. GET /api/agent/preflight  →  если action != "run": пропустить
  2. GET /api/inbox?per_page=50
  3. для каждого item где has_updates == true:
       msgs = GET /api/inbox/{id}/messages
       последнее = msgs[-1]
       если последнее.is_employer == true:
           POST /api/inbox/{id}/reply { use_ai: true, vacancy_name: ..., employer_name: ... }
  4. раз в час: GET /api/inbox?status=discard
       если items.len > 5:
           POST /api/inbox/clear-rejections?dry_run=false
```

---

## Управление шаблонами писем

### Посмотреть все шаблоны

```
GET /api/letter-templates?profile=default
```

Возвращает пользовательские + встроенные (`default_templates`).

### Создать свой шаблон

```
POST /api/letter-templates
```
```json
{
  "profile": "default",
  "name": "my-template",
  "content": "Здравствуйте! Откликаюсь на вакансию «%(vacancy_name)s».\n\nМой опыт хорошо подходит для этой позиции.\n\nС уважением, %(first_name)s"
}
```

### Удалить шаблон

```
DELETE /api/letter-templates/my-template?profile=default
```

### Заполнить встроенными (при первом запуске)

```
POST /api/letter-templates/seed?profile=default
```

---

## Статус токена

```
GET /api/token-status?profile=default
```

| `status` | Значение | Действие |
|---|---|---|
| `ok` | Токен действителен | Запускать |
| `expired` + `can_refresh: true` | Истёк, но есть refresh | Запустить с `auto_refresh: true` |
| `expired` + `can_refresh: false` | Нет refresh_token | Уведомить человека |
| `no_token` | Не авторизован | Уведомить человека |
| `no_config` | Профиль не существует | Создать профиль |

---

## Полный рабочий цикл (рекомендуется)

```
[при запуске — один раз]
  POST /api/letter-templates/seed?profile=default

[каждые 4 часа]
  GET  /api/agent/preflight → action == "run"?
  POST /api/agent/run { operation: "update-resumes" }
  POST /api/agent/run { operation: "apply-vacancies", apply_params: { use_ai: true, force_message: true, ... } }

[каждые 20-30 минут]
  GET  /api/agent/preflight → action == "run"?
  GET  /api/inbox → ответить на has_updates=true
  убрать отказы если накопились
```

---

## Несколько профилей (аккаунтов)

Все endpoint-ы принимают `?profile=<name>`:

```
GET /api/profiles
→ { "profiles": ["default", "senior-dev", "freelance"] }
```

Для каждого профиля — отдельный токен, база данных, шаблоны писем.

---

## Обработка ошибок

| HTTP код | Причина | Действие |
|---|---|---|
| `401` | Нет токена или истёк | Уведомить человека об авторизации |
| `400` | Неверные параметры | Исправить запрос |
| `502` | refresh-token не удался | Уведомить человека |
| `404` | op_id или профиль не найден | Проверить правильность id |
| `returncode != 0` | Ошибка CLI | Читать `stderr` для диагностики |

---

## Настройка OpenAI (для AI-писем и ответов)

```
PUT /api/config?profile=default
```
```json
{
  "data": {
    "openai": {
      "api_key": "sk-...",
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1"
    }
  }
}
```

Поддерживаются любые OpenAI-совместимые API: OpenRouter, LM Studio, Together AI и др.

---

## Справка по endpoint-ам

```
GET  /api/agent/preflight?profile=    # проверить готовность перед операцией
POST /api/agent/run                   # запустить операцию (основной endpoint)
GET  /api/token-status?profile=       # статус токена (offline, без запросов к HH)
GET  /api/operation-status/{op_id}    # статус фоновой операции

GET  /api/inbox?profile=              # список переписок
GET  /api/inbox/{id}/messages         # история сообщений
POST /api/inbox/{id}/reply            # отправить ответ
POST /api/inbox/clear-rejections      # скрыть отказы

GET  /api/letter-templates?profile=   # список шаблонов писем
POST /api/letter-templates            # создать/обновить шаблон
DELETE /api/letter-templates/{name}   # удалить шаблон
POST /api/letter-templates/seed       # заполнить встроенными шаблонами

GET  /api/profiles                    # список профилей
POST /api/profiles                    # создать профиль
GET  /api/stats?profile=              # статистика откликов
PUT  /api/config?profile=             # обновить настройки
GET  /api/logs?profile=               # просмотр логов
```
