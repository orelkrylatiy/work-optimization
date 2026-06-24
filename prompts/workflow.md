# 🔄 Workflow Orchestrator

## Главная петля работы (5-7 итераций)

```python
# Псевдокод основного цикла
for iteration in range(1, 8):  # 5-7 итераций
    print(f"=== ИТЕРАЦИЯ {iteration}/7 ===")
    
    # Шаг 1: Проверка состояния
    state = check_state()
    
    # Шаг 2: Boost резюме (1 раз в 24ч)
    if state['resume_boosted_before'] < 24_hours_ago:
        print("⏭️ Пропуск boost (менее 24ч)")
    else:
        boost_resume()
        wait(60)  # 1 мин пауза
    
    # Шаг 3: Отклики на вакансии
    if state['applies_today'] >= 100:
        print("⏭️ Пропуск откликов (лимит 100)")
    else:
        apply_vacancies(
            count=100 - state['applies_today'],
            unique_cover_letters=True  # Генерировать уникальные
        )
        wait(120)  # 2 мин пауза
    
    # Шаг 4: Ответы в чатах
    new_messages = check_new_messages()
    if not new_messages:
        print("⏭️ Пропуск чатов (нет новых)")
    else:
        for chat in new_messages:
            response = generate_chat_response(
                context=chat['history'],
                question=chat['last_message']
            )
            send_message(chat['id'], response)
            wait(30)  # 30 сек между ответами
        wait(60)
    
    # Шаг 5: Follow-up (тишина >2 дней)
    silent_chats = get_silent_chats(days=2)
    if not silent_chats:
        print("⏭️ Пропуск follow-up (все ответили)")
    else:
        for chat in silent_chats[:3]:  # Макс 3 за итерацию
            send_followup(chat)
            wait(30)
        wait(60)
    
    # Шаг 6: Пауза между итерациями
    if iteration < 7:
        pause_minutes = random.randint(30, 60)
        print(f"⏸️ Пауза {pause_minutes} мин перед итерацией {iteration+1}")
        wait(pause_minutes * 60)
```

---

## 📋 Чек-лист итерации

### Пре-чек (30 сек)
- [ ] `whoami` работает → авторизация ОК
- [ ] Токен не протух
- [ ] Лимит откликов не достигнут

### Шаг 1: Boost резюме (1 мин)
- [ ] Проверить когда последний boost
- [ ] Если >24ч → запустить `boost-resume`
- [ ] Лог: `Boost выполнен в HH:MM`

### Шаг 2: Отклики (5-10 мин)
- [ ] Dry-run: проверить сколько вакансий найдено
- [ ] Сгенерировать уникальные письма (вариации 20-30%)
- [ ] Запуск live
- [ ] Лог: `Отправлено N откликов`

### Шаг 3: Чаты (3-5 мин)
- [ ] Получить список чатов с новыми сообщениями
- [ ] Для каждого:
  - [ ] Прочитать последние 5-10 сообщений
  - [ ] Сгенерировать контекстный ответ
  - [ ] Отправить
  - [ ] Пауза 30 сек
- [ ] Лог: `Ответов в чаты: N`

### Шаг 4: Follow-up (2-3 мин)
- [ ] Найти чаты без ответа >2 дней
- [ ] Макс 3 follow-up за итерацию
- [ ] Вежливое напоминание (не спам!)
- [ ] Лог: `Follow-up: N`

### Пост-чек (30 сек)
- [ ] Обновить `state.json`
- [ ] Записать метрики итерации
- [ ] Проверить ошибки

---

## 🎯 Промпт для каждой фазы

### Фаза 1: Boost Resume
```
Ты ассистент для поднятия резюме в топ на HH.ru.

Задача:
1. Проверить когда последний раз выполнялся boost
2. Если прошло <24 часов → пропустить
3. Если >24 часов → выполнить boost-resume
4. Записать время выполнения

Команда:
hh-applicant-tool boost-resume

Ожидаемый результат:
✅ Резюме поднято в топ
⏭️ Пропущено (менее 24ч)
❌ Ошибка: [текст]
```

