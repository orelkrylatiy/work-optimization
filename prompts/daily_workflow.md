# 📅 Ежедневный workflow — HH Applicant Tool

**Оптимальная стратегия:** 5-7 итераций в день с уникальными ответами и тайм-аутами.

---

## 🎯 Цели на день

| Метрика | Цель |
|---------|------|
| Откликов | 80-120 |
| Ответов работодателям | Все новые за 24ч |
| Поднятие резюме | 1 раз (утро) |
| Итераций | 5-7 |
| Тайм-аут между итерациями | 1-2 часа |

---

## 🔄 Цикл итерации (повторять 5-7 раз в день)

```
┌─────────────────────────────────────────────────────────────┐
│  ИТЕРАЦИЯ №N                                                │
│                                                             │
│  1. Проверка состояния (2 мин)                              │
│     └─ whoami → статистика                                 │
│                                                             │
│  2. Если утро → поднять резюме (1 мин)                      │
│     └─ boost-resume                                        │
│                                                             │
│  3. Отклики (10-15 мин)                                     │
│     ├─ dry-run → проверить выдачу                          │
│     └─ live → отправить отклики                            │
│                                                             │
│  4. Ответы работодателям (5-10 мин)                         │
│     ├─ review → посмотреть новые сообщения                 │
│     └─ reply → ответить персонально                        │
│                                                             │
│  5. Тайм-аут (1-2 часа)                                     │
│     └─ пауза до следующей итерации                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Детали по шагам

### Шаг 1: Проверка состояния

```bash
# Быстрая проверка
hh-applicant-tool whoami

# Если нужно больше деталей
hh-applicant-tool whoami --json | jq '.counters'
```

**Что смотреть:**
- ✅ `unread_negotiations` — сколько новых сообщений
- ✅ `new_resume_views` — просмотры резюме
- ✅ `resumes_count` — опубликованные резюме

---

### Шаг 2: Поднятие резюме (только утром, 1 раз)

```bash
# Утренняя итерация (9:00-10:00)
hh-applicant-tool boost-resume

# Проверка результата
hh-applicant-tool list-resumes
```

**Важно:**
- Не чаще 1 раза в 24 часа на резюме
- Лучше утром, до начала откликов

---

### Шаг 3: Отклики на вакансии

#### 3a. Dry-run (проверка выдачи)

```bash
hh-applicant-tool apply-vacancies \
  --search "Frontend разработчик" \
  --letter-file ./letter.txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests \
  --per-page 50 \
  --total-pages 3 \
  --dry-run
```

**Что проверять:**
- ✅ Вакансии релевантные (React, TypeScript, Frontend)
- ✅ Нет junior/стажёр позиций
- ✅ Нет web3/crypto/blockchain
- ✅ Есть сопроводительное письмо

#### 3b. Live (отправка)

```bash
# Если dry-run ок — запускаем live
hh-applicant-tool apply-vacancies \
  --search "Frontend разработчик" \
  --letter-file ./letter.txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests \
  --per-page 50 \
  --total-pages 3
```

**Параметры поиска для разных итераций:**

| Итерация | Поиск | Страниц | Цель |
|----------|-------|---------|------|
| 1 (утро) | `Frontend разработчик` | 3 | 40-50 откликов |
| 2 (день) | `React TypeScript` | 2 | 20-30 откликов |
| 3 (вечер) | `JavaScript Frontend` | 2 | 20-30 откликов |

---

### Шаг 4: Ответы работодателям

#### 4a. Проверка новых сообщений

```bash
# Посмотреть активные переговоры
hh-applicant-tool call-api "/negotiations?status=active&per_page=20" \
  | jq '.items[] | {id, vacancy: .vacancy.name, updated: .updated_at}'
