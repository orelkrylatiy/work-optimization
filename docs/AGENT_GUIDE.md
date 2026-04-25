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

## Дайджест — одним вызовом получить всё нужное

```
GET /api/agent/digest?profile=default
```

```json
{
  "date": "2025-04-25",
  "token": { "status": "ok", "expires_in_seconds": 82400 },
  "stats": {
    "applied_today": 23,
    "total_applied": 187,
    "by_state": { "active": 45, "invitation": 3, "discard": 12 }
  },
  "inbox_needs_reply": [
    { "id": 123, "state": "invitation", "vacancy_name": "Python Dev", "employer_name": "Acme" }
  ],
  "inbox_needs_reply_count": 1,
  "action_needed": "reply_inbox"
}
```

Поле `action_needed`: `none` / `reply_inbox` / `refresh` / `reauth`.  
Агент может начинать каждый цикл именно с этого вызова.

---

## Массовый ответ работодателям (reply-employers)

Самый мощный режим: CLI читает **полную историю каждой переписки** и передаёт AI.

```
POST /api/run/reply-employers
```

```json
{
  "profile": "default",
  "use_ai": true,
  "only_invitations": false,
  "max_pages": 10,
  "period": 14
}
```

Или через `/api/agent/run`:

```json
{
  "profile": "default",
  "operation": "reply-employers",
  "auto_refresh": true,
  "args": ["--use-ai", "--only-invitations", "--max-pages", "10"]
}
```

Параметры `reply-employers`:

| Параметр | Тип | Описание |
|---|---|---|
| `use_ai` | bool | AI генерирует ответ по истории чата |
| `only_invitations` | bool | Отвечать только на приглашения |
| `max_pages` | int | Сколько страниц переписок проверить |
| `period` | int | Игнорировать чаты старше N дней |
| `reply_message` | str | Фиксированный шаблон ответа (без AI) |
| `dry_run` | bool | Тест без отправки |

---

## Контекстный ответ в конкретный чат

`/api/inbox/{id}/reply` теперь загружает историю переписки перед вызовом AI:

```
POST /api/inbox/123456/reply
```

```json
{
  "profile": "default",
  "message": "",
  "use_ai": true,
  "vacancy_name": "Python Dev",
  "employer_name": "Acme Corp",
  "fetch_history": true
}
```

AI получит последние 10 сообщений чата — ответ будет осмысленным.  
Можно передать историю явно через поле `history: [...]` (тогда `fetch_history: false`).

---

## Резюме-контент для персонализированных писем

Получи текст резюме и используй как `system_prompt` при запуске откликов:

```
GET /api/resumes/{resume_id}/content?profile=default
```

```json
{
  "resume_id": "abc123",
  "title": "Python разработчик",
  "text": "РЕЗЮМЕ: Python разработчик\nКлючевые навыки: Python, FastAPI...\nОПЫТ РАБОТЫ:\n- Senior Dev в Acme...",
  "system_prompt_suggestion": "Ты — соискатель с опытом. Вот твоё резюме:\n\n..."
}
```

Использование:

```json
{
  "operation": "apply-vacancies",
  "apply_params": {
    "use_ai": true,
    "force_message": true,
    "system_prompt": "<вставить system_prompt_suggestion из ответа выше>"
  }
}
```

Письма сразу станут персонализированными — AI будет ссылаться на конкретный опыт.

---

## Управление чёрным списком

```
GET    /api/employers/blacklist?profile=         # список заблокированных
POST   /api/employers/blacklist/{employer_id}    # заблокировать
DELETE /api/employers/blacklist/{employer_id}    # разблокировать
```

Агент может автоматически блокировать работодателей после отказа или нерелевантного предложения.

---

## Рекомендуемый цикл агента (финальная версия)

```
[один раз при запуске]
  POST /api/letter-templates/seed?profile=default
  GET  /api/resumes?profile=default  →  взять resume_id
  GET  /api/resumes/{id}/content     →  сохранить system_prompt_suggestion

[каждые 4 часа]
  GET  /api/agent/digest             →  action_needed != "reauth"?
  POST /api/agent/run { operation: "update-resumes" }
  POST /api/agent/run {
    operation: "apply-vacancies",
    apply_params: {
      use_ai: true,
      force_message: true,
      system_prompt: "<resume system_prompt>",
      skip_tests: true,
      max_responses: 50
    }
  }

[каждые 20 минут]
  GET  /api/agent/digest              →  если action_needed == "none": пропустить
  если inbox_needs_reply_count > 0:
    POST /api/agent/run { operation: "reply-employers", args: ["--use-ai"] }
  или точечно:
    GET  /api/inbox?per_page=50
    для каждого has_updates=true:
      POST /api/inbox/{id}/reply { use_ai: true, fetch_history: true }

[еженедельно]
  POST /api/inbox/clear-rejections   →  убрать накопившиеся отказы
  GET  /api/stats                    →  сводка для отчёта
```

---

## Справка по всем endpoint-ам

```
# Агент
GET  /api/agent/preflight?profile=    проверить готовность
GET  /api/agent/digest?profile=       дайджест: статус + inbox + статистика
POST /api/agent/run                   запустить операцию (apply/update/reply/refresh)
GET  /api/token-status?profile=       офлайн-статус токена
GET  /api/operation-status/{op_id}    статус фоновой операции

# Отклики
POST /api/run/apply-vacancies-full    запуск с полными параметрами
POST /api/run/reply-employers         массовый ответ с историей чата
POST /api/run/update-resumes          обновить/поднять резюме

# Inbox
GET  /api/inbox?profile=              список переписок
GET  /api/inbox/{id}/messages         история сообщений
POST /api/inbox/{id}/reply            ответить (+ AI с историей)
POST /api/inbox/clear-rejections      скрыть отказы

# Шаблоны писем
GET    /api/letter-templates?profile= список шаблонов
POST   /api/letter-templates          создать/обновить шаблон
DELETE /api/letter-templates/{name}   удалить шаблон
POST   /api/letter-templates/seed     заполнить встроенными

# Резюме
GET  /api/resumes?profile=            список резюме из БД
GET  /api/resumes/{id}/content        текст резюме для system_prompt

# Чёрный список
GET    /api/employers/blacklist?profile=       список
POST   /api/employers/blacklist/{id}           заблокировать
DELETE /api/employers/blacklist/{id}           разблокировать

# Управление
GET  /api/profiles                    список профилей
POST /api/profiles                    создать профиль
GET  /api/stats?profile=              статистика откликов
PUT  /api/config?profile=             обновить настройки (openai, delays, ...)
GET  /api/logs?profile=               последние логи
POST /api/auth/reauthorize?profile=   запустить авторизацию (требует человека)
```