### Фаза 2: Apply Vacancies
```
Ты ассистент для откликов на вакансии на HH.ru.

Пользователь: Максим Агофонов, Frontend-разработчик (React/TypeScript)
Опыт: 5+ лет
Стек: React, TypeScript, Redux, Python, Go, Node.js
Локация: Москва (удалёнка)
Контакты: Telegram @wavemax6

Задача:
1. Найти вакансии по запросу "{{search_query}}"
2. Исключить: junior, стажёр, bitrix, web3, crypto, blockchain
3. Для каждой вакансии сгенерировать УНИКАЛЬНОЕ сопроводительное письмо
4. Отправить отклик с письмом

Параметры:
- search_query: "Frontend разработчик" | "React TypeScript" | "JavaScript"
- count: {{remaining_applies}} (макс 100 в день)
- unique_variations: true (20-30% вариаций в текстах)

Команда:
hh-applicant-tool apply-vacancies \
  --search "{{search_query}}" \
  --letter-file ./prompts/templates/cover-letter-{{variation_id}}.txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests

Ожидаемый результат:
✅ Отправлено N откликов
⏭️ Пропущено (лимит достигнут)
❌ Ошибка: [текст]
```

### Фаза 3: Chat Responses
```
Ты ассистент для ответов работодателям в чатах HH.ru.

Стиль общения:
- Вежливый, профессиональный
- Краткий (2-4 предложения)
- С упоминанием Telegram @wavemax6
- Адаптированный под контекст чата

Задача:
1. Прочитать историю чата (последние 5-10 сообщений)
2. Определить вопрос/тему работодателя
3. Сгенерировать персональный ответ
4. Отправить сообщение

Входные данные:
- vacancy_name: "{{vacancy_name}}"
- employer_name: "{{employer_name}}"
- chat_history: [последние сообщения]
- last_question: "{{last_message}}"

Правила:
- Если вопрос про опыт → честно рассказать релевантное
- Если вопрос про навыки → перечислить подходящие
- Если вопрос про формат → уточнить предпочтения
- Если нет вопроса → вежливый follow-up

Примеры ответов:
- "Здравствуйте! Да, у меня есть опыт с [технология]. Использовал в проекте [кратко]. Готов обсудить детали в Telegram: @wavemax6"
- "Добрый день! Для меня приоритетна удалёнка, но готов обсудить гибридный формат для интересной команды."

Команда:
curl -X POST "https://api.hh.ru/chats/{{chat_id}}/messages" \
  -H "Authorization: Bearer {{token}}" \
  -H "Content-Type: application/json" \
  -d '{"text": "{{generated_response}}", "idempotency_key": "{{uuid}}"}'

Ожидаемый результат:
✅ Отправлено N ответов
⏭️ Пропущено (нет новых сообщений)
❌ Ошибка: [текст]
```

### Фаза 4: Follow-up
```
Ты ассистент для follow-up сообщений в чатах HH.ru.

Стиль:
- Вежливый, ненавязчивый
- Напоминание о себе (не требование ответа)
- Краткий (1-2 предложения)

Когда использовать:
- Работодатель написал → ты ответил → тишина >2 дней
- Ты откликнулся → тишина >3 дней
- Собеседование было → тишина >5 дней

Когда НЕ использовать:
- Прошло <48 часов с последнего сообщения
- Уже был follow-up на этой неделе
- Статус "discard" (отказ)

Шаблоны:
1. После отклика (3 дня):
   "Здравствуйте! Напомню о своём отклике на вакансию {{vacancy_name}}. 
    Всё ещё заинтересован в позиции, готов обсудить детали. 
    Мой Telegram: @wavemax6"

2. После ответа работодателя (2 дня тишины):
   "Добрый день! Хотел уточнить, остались ли у вас вопросы по моему опыту? 
    Готов предоставить дополнительную информацию. 
    Telegram: @wavemax6"

3. После собеседования (5 дней):
   "Здравствуйте! Подскажите, пожалуйста, есть ли обратная связь по итогам собеседования? 
    Буду благодарен за любой ответ. 
    С уважением, Максим"

Команда:
curl -X POST "https://api.hh.ru/chats/{{chat_id}}/messages" \
  -H "Authorization: Bearer {{token}}" \
  -H "Content-Type: application/json" \
  -d '{"text": "{{followup_text}}", "idempotency_key": "{{uuid}}"}'

Ожидаемый результат:
✅ Отправлено N follow-up
⏭️ Пропущено (нет подходящих чатов)
❌ Ошибка: [текст]
```

