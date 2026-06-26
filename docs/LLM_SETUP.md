# 🧠 Подключение LLM

Этот документ описывает, **как подключить LLM** к проекту, **где она используется** и **какие провайдеры подходят**.

## Главная идея

LLM здесь — это **чистая функция «контекст → текст»**, встроенная в детерминированный поток.
Она не принимает решения «что запустить» — это делают cron и сам инструмент.

LLM нужна ровно для трёх вещей:

| Что генерит | Где включается |
|-------------|----------------|
| 📝 Сопроводительные письма под вакансию | `apply-vacancies --ai` / админка `/api/generate-letter` |
| 💬 Ответы работодателям в чате | `reply-employers --use-ai` / админка `/api/inbox/{id}/reply` |
| 🔓 Распознавание капчи (vision) | автоматически при `authorize` / `apply-vacancies` |

AI **не обязателен**: без него инструмент работает на шаблонных письмах (`--letter-file`) и
ручных ответах. AI включается только если настроены соответствующие секции конфига.

---

## Где живёт конфиг

Ключи лежат в `config.json` внутри директории профиля
(локально `~/.config/hh-applicant-tool/...`, в Docker — `config/config.json`).

Открыть в редакторе:

```bash
hh-applicant-tool config -p          # путь к файлу
hh-applicant-tool config             # открыть в $EDITOR
```

CLI и веб-админка теперь читают **одни и те же** секции и используют **один и тот же**
клиент (`ChatOpenAI` с retry и rate-limit). Рассинхрона больше нет.

---

## Секции конфига

Любой OpenAI-совместимый endpoint. У каждой задачи — своя секция, чтобы можно было
ставить разные модели (например, дешёвую для фильтра и капчи, поумнее — для писем).

```jsonc
{
  // Сопроводительные письма (CLI apply-vacancies --ai и админка generate-letter)
  "openai_cover_letter": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_completion_tokens": 600,
    "rate_limit": 40
  },

  // AI-фильтр вакансий (CLI apply-vacancies --ai)
  "openai_vacancy_filter": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini"
  },

  // Распознавание капчи — нужна vision-модель
  "openai_captcha": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini"
  },

  // Ответы работодателям в чате (админка inbox). Необязательна:
  // если её нет — используется openai_cover_letter.
  "openai_reply": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4o-mini",
    "temperature": 0.7
  }
}
```

### Поля секции

| Поле | Обяз. | Описание |
|------|:----:|----------|
| `api_key` | ✅ | Ключ провайдера |
| `base_url` | ✅ | Полный endpoint. Допускается короткий (`.../v1`) — админка сама допишет `/chat/completions`; для CLI указывайте полный URL |
| `model` | ⚠️ | ID модели. Большинство провайдеров требуют |
| `temperature` | — | По умолчанию `0.0` (CLI) / задаётся вызовом (админка) |
| `max_completion_tokens` | — | Лимит ответа (по умолчанию 1000 в CLI) |
| `rate_limit` | — | Запросов в минуту, `0` = выключено (по умолчанию 40) |
| `proxy_url` | — | Отдельный прокси только для AI-запросов |

> **Обратная совместимость.** Если оставить одну старую секцию `openai`, и письма, и
> ответы будут брать ключ из неё. Новые секции имеют приоритет.

---

## Провайдеры

### OpenAI

```json
"base_url": "https://api.openai.com/v1/chat/completions",
"model": "gpt-4o-mini"
```

### OpenRouter (много моделей за одним ключом)

```json
"base_url": "https://openrouter.ai/api/v1/chat/completions",
"model": "openai/gpt-4o-mini"
```

### Ollama (локально, бесплатно, без интернета)

**Важно:** Ollama поддерживает два режима API:

1. **OpenAI-совместимый режим** (рекомендуется для этого проекта):
   ```bash
   ollama serve
   ollama pull qwen2.5:7b
   ```
   ```json
   "base_url": "http://localhost:11434/v1/chat/completions",
   "model": "qwen2.5:7b",
   "api_key": "ollama"
   ```

2. **Нативный режим Ollama** (альтернатива):
   ```json
   "base_url": "http://localhost:11434/api/generate",
   "model": "qwen2.5:7b"
   ```
   ⚠️ Нативный режим требует изменения кода клиента — используйте OpenAI-совместимый режим.

**Проверка работоспособности:**
```bash
# Убедитесь, что Ollama запущен
ollama list

# Проверьте, что модель установлена
ollama ls | grep qwen2.5

# Проверьте API endpoint
curl http://localhost:11434/api/tags
```

**Troubleshooting 404 ошибок:**
- Убедитесь, что модель установлена: `ollama pull qwen2.5:7b`
- Проверьте, что Ollama сервер запущен: `ollama serve`
- Используйте полный URL: `http://localhost:11434/v1/chat/completions` (не сокращённый)
- Для капчи нужна vision-модель (напр. `llama3.2-vision`); иначе оставьте для капчи облачную модель, а письма/фильтр гоните локально.

Подойдёт **любой** OpenAI-совместимый сервер (LM Studio, vLLM, llama.cpp `--api`, и т.д.).

---

## Промпты (стиль писем и ответов)

Системный промпт можно задать **строкой или файлом** — `--system-prompt` и `--prompt`
понимают оба варианта (путь к файлу или `@file`):

```bash
# письмо: стиль из файла
hh-applicant-tool apply-vacancies --ai --system-prompt prompts/cover_letter_frontend.txt ...

# ответ работодателю: стиль из файла
hh-applicant-tool reply-employers --use-ai --system-prompt prompts/reply_employer.txt ...
```

Готовые заготовки и шаблон под личные данные — в [../prompts/README.md](../prompts/README.md).

## Проверка

```bash
# письма: dry-run покажет сгенерированный текст без отправки
hh-applicant-tool apply-vacancies --ai --search "Frontend" --dry-run

# ответы в чате через админку
curl -s -X POST http://127.0.0.1:8000/api/inbox/123/reply \
  -H 'Content-Type: application/json' \
  -d '{"use_ai": true, "vacancy_name": "React Dev", "employer_name": "Acme"}'
```

---

## Troubleshooting

| Симптом | Причина / решение |
|---------|-------------------|
| `AI не настроен: добавьте секцию ...` | Нет секции или пустой `api_key` |
| `Ошибка AI: ... 401` | Неверный `api_key` |
| `Ошибка AI: ... rate limit` | Поднимите `rate_limit` ниже или подождите; клиент сам делает retry на 429 |
| Письма пустые/обрезаны | Увеличьте `max_completion_tokens` |
| Капча не решается | Нужна **vision**-модель в `openai_captcha` |
| Долгие ответы / таймаут | Локальная модель слишком тяжёлая — возьмите модель полегче |

См. также: [README — раздел AI](../README.md#ai) и [AGENT_GUIDE](AGENT_GUIDE.md).
