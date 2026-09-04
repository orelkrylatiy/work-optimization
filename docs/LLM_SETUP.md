# Подключение LLM

LLM в этом проекте не управляет расписанием и не решает, какие команды запускать. Она получает уже подготовленный контекст и генерирует текст для конкретной операции.

## Где Используется AI

| Задача | Конфиг | Runtime |
|---|---|---|
| сопроводительные письма | `openai_cover_letter` | `apply-vacancies --ai` / `scripts/apply.sh` |
| ответы работодателям | `openai_reply`, fallback `openai_cover_letter` | `scripts/reply.sh` |
| AI-фильтр вакансий | `openai_vacancy_filter` | `apply-vacancies --ai-filter ...` |
| капча | `openai_captcha` | browser authorization / apply captcha flow |

Scheduled reply worker использует общий `ChatOpenAI`, то есть те же timeout, rate limit и transient retries, что и основной Python-код.

## Конфигурация

`config.json` хранится отдельно для каждого профиля. В Docker базовая директория обычно `/app/config`.

Минимальный пример:

```json
{
  "openai_cover_letter": {
    "api_key": "...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.35,
    "max_completion_tokens": 600,
    "rate_limit": 30,
    "timeout": 45
  },
  "openai_reply": {
    "api_key": "...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.35,
    "max_completion_tokens": 500,
    "rate_limit": 30,
    "timeout": 45,
    "max_retries": 3
  },
  "reply_fallback": {
    "enabled": true,
    "message": "Здравствуйте! Спасибо за сообщение. Я разработчик, вакансия мне интересна. Готов обсудить задачи, формат работы и ответить на вопросы."
  }
}
```

`base_url` должен быть полным OpenAI-compatible chat-completions endpoint.

## Fallback Для Ответов

Здесь есть два разных fallback-механизма.

### 1. Fallback Конфига Провайдера

Порядок выбора LLM строго определён:

```text
openai_reply
    ↓ если секции нет
openai_cover_letter
    ↓ если секции нет / она невалидна
STOP
```

Live reply-worker не подставляет скрытый default URL, model или API key. Конфигурационная ошибка должна остановить отправку, а не переключить production worker на неожиданную модель.

Для сопроводительных fallback на `openai_reply` нет: `scripts/apply.sh` требует `openai_cover_letter`.

### 2. Runtime Fallback Сообщения

После того как LLM выбрана, `ChatOpenAI` сначала выполняет свои обычные retries. Если после них вызов всё равно завершается `OpenAIError` (сеть, 429/5xx, невалидный ответ провайдера и другие runtime-ошибки LLM), reply worker может отправить статический шаблон.

Если секция `reply_fallback` отсутствует, fallback включён по умолчанию и используется безопасный встроенный текст:

```text
Здравствуйте! Спасибо за сообщение. Я разработчик, вакансия мне интересна. Готов обсудить задачи, формат работы и ответить на вопросы.
```

Шаблон можно заменить отдельно для каждого профиля:

```json
{
  "reply_fallback": {
    "enabled": true,
    "message": "Здравствуйте! Вакансия интересна. Готов обсудить детали и ответить на вопросы."
  }
}
```

Или полностью выключить, вернув прежнее fail-closed поведение:

```json
{
  "reply_fallback": {
    "enabled": false
  }
}
```

Fallback не используется просто потому, что модель написала плохой текст. Такой текст по-прежнему проходит humanizer/corrective-generation и при повторной неудаче пропускается. Статический fallback включается только когда вызов LLM завершился ошибкой.

Сам fallback проходит те же проверки качества: пустой текст, длинные тире, placeholder'ы и AI-клише не допускаются. После генерации worker всё равно повторно проверяет, что последнее сообщение работодателя не изменилось, и отправляет ответ с deterministic idempotency key.

В JSON-статистике `scripts/reply_iterative_ai.py` поле `fallback` показывает, сколько раз за run использовался шаблон.

## Проверка Конфига

Статическая проверка, без отправки данных модели:

```bash
python scripts/check_ai.py --purpose cover-letter
python scripts/check_ai.py --purpose reply
```

Проверка конкретного профиля:

```bash
python scripts/check_ai.py --purpose reply --profile account2
```

Реальный probe одним коротким запросом:

```bash
python scripts/check_ai.py --purpose reply --probe
```

`--probe` удобно запускать вручную после изменения provider/model. Его не нужно выполнять каждый час из cron.

## OpenAI / OpenRouter

Пример OpenAI:

```json
{
  "api_key": "...",
  "base_url": "https://api.openai.com/v1/chat/completions",
  "model": "gpt-4o-mini"
}
```

Пример OpenRouter:

```json
{
  "api_key": "...",
  "base_url": "https://openrouter.ai/api/v1/chat/completions",
  "model": "openai/gpt-4o-mini"
}
```

## Ollama

Проект ожидает OpenAI-compatible interface Ollama:

```bash
ollama serve
ollama pull qwen2.5:14b
```

```json
{
  "api_key": "ollama",
  "base_url": "http://localhost:11434/v1/chat/completions",
  "model": "qwen2.5:14b"
}
```

Нативный `/api/generate` имеет другой формат payload и для этого клиента не подходит.

Если приложение работает в Docker, `localhost` внутри контейнера означает сам контейнер. Если Ollama запущена на host-машине, укажи сетевой адрес, доступный контейнеру, либо запусти провайдер в общей Docker network.

## Промпты И Humanizer

Основные шаблоны:

- `prompts/cover_letter_frontend.txt`
- `prompts/reply_employer.txt`

Они запрещают длинные тире, placeholder'ы, канцелярит, типовые AI-переходы и излишне гладкий рекламный стиль.

Для autonomous replies prompt не является единственной защитой. `src/hh_applicant_tool/automation/reply_worker.py` дополнительно валидирует полученный текст. Если ответ содержит длинное тире, placeholder или явное AI-клише, worker делает одну corrective generation. Вторая неудача означает `skip`, а не отправку плохого сообщения.

Telegram больше не приписывается кодом в каждый ответ. Prompt разрешает его только когда это действительно следует из контекста.

## Privacy Dry-run

`reply.sh --dry-run` не отправляет историю переписки LLM-провайдеру. Он показывает deterministic preview и проверяет логику выбора чатов без утечки содержимого чатов внешней модели.

Live mode, естественно, передаёт текст последних сообщений выбранному LLM provider для генерации ответа.

## Диагностика

```bash
# AI config
python scripts/check_ai.py --purpose reply

# реальный provider probe
python scripts/check_ai.py --purpose reply --probe

# чат без отправки и без LLM
./scripts/reply.sh --dry-run --chats 20

# отклики без отправки (AI письмо генерируется)
./scripts/apply.sh --dry-run --limit 10 --pages 2
```

При 429/5xx или временной сетевой ошибке `ChatOpenAI` сначала делает ограниченные retries. Если они исчерпаны и `reply_fallback.enabled=true`, worker использует статический fallback. Если fallback выключен, чат пропускается и run получает ошибку, как раньше.