```

#### 4b. Ответы (персонально!)

```bash
# Интерактивный режим — каждый чат вручную
hh-applicant-tool reply-employers
```

**Правила:**
1. Открываешь каждый диалог
2. Читаешь контекст
3. Пишешь персональный ответ (не шаблон!)
4. Всегда упоминаешь Telegram: `@wavemax6`

#### 4c. Если нет новых сообщений

```bash
# Пропускаем шаг, идём на тайм-аут
echo "Нет новых сообщений — переходим к паузе"
```

---

### Шаг 5: Тайм-аут между итерациями

```bash
# Пауза 1-2 часа между итерациями
sleep 7200  # 2 часа
```

**Зачем:**
- HH.ru не банит за массовые действия
- Работодатели видят «органичную» активность
- Ты не выгораешь от марафона

---

## 🕐 Расписание на день

| Время | Итерация | Действия |
|-------|----------|----------|
| 09:00 | #1 | whoami + boost-resume + apply (50) + reply |
| 11:00 | #2 | apply (25) + reply |
| 13:00 | #3 | apply (25) + reply |
| 15:00 | #4 | apply (20) + reply |
| 17:00 | #5 | apply (20) + reply |
| 19:00 | #6 | reply (если есть) |
| 21:00 | #7 | Финальная проверка + plan на завтра |

---

## 🤖 Автоматизация (cron + агент)

### Cron для фоновых задач

```bash
# ~/.config/crontabs/root

# Утреннее поднятие резюме (9:00)
0 9 * * * cd /path/to/project && hh-applicant-tool boost-resume >> /var/log/hh-boost.log 2>&1

# Отклики (каждые 2 часа, 9:00-19:00)
0 9,11,13,15,17,19 * * * cd /path/to/project && hh-applicant-tool apply-vacancies --search "Frontend разработчик" --letter-file ./letter.txt --force-message --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" --skip-tests --per-page 25 --total-pages 1 >> /var/log/hh-apply.log 2>&1

# Проверка новых сообщений (каждый час)
0 * * * * cd /path/to/project && hh-applicant-tool call-api "/negotiations?status=active&per_page=5" | jq '.items | length' >> /var/log/hh-inbox.log 2>&1
```

### Агент для персонализированных ответов

Агент подключается на шаге 4 (ответы работодателям):

```bash
# Агент читает новые сообщения
hh-applicant-tool call-api "/negotiations?status=active&per_page=20" \
  | jq '.items[] | select(.updated_at > "2024-01-01T00:00:00")'

# Для каждого — генерирует персональный ответ
# (см. prompts/reply_employer.md)

# Отправляет через API
hh-applicant-tool call-api -X POST "/negotiations/{ID}/messages" \
  -d '{"message": "Персональный ответ..."}'
```

---

## 📊 Мониторинг прогресса

### В конце дня проверить

```bash
# Статистика за день
hh-applicant-tool whoami

# Лог откликов
tail -50 /var/log/hh-apply.log

# Лог ответов
tail -50 /var/log/hh-reply.log
```

### Цели достигнуты?

- [ ] 80-120 откликов
- [ ] Все новые сообщения обработаны
- [ ] Резюме поднято утром
- [ ] 5-7 итераций выполнено

Если **нет** — скорректируй план на завтра:
- Увеличь `--total-pages` в откликах
- Добавь ещё 1-2 итерации
- Расширь поисковые запросы

---

## ⚠️ Troubleshooting

### Лимит откликов HH.ru

**Симптом:** Отклики перестали отправляться

**Решение:**
```bash
# Подождать до завтра
# Лимит: ~100-150 откликов в сутки
```

### Токен истёк

```bash
hh-applicant-tool refresh-token
# Или
hh-applicant-tool authorize
```

### Нет новых вакансий в поиске

```bash
# Расширить поиск
--search "JavaScript"  # вместо "Frontend разработчик"

# Убрать фильтры
# --excluded-filter "..."  # закомментировать

# Больше страниц
--total-pages 5  # вместо 3
```

---

## 📁 Промпт-файлы

| Файл | Назначение |
|------|------------|
| `prompts/cover_letter_frontend.md` | Сопроводительные письма |
| `prompts/reply_employer.md` | Ответы работодателям |
| `prompts/resume_boost.md` | Поднятие резюме |
| `prompts/daily_workflow.md` | Этот файл |

---

## 🚀 Быстрый старт

```bash
# 1. Клонировать репо
cd /path/to/project

# 2. Запустить первую итерацию
hh-applicant-tool whoami
hh-applicant-tool boost-resume  # если утро
hh-applicant-tool apply-vacancies --search "Frontend разработчик" --letter-file ./letter.txt --force-message --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" --skip-tests --dry-run
hh-applicant-tool apply-vacancies --search "Frontend разработчик" --letter-file ./letter.txt --force-message --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" --skip-tests
hh-applicant-tool reply-employers

# 3. Подождать 2 часа, повторить
```
