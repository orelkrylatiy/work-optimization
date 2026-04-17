# Linting Configuration

Проект использует комплексный подход к контролю качества кода с несколькими инструментами.

## Инструменты

### 1. **Ruff** — основной линтер
- Быстрая проверка кода на стиль и ошибки
- **Правила**: E (PEP8), F (Pyflakes), B (Bug bear), I (isort), UP (pyupgrade), SIM (simplify)
- **Конфиг**: `pyproject.toml` → `[tool.ruff]`
- **Игнорируемые**: E501 (длина строк), E731 (лямбды), B008 (вызовы в аргументах)

### 2. **Isort** — сортировка импортов
- Автоматически организует импорты в порядке: стандартная библиотека → external → local
- **Конфиг**: `.pre-commit-config.yaml`
- **Профиль**: `black`

### 3. **Pylint** — глубокий анализ кода
- Проверка качества, сложности, стиля
- **Конфиг**: `.pylintrc`
- **Макет**: max-line-length=100, max-arguments=5, max-statements=50
- **Отключено**: missing docstrings, некоторые style-правила

### 4. **Pre-commit Hooks** — автоматическая проверка перед коммитом
- Автоматическое исправление: `ruff --fix`, `isort`, `ruff format`
- Валидация: YAML, JSON, merge conflicts, large files
- **Конфиг**: `.pre-commit-config.yaml`

## Использование

### Локальная разработка

```bash
# 1. Установить dev зависимости и pre-commit hooks
make dev

# 2. Проверить код на ошибки (только чтение)
make lint

# 3. Автоматически исправить ошибки
make format

# 4. Быстрое исправление (только ruff + isort)
make lint-fix

# 5. Полная проверка (lint + typecheck + test)
make ci
```

### CI/CD Pipeline

Все проверки автоматически запускаются при push/PR в `.github/workflows/ci.yml`:
- ✅ **Lint job**: ruff, isort, pylint
- ✅ **Typecheck job**: basedpyright
- ✅ **Test job**: pytest с покрытием
- ✅ **Docker job**: построение образа

## Конфигурационные файлы

| Файл | Назначение |
|------|-----------|
| `pyproject.toml` | Конфиги ruff, pytest, coverage, pyright |
| `.pylintrc` | Настройки pylint |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `.editorconfig` | Единые стили в разных редакторах |

## Игнорирование правил

### Для одной строки:
```python
# pylint: disable=line-too-long
some_very_long_line_that_exceeds_limit()
```

### Для файла:
```python
# pylint: disable=missing-docstring
```

### Для ruff (старый способ):
```python
value = lambda x: x + 1  # noqa: E731
```

## Настройка в IDE

### VS Code
Установить расширения:
- Pylance (для type checking)
- Ruff (для линтинга)
- isort (для сортировки импортов)

### PyCharm
- Встроенная поддержка ruff/pylint
- Настроить line width в Settings → Editor → Code Style → Python (100 символов)

## Troubleshooting

**Ошибка: "pre-commit not installed"**
```bash
poetry install --with dev
poetry run pre-commit install
```

**Pre-commit hooks не запускаются автоматически**
```bash
poetry run pre-commit install
# или полная переустановка
rm .git/hooks/pre-commit
poetry run pre-commit install
```

**Исправить все ошибки сразу**
```bash
make format
git add -A
git commit
```

## Performance Tips

- Ruff работает за миллисекунды (очень быстро)
- Pylint медленнее, будет выполняться несколько секунд
- Чтобы ускорить локальную разработку, используйте `make lint-fix` (только ruff + isort)
- Полная проверка `make lint` запускается в CI для всех PR
