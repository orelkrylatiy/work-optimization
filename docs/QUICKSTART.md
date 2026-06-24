# Agent Quick Start

Этот файл поможет агенту быстро включиться в работу без изучения всей документации.

---

## 🔐 Авторизация

Проверить:
```bash
hh-applicant-tool whoami
```

Если ошибка — запустить:
```bash
hh-applicant-tool authorize
```

---

## 📊 Контекст

**Пользователь:** Максим Агофонов  
**Роль:** Frontend-разработчик (React/TypeScript/Redux)  
**Опыт:** 5+ лет (Selecty, РСХБ-Интех)  
**Локация:** Москва, удалёнка OK  
**Контакты:** 
- Telegram: **@wavemax6** (основной)
- Email: vertolet333i@gmail.com

**Резюме:** https://hh.ru/resume/9ae6f847ff0f917b220039ed1f4373635a4471

---

## 🎯 Ежедневные задачи

### 1. Утро (первый запуск)

```bash
# Проверить состояние
hh-applicant-tool whoami
hh-applicant-tool list-resumes

# Поднять резюме в топ
hh-applicant-tool boost-resume
```

### 2. Отклики (80-120 в день)

```bash
# Dry-run сначала!
hh-applicant-tool apply-vacancies \
  --search "Frontend разработчик" \
  --letter-file ./letter.txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests \
  --dry-run

# Если всё ок — запуск
hh-applicant-tool apply-vacancies \
  --search "Frontend разработчик" \
  --letter-file ./letter.txt \
  --force-message \
  --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" \
  --skip-tests
```

**Варианты поиска:**
- `"Frontend разработчик"` — основной
- `"React TypeScript"` — узкий
- `"JavaScript"` — широкий

### 3. Ответы работодателям

```bash
# Шаблонное сообщение (быстро)
hh-applicant-tool reply-employers \
  -m "Здравствуйте! Благодарю за интерес. Готов обсудить детали. Telegram: @wavemax6" \
  --period 2

# Интерактивный режим (персонально)
hh-applicant-tool reply-employers
```

---

## 📈 KPI

| Метрика | Цель |
|---------|------|
| Откликов в день | 80-120 |
| Ответов работодателям | Все новые за 2 дня |
| Автоподнятие резюме | 1 раз в день |
| Просмотры резюме | Растут |

---

## ⚠️ Важно

1. **Всегда упоминать Telegram @wavemax6** в ответах
2. **Dry-run перед live** запуском откликов
3. **Исключать:** junior, стажёры, bitrix, web3, crypto, blockchain
4. **Лимит HH:** ~100-150 откликов в сутки

---

## 🛠 Troubleshooting

| Проблема | Решение |
|----------|---------|
| "Требуется авторизация" | `hh-applicant-tool authorize` |
| "Лимит откликов" | Ждать до завтра |
| "Токен протух" | `hh-applicant-tool refresh-token` |
| "Нет вакансий" | Расширить поиск, убрать фильтры |

---

## 📚 Документация

- [AGENT_GUIDE.md](AGENT_GUIDE.md) — полное руководство
- [AUTONOMOUS_AGENT_WORKFLOW.md](AUTONOMOUS_AGENT_WORKFLOW.md) — автономный контур
- [README.md](../README.md) — обзор проекта
