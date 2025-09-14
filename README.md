# Telegram Bots Portfolio — Starter

[![CI](https://github.com/LizardKing131313/tg_bots/actions/workflows/ci.yml/badge.svg)](https://github.com/LizardKing131313/tg_bots/actions/workflows/ci.yml)
[![Qodana](https://github.com/LizardKing131313/tg_bots/actions/workflows/qodana_code_quality.yml/badge.svg)](https://github.com/LizardKing131313/tg_bots/actions/workflows/qodana_code_quality.yml)
![Coverage](badges/coverage.svg)

Стартовый шаблон монорепозитория под 10 телеграм-ботов на **aiogram 3**.
Готовы два бота: `echo_bot` (базовый пример) и `questionnaire_bot` (FSM).

## Рекомендуемая подготовка окружения

```bash
pip install -U pip setuptools wheel
# опционально
pip install -U pip-tools
```

## Быстрый старт (dev, long-polling)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -U pip setuptools wheel
pip install -e ".[dev]"

cd bots/echo_bot && python -m app
```

## Логи

- Консоль — цветной вывод (если установлен `colorlog`).
- Файл с ротацией по дням — `logs/bot.log` (по умолчанию),
  хранится `LOG_BACKUP_DAYS` дней.

Переменные окружения:

```env
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log
LOG_BACKUP_DAYS=7
```

Установка colorlog (опционально):

```bash
pip install colorlog
```

## Стек

- Python 3.11+
- aiogram 3
- pydantic 2 + pydantic-settings
- python-dotenv
- httpx
- pre-commit (Ruff + Black хуки)
- pytest (юнит-тесты)

## CI (GitHub Actions)

В репозитории уже есть workflow `.github/workflows/ci.yml`, который при каждом push/PR:

- ставит зависимости (`pip install -e ".[dev]"`),
- гоняет **Ruff** (`ruff check .`),
- проверяет формат **Black** (`black --check .`),
- запускает **pytest** (пока тестов нет, этап «зелёный»).

## IntelliJ IDEA: запуск pre-commit перед коммитом

**Settings → Version Control → Commit → Before Commit**:

- включи **Run Git Hooks** (если доступно), либо добавь External Tool на:

  ```bash
  pre-commit run --files $ChangedFiles$
  ```

- при желании включи **Run tests** и **Run inspection**.

## Линтинг, форматирование и тесты

В проекте настроены **Ruff** (линтер) и
**Black** (форматтер), а также pre-commit хуки.

### Установка зависимостей и активация хуков

```bash
make setup
# или вручную:
# pip install -U pre-commit ruff black
# pre-commit install
```

### Проверить код

```bash
make lint
```

### Автоматически исправить и отформатировать

```bash
make fix
```

### Запустить тесты

```bash
make test
```

### Проверить и протестировать (режим CI)

```bash
make ci
```

> Все конфигурации Ruff и Black лежат в `pyproject.toml`.
> `.editorconfig` содержит только базовые настройки редактора.

## Структура репозитория

```ignorelang
tg-bots-portfolio-starter/
  bots/
    echo_bot/
    questionnaire_bot/
  libs/
    common/
  .github/workflows/ci.yml
  Makefile
  pyproject.toml
  .pre-commit-config.yaml
  .editorconfig
  .gitignore
  README.md
```
