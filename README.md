# HH Applicant Tool

Утилита для автоматизации работы с [HeadHunter](https://hh.ru): рассылка откликов на вакансии, обновление резюме, сохранение контактов в локальной базе данных.

## ✨ Ключевые возможности

- **Автоматическая рассылка откликов** — на подходящие вакансии без участия человека
- **Обновление резюме** — поднимаем резюме в поиске работодателей
- **AI-фильтрация вакансий** — автоматический отсев неподходящих предложений (два режима: `heavy` и `light`)
- **Генерация сопроводительных писем** — через ChatGPT/OpenAI для персонализации откликов
- **Локальная база данных** — все контакты и информация о вакансиях хранятся локально (SQLite)
- **Технология эмуляции** — работает как официальное Android-приложение, избегая блокировок
- **CLI + Web UI** — команднострочный интерфейс и веб-админ панель для управления
- **Поддержка нескольких профилей** — работа с несколькими аккаунтами и резюме
- **Docker** — легко развернуть на сервере или VPS
- **Scriptable** — использование в своих Python-скриптах

## 📋 Содержание

- [Требования](#требования)
- [Установка](#установка)
- [Авторизация](#авторизация)
- [Использование](#использование)
- [Веб-админ панель](#веб-админ-панель)
- [Конфигурация](#конфигурация)
- [Шаблоны сообщений](#шаблоны-сообщений)
- [Использование в скриптах](#использование-в-скриптах)

## 📌 Требования

- Python >= 3.11
- Git
- Docker (опционально)

## 📦 Установка

### Через pipx (рекомендуется)

```bash
# С поддержкой авторизации (Playwright + браузер)
pipx install 'hh-applicant-tool[playwright]'

# С поддержкой sixel для вывода капчи в терминал
pipx install 'hh-applicant-tool[playwright,pillow]'

# Для обновления
pipx upgrade hh-applicant-tool
```

### Через виртуальное окружение

```bash
python -m venv venv
. venv/bin/activate  # или venv\Scripts\activate на Windows
pip install 'hh-applicant-tool[playwright]'
```

### Установка зависимостей для авторизации

```bash
hh-applicant-tool install
```

### Docker (рекомендуется для сервера)

**Преимущества:** Легко развернуть на VPS/сервере, не нужна установка Python локально.

#### Начальная настройка

Установите Docker и Docker Compose:

```bash
sudo apt install docker.io docker-compose-v2
```

Получите репозиторий:

```bash
git clone https://github.com/s3rgeym/hh-applicant-tool
cd hh-applicant-tool
```

#### Авторизация

```bash
# Способ 1: По коду подтверждения
docker-compose run -u docker -it hh_applicant_tool \
  hh-applicant-tool auth

# Способ 2: По логину и паролю
docker-compose run -u docker -it hh_applicant_tool \
  hh-applicant-tool auth '<email>' -p '<password>'

# Способ 3: С выводом капчи в терминал (Kitty protocol)
docker-compose run -u docker -it hh_applicant_tool \
  hh-applicant-tool auth --use-kitty
```

#### Запуск сервиса

```bash
# Запустить в фоне (будет автозапускаться при перезагрузке)
docker-compose up -d

# Просмотр логов в реальном времени
docker-compose logs -f

# Остановить сервис
docker-compose down
```

Сервис будет:
- Рассылать отклики на рекомендуемые вакансии
- Автоматически поднимать резюме через cron

#### Работа с несколькими профилями

Если нужно работать с несколькими аккаунтами, отредактируйте `docker-compose.yml`:

```yaml
services:
  hh_applicant_tool:
    # ... основной сервис ...

  hh_second:
    extends: hh_applicant_tool
    container_name: hh_second
    environment:
      - HH_PROFILE_ID=second

  hh_third:
    extends: hh_applicant_tool
    container_name: hh_third
    environment:
      - HH_PROFILE_ID=third
```

Авторизуйте каждый профиль:

```bash
docker-compose exec -u docker -it hh_applicant_tool \
  hh-applicant-tool --profile second auth

docker-compose exec -u docker -it hh_applicant_tool \
  hh-applicant-tool --profile third auth
```

Затем запустите все профили:

```bash
docker-compose up -d
```

#### Тестирование

Войдите в контейнер и тестируйте команды:

```bash
docker-compose exec -u docker -it hh_applicant_tool bash

# Внутри контейнера:
hh-applicant-tool whoami
hh-applicant-tool config -p
hh-applicant-tool refresh-token
```

#### Обновление

```bash
# Обновить код
git pull

# Пересобрать контейнер
docker-compose up -d --build

# Просмотр логов обновления
docker-compose logs
```

#### Файлы конфигурации

Все данные хранятся в `config/`:
- `config.json` — токены и настройки
- `data` — SQLite база данных
- `log.txt` — логи
- `cookies.txt` — пользовательские куки

> ⚠️ **Важно:** Команды `docker-compose` нужно запускать из директории проекта!

## 🔐 Авторизация

### Способ 1: По коду подтверждения

```bash
hh-applicant-tool authorize '<ваш email или телефон>'
```

СМС/письмо с кодом придёт на указанный номер/почту.

### Способ 2: По логину и паролю

```bash
hh-applicant-tool authorize '<email>' -p '<пароль>'
```

### Способ 3: С вводом капчи в терминал

Если при авторизации требуется капча, используйте флаги для вывода в терминал:

```bash
hh-applicant-tool authorize --use-kitty
# или
hh-applicant-tool authorize --use-sixel
```

### Проверка авторизации

```bash
hh-applicant-tool whoami
```

## 🚀 Использование

### Рассылка откликов

```bash
# Рассылать на рекомендуемые вакансии
hh-applicant-tool apply-vacancies

# Поиск по ключевому слову
hh-applicant-tool apply-vacancies --search "Python backend"

# Режим тестирования (отклики не отправляются)
hh-applicant-tool apply-vacancies --search "Python" --dry-run

# С AI-фильтрацией вакансий
hh-applicant-tool apply-vacancies --ai-filter heavy

# С генерацией сопроводительных писем
hh-applicant-tool apply-vacancies --ai
```

### Обновление резюме

```bash
# Поднять все резюме в поиске
hh-applicant-tool update-resumes

# Просмотр списка резюме
hh-applicant-tool list-resumes
```

### Остальные команды

```bash
# Просмотр логов в реальном времени
hh-applicant-tool log -f

# Просмотр конфигурации
hh-applicant-tool config -p

# SQL-запросы к базе данных
hh-applicant-tool query 'SELECT COUNT(*) FROM negotiations'

# Обновить токен доступа
hh-applicant-tool refresh-token

# Справка
hh-applicant-tool -h
```

## 🌐 Веб-админ панель

Форк добавляет встроенную веб-панель для управления утилитой (FastAPI).

### Запуск веб-админ панели

```bash
python -m uvicorn admin.app:app --host 0.0.0.0 --port 8000
```

Откройте в браузере: `http://localhost:8000`

### Функциональность панели

- 📊 **Статистика** — общие числа откликов, исходящих статусы, график по дням
- 📋 **Переговоры** — список откликов, фильтрация по статусу
- 💼 **Вакансии** — просмотр сохранённых вакансий, поиск
- 🏢 **Работодатели** — контакты и статустика по компаниям
- ⏭️ **Пропущенные** — вакансии, отклонённые фильтром или AI
- ⚙️ **Конфигурация** — редактирование параметров без консоли
- 📝 **Логи** — просмотр последних записей
- ▶️ **Операции** — запуск `apply-vacancies` и `update-resumes` с UI
- 🔐 **Авторизация и профили** — добавление нового профиля, выход из текущего аккаунта и повторный вход теперь доступны прямо из админки

## ⚙️ Конфигурация

Конфиг хранится в файле `config.json`:

| ОС | Путь |
|---|---|
| **Windows** | `C:\Users\%username%\AppData\Roaming\hh-applicant-tool\` |
| **macOS** | `~/Library/Application Support/hh-applicant-tool/` |
| **Linux** | `~/.config/hh-applicant-tool/` |

### Редактирование конфига

```bash
# Открыть в редакторе
hh-applicant-tool config -e

# Просмотреть путь
hh-applicant-tool config -p

# Установить значение
hh-applicant-tool config -s proxy_url "socks5://localhost:1080"

# Уточнить значение
hh-applicant-tool config -k token.access_token
```

### Параметры конфига

```json
{
  "proxy_url": "socks5://localhost:1080",
  "api_delay": 0.5,
  "openai_cover_letter": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_completion_tokens": 1000
  },
  "openai_vacancy_filter": {
    "api_key": "sk-...",
    "model": "gpt-4o-mini",
    "temperature": 0.1
  },
  "smtp": {
    "host": "smtp.yandex.ru",
    "port": 465,
    "user": "your_email@yandex.ru",
    "password": "app_password",
    "ssl": true
  }
}
```

## 📝 Шаблоны сообщений

Поддерживаются плейсхолдеры при написании сообщений в откликах и ответах:

- `%(vacancy_name)s` — название вакансии
- `%(employer_name)s` — название компании
- `%(first_name)s` — ваше имя
- `%(last_name)s` — ваша фамилия
- `%(email)s` — ваша почта
- `%(resume_title)s` — название резюме
- `%(resume_url)s` — ссылка на резюме

### Случайные варианты

Для создания уникальных сообщений используйте синтаксис `{вариант1|вариант2}`:

```
Здравствуйте! {Меня заинтересовала|Прошу рассмотреть} ваша вакансия %(vacancy_name)s.
```

## 🐍 Использование в скриптах

```python
from hh_applicant_tool import HHApplicantTool

tool = HHApplicantTool([
    "--proxy-url", "socks5://localhost:1080",
])

# Работа с API
user_info = tool.api_client.get('/me')
print(user_info)

# Сохранение настроек
import datetime as dt
tool.storage.settings.set_value("_last_run", dt.datetime.now())
tool.save_token()
```

## 📊 Локальная база данных

Все данные хранятся в SQLite файле `data`:

- 📌 Просмотренные вакансии
- 👥 Профили работодателей
- 📞 Контакты работодателей
- 📮 История откликов
- 🚫 Пропущенные вакансии (с причинами)

### SQL-запросы

```bash
# Сколько откликов отправлено
hh-applicant-tool query 'SELECT COUNT(*) FROM negotiations'

# Последние 10 откликов
hh-applicant-tool query 'SELECT * FROM negotiations ORDER BY created_at DESC LIMIT 10'

# Экспорт в CSV
hh-applicant-tool query 'SELECT * FROM negotiations' --csv -o negotiations.csv
```

## 🛠️ Разработка

### Установка для разработки

```bash
git clone https://github.com/s3rgeym/hh-applicant-tool
cd hh-applicant-tool
poetry install --with dev
```

### Запуск тестов

```bash
pytest
```

### Проверка кода

```bash
ruff check .
pylint src/
```

## 📄 Лицензия

[Limited Non-Commercial License](./LICENSE) — личное использование, запрещена коммерческая эксплуатация.

## 🙏 Спасибо

Проект основан на [оригинальном hh-applicant-tool](https://github.com/s3rgeym/hh-applicant-tool) от [s3rgeym](https://github.com/s3rgeym).