---

## 📊 Метрики итерации

Записывать в `logs/iteration-N.json`:

```json
{
  "iteration": 1,
  "timestamp": "2026-06-24T12:00:00+03:00",
  "duration_seconds": 480,
  "steps": {
    "boost_resume": {
      "executed": true,
      "last_boost": "2026-06-23T10:00:00+03:00",
      "result": "success"
    },
    "apply_vacancies": {
      "executed": true,
      "count": 85,
      "search_query": "Frontend разработчик",
      "result": "success"
    },
    "chat_responses": {
      "executed": true,
      "count": 5,
      "chats_responded": [5384102110, 5383641581],
      "result": "success"
    },
    "follow_up": {
      "executed": true,
      "count": 2,
      "chats": [5383667594, 5384104537],
      "result": "success"
    }
  },
  "metrics": {
    "applies_today": 85,
    "applies_total": 245,
    "chats_active": 12,
    "chats_new_messages": 5,
    "views_resume": 132,
    "invitations": 3
  },
  "errors": [],
  "next_iteration_in": 1800
}
```

---

## 🛠 Скрипты

### `scripts/run-iteration.sh`
```bash
#!/bin/bash
# Запуск одной итерации

ITERATION=${1:-1}
LOG_FILE="logs/iteration-${ITERATION}.json"

echo "=== ИТЕРАЦИЯ ${ITERATION} ==="
date -Iseconds > $LOG_FILE

# Шаг 1: Boost
echo "[1/4] Boost resume..."
hh-applicant-tool boost-resume 2>&1 | tee -a $LOG_FILE

# Шаг 2: Отклики
echo "[2/4] Apply vacancies..."
hh-applicant-tool apply-vacancies \
  --search "Frontend разработчик" \
  --letter-file ./prompts/templates/cover-letter-$(($RANDOM % 5 + 1)).txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests 2>&1 | tee -a $LOG_FILE

# Шаг 3: Чаты
echo "[3/4] Chat responses..."
python3 scripts/respond-to-chats.py 2>&1 | tee -a $LOG_FILE

# Шаг 4: Follow-up
echo "[4/4] Follow-up..."
python3/scripts/send-followups.py 2>&1 | tee -a $LOG_FILE

echo "=== ИТЕРАЦИЯ ${ITERATION} ЗАВЕРШЕНА ==="
```

### `scripts/run-full-cycle.sh`
```bash
#!/bin/bash
# Запуск 5-7 итераций с паузами

MAX_ITERATIONS=${1:-5}
PAUSE_MIN=${2:-30}
PAUSE_MAX=${3:-60}

for i in $(seq 1 $MAX_ITERATIONS); do
    ./scripts/run-iteration.sh $i
    
    if [ $i -lt $MAX_ITERATIONS ]; then
        PAUSE=$((RANDOM % (PAUSE_MAX - PAUSE_MIN + 1) + PAUSE_MIN))
        echo "⏸️ Пауза ${PAUSE} мин перед итерацией $((i+1))"
        sleep ${PAUSE}m
    fi
done

echo "✅ Цикл из ${MAX_ITERATIONS} итераций завершён"
```
