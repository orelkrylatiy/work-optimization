# ⏰ Автозапуск hh-applicant-tool

Этот гайд описывает способы автоматического запуска ежедневных задач.

---

## 📋 Способы автозапуска

| Способ | ОС | Сложность | Надёжность |
|--------|----|-----------|------------|
| **cron** | macOS, Linux | ⭐ Просто | ⭐⭐⭐ Высокая |
| **systemd timer** | Linux | ⭐⭐ Средне | ⭐⭐⭐⭐ Очень высокая |
| **Python scheduler** | Любая | ⭐ Просто | ⭐⭐ Средняя |
| **Docker + cron** | Любая | ⭐⭐ Средне | ⭐⭐⭐ Высокая |

---

## 1️⃣ Cron (рекомендуется для macOS/Linux)

### Быстрая настройка

```bash
# Автозапуск в 9:00 ежедневно
make schedule

# Или в своё время (например, 10:30)
make schedule-time TIME=10:30
```

### Что делает скрипт

1. Создаёт 2 cron-задачи:
   - **09:00** — `boost-resume` (поднятие резюме)
   - **09:15** — `apply-vacancies` (отклики, 50 вакансий)

2. Логи сохраняются в `logs/boost.log` и `logs/apply.log`

### Проверка

```bash
# Посмотреть задачи
crontab -l | grep hh-applicant

# Посмотреть логи
tail -f logs/boost.log
tail -f logs/apply.log
```

### Отмена

```bash
make unschedule
```

### Вручную (если make не работает)

```bash
# Открой crontab
crontab -e

# Добавь строки (замени /path/to/project на свой):
15 9 * * * cd /path/to/project && python3 -m hh_applicant_tool boost-resume >> /path/to/project/logs/boost.log 2>&1
30 9 * * * cd /path/to/project && python3 -m hh_applicant_tool apply-vacancies --search "Frontend разработчик" --letter-file /path/to/project/letter.txt --force-message --excluded-filter "junior|стажир|bitrix|web3|crypto|blockchain" --skip-tests --per-page 50 --total-pages 3 >> /path/to/project/logs/apply.log 2>&1
```

---

## 2️⃣ systemd timer (для Linux серверов)

### Настройка

```bash
# Запустить скрипт настройки
bash scripts/setup-systemd-timer.sh

# Или через make (если есть)
make schedule-systemd
```

### Проверка

```bash
# Список таймеров
systemctl --user list-timers | grep hh-

# Статус
systemctl --user status hh-boost.timer
systemctl --user status hh-apply.timer

# Логи
journalctl --user -u hh-boost.service -f
journalctl --user -u hh-apply.service -f
```

### Отмена

```bash
systemctl --user disable --now hh-boost.timer hh-apply.timer
rm ~/.config/systemd/user/hh-*.service ~/.config/systemd/user/hh-*.timer
systemctl --user daemon-reload
```

---

## 3️⃣ Python Scheduler (кроссплатформенный)

### Тестовый запуск

```bash
# Один запуск (проверка)
make scheduler-test

# Или вручную
python3 scripts/scheduler.py --once
```

### Фоновый запуск

```bash
# Запуск в фоне (daemon)
make scheduler-background

# Проверка
ps aux | grep scheduler
```

###Foreground (для отладки)

```bash
make scheduler
```

### Параметры

```bash
# Своё время запуска
python3 scripts/scheduler.py --time 10:30

# Отдельное время для apply
python3 scripts/scheduler.py --time 09:00 --apply-time 09:20

# Только boost (без apply)
python3 scripts/scheduler.py --no-apply

# Только apply (без boost)
python3 scripts/scheduler.py --no-boost
```

### Остановка

```bash
# Найти PID
ps aux | grep scheduler

# Убить процесс
kill <PID>
```

---

## 4️⃣ Docker + Cron

### Dockerfile с cron

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка cron
RUN apt-get update && apt-get install -y cron

# Копирование проекта
COPY . .

# Установка зависимостей
RUN pip install -e .

# Копирование crontab
COPY crontab /etc/cron.d/hh-applicant
RUN chmod 0644 /etc/cron.d/hh-appinant
RUN crontab /etc/cron.d/hh-applicant

# Запуск cron
CMD ["cron", "-f"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  scheduler:
    build: .
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped
```

### Запуск

```bash
docker compose up -d scheduler
docker compose logs -f scheduler
```

---

## 📊 Сравнение способов

| Критерий | cron | systemd | Python | Docker |
|----------|------|---------|--------|--------|
| **Простота** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Надёжность** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Кроссплатформенность** | macOS/Linux | Linux | Любая | Любая |
| **Логирование** | Файл | journalctl | Файл | stdout |
| **Перезапуск** | Автоматически | Автоматически | Нет | Автоматически |

---

## 🎯 Рекомендуемая конфигурация

### Для macOS (локальная разработка)

```bash
# Cron — просто и надёжно
make schedule TIME=09:00
```

### Для Linux сервера (VPS)

```bash
# systemd timer — максимальная надёжность
bash scripts/setup-systemd-timer.sh
```

### Для тестирования

```bash
# Python scheduler — один запуск
make scheduler-test
```

### Для Docker-развёртывания

```bash
# Docker + cron
docker compose up -d scheduler
```

---

## ⚠️ Важные замечания

### 1. Время запуска

- **Boost-resume**: 1 раз в 24 часа, лучше утром (9:00-10:00)
- **Apply-vacancies**: через 15-30 минут после boost

### 2. Лимиты HH.ru

- ~100-150 откликов в сутки
- Не запускай чаще 1 раза в день
- Следи за логами на предмет ошибок

### 3. Токены

- Токены могут истекать
- Раз в 1-2 недели проверяй `whoami`
- При необходимости обнови через `authorize`

### 4. Логи

```bash
# Проверка ошибок
grep -i error logs/*.log

# Последние 50 строк
tail -50 logs/apply.log
```

---

## 🔧 Troubleshooting

### Cron не работает

```bash
# Проверь cron
sudo systemctl status cron  # Linux
sudo launchctl list | grep cron  # macOS

# Логи cron
grep CRON /var/log/syslog  # Linux
log show --predicate 'process == "cron"' --last 1h  # macOS
```

### Python scheduler не запускается

```bash
# Проверь Python
which python3
python3 --version

# Проверь зависимости
python3 -m hh_applicant_tool --help

# Запусти вручную
python3 scripts/scheduler.py --once
```

### Нет логов

```bash
# Проверь права
ls -la logs/

# Создай директорию
mkdir -p logs
chmod 755 logs
```

---

## 📁 Файлы

| Файл | Назначение |
|------|------------|
| `scripts/setup-cron.sh` | Настройка cron |
| `scripts/setup-systemd-timer.sh` | Настройка systemd timer |
| `scripts/scheduler.py` | Python-планировщик |
| `logs/boost.log` | Лог поднятия резюме |
| `logs/apply.log` | Лог откликов |
| `logs/scheduler.log` | Лог планировщика |
