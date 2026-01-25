# 🔧 Единый индекс инструментов проекта

**Обновлено:** 2026-01-23  
**Всего инструментов:** 40+

---

## 📋 Содержание

- [Утилиты (utils/)](#утилиты-utils)
- [Скрипты (scripts/)](#скрипты-scripts)
- [Shell скрипты](#shell-скрипты)
- [CLI интерфейсы](#cli-интерфейсы)
- [Autonomous Improver скрипты](#autonomous-improver-скрипты)

---

## 🛠️ Утилиты (utils/)

**Документация:** [utils/README.md](../utils/README.md)

### Критичные утилиты ⭐

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `logger.py` | Система логирования | ✅ [utils/README.md#loggerpy](../utils/README.md#loggerpy) |
| `config.py` | Работа с конфигурацией | ✅ [utils/README.md#configpy](../utils/README.md#configpy) |
| `model_checker.py` | Проверка моделей Ollama | ✅ [utils/README.md#model_checkerpy](../utils/README.md#model_checkerpy) |
| `path_validator.py` | Валидация путей (безопасность) | ✅ [utils/README.md#path_validatorpy](../utils/README.md#path_validatorpy) |

### Утилиты для работы с данными

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `db_cli.py` | CLI для управления БД | ✅ [README.md#управление-базами-данных](../README.md#управление-базами-данных) |
| `artifact_saver.py` | Сохранение артефактов | ✅ [utils/README.md#artifact_saverpy](../utils/README.md#artifact_saverpy) |
| `token_counter.py` | Подсчет токенов | ✅ [utils/README.md#token_counterpy](../utils/README.md#token_counterpy) |

### Утилиты для работы с файлами

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `file_context.py` | Работа с файлами (modify/debug) | ✅ [utils/README.md#file_contextpy](../utils/README.md#file_contextpy) |

### Утилиты для моделей и LLM

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `intent_helpers.py` | Хелперы для intent агента | ✅ [utils/README.md#intent_helperspy](../utils/README.md#intent_helperspy) |
| `structured_helpers.py` | Хелперы для structured output | ✅ [utils/README.md#structured_helperspy](../utils/README.md#structured_helperspy) |

### Утилиты для валидации

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `validation.py` | Валидация кода (pytest, mypy, bandit) | ✅ [utils/README.md#validationpy](../utils/README.md#validationpy) |

### Утилиты для UI и конфигурации

| Утилита | Назначение | Документация |
|---------|------------|--------------|
| `ui_delays.py` | Управление задержками UI | ✅ [utils/README.md#ui_delayspy](../utils/README.md#ui_delayspy) |
| `env_config.py` | Конфигурация из переменных окружения | ✅ [utils/README.md#env_configpy](../utils/README.md#env_configpy) |

---

## 📜 Скрипты (scripts/)

**Документация:** [scripts/README.md](../scripts/README.md)

### Скрипты анализа и проверки

| Скрипт | Назначение | Документация |
|--------|------------|--------------|
| `analyze_dependencies.py` | Анализ зависимостей | ✅ [scripts/README.md#analyze_dependenciespy](../scripts/README.md#analyze_dependenciespy) |
| `check_imports.py` | Проверка импортов (frontend) | ✅ [scripts/README.md#check_importspy](../scripts/README.md#check_importspy) |
| `check_undefined.py` | Проверка неопределенных переменных | ✅ [scripts/README.md#check_undefinedpy](../scripts/README.md#check_undefinedpy) |
| `check_refactoring_imports.py` | Проверка импортов после рефакторинга | ✅ [scripts/README.md#check_refactoring_importspy](../scripts/README.md#check_refactoring_importspy) |
| `check_imports.js` | Проверка импортов (Node.js) | ✅ [scripts/README.md#check_importsjs](../scripts/README.md#check_importsjs) |

### Тестовые скрипты

| Скрипт | Назначение | Документация |
|--------|------------|--------------|
| `test_thinking_streaming.py` | Тесты thinking стриминга | ✅ [scripts/README.md#test_thinking_streamingpy](../scripts/README.md#test_thinking_streamingpy) |
| `test_thinking_integration.py` | Интеграционные тесты thinking | ✅ [scripts/README.md#test_thinking_integrationpy](../scripts/README.md#test_thinking_integrationpy) |
| `test_autonomous_improver_logic.py` | Тесты Autonomous Improver | ✅ [scripts/README.md#test_autonomous_improver_logicpy](../scripts/README.md#test_autonomous_improver_logicpy) |

---

## 🐚 Shell скрипты

**Документация:** [scripts/SHELL_SCRIPTS.md](../scripts/SHELL_SCRIPTS.md)

### Скрипты в корне проекта

| Скрипт | Назначение | Документация |
|--------|------------|--------------|
| `run_improver.sh` | Запуск Autonomous Improver | ✅ [scripts/SHELL_SCRIPTS.md#run_improversh](../scripts/SHELL_SCRIPTS.md#run_improversh) |
| `setup_models.sh` | Установка моделей Ollama | ✅ [scripts/SHELL_SCRIPTS.md#setup_modelssh](../scripts/SHELL_SCRIPTS.md#setup_modelssh) |

### Скрипты в scripts/

| Скрипт | Назначение | Документация |
|--------|------------|--------------|
| `start_improver_test.sh` | Запуск теста Autonomous Improver | ✅ [scripts/SHELL_SCRIPTS.md#start_improver_testsh](../scripts/SHELL_SCRIPTS.md#start_improver_testsh) |
| `RUN_TEST.sh` | Запуск тестов (общий) | ✅ [scripts/SHELL_SCRIPTS.md#run_testsh](../scripts/SHELL_SCRIPTS.md#run_testsh) |

---

## 💻 CLI интерфейсы

| CLI | Назначение | Документация |
|-----|------------|--------------|
| `cli.py` | CLI для многоагентной системы | ✅ [cli.py](../cli.py) |
| `utils/db_cli.py` | CLI для управления БД | ✅ [README.md#управление-базами-данных](../README.md#управление-базами-данных) |

---

## 🤖 Autonomous Improver скрипты

**Документация:** [infrastructure/autonomous_improver/README.md](../infrastructure/autonomous_improver/README.md#скрипты)

| Скрипт | Назначение | Документация |
|--------|------------|--------------|
| `scripts/test.py` | Тестовый скрипт | ✅ [README.md#scriptstestpy](../infrastructure/autonomous_improver/README.md#scriptstestpy) |
| `scripts/analyze_results.py` | Анализ результатов | ✅ [README.md#scriptsanalyze_resultspy](../infrastructure/autonomous_improver/README.md#scriptsanalyze_resultspy) |
| `scripts/run.sh` | Shell скрипт запуска | ✅ [README.md#scriptsrunsh](../infrastructure/autonomous_improver/README.md#scriptsrunsh) |

---

## 📊 Статистика

- **Всего инструментов:** 40+
- **Утилиты:** 13
- **Скрипты:** 9
- **Shell скрипты:** 4
- **CLI:** 2
- **Autonomous Improver:** 3

### Статус документации

- ✅ **Задокументированы:** 40+ (100%)
- ⚠️ **Частично задокументированы:** 0
- ❌ **Не задокументированы:** 0

---

## 🔍 Быстрый поиск

### По назначению

**Логирование:**
- `utils/logger.py` — система логирования

**Конфигурация:**
- `utils/config.py` — конфигурация из config.toml
- `utils/env_config.py` — конфигурация из переменных окружения

**Модели:**
- `utils/model_checker.py` — проверка и выбор моделей Ollama

**Безопасность:**
- `utils/path_validator.py` — валидация путей (path traversal защита)

**Проверка кода:**
- `scripts/check_imports.py` — проверка импортов
- `scripts/check_undefined.py` — проверка неопределенных переменных
- `utils/validation.py` — валидация кода (pytest, mypy, bandit)

**Анализ:**
- `scripts/analyze_dependencies.py` — анализ зависимостей
- `infrastructure/autonomous_improver/scripts/analyze_results.py` — анализ результатов

**Тестирование:**
- `scripts/test_thinking_streaming.py` — тесты thinking стриминга
- `scripts/test_autonomous_improver_logic.py` — тесты Autonomous Improver

**Запуск:**
- `run_improver.sh` — запуск Autonomous Improver
- `cli.py` — CLI интерфейс

---

## 🔗 Связанные документы

- [Каталог всех инструментов](TOOLS_CATALOG.md) — детальный каталог
- [План организации](archive/ORGANIZATION_PLAN_SIMPLE.md) — план документирования (в архиве)
- [Утилиты (utils/)](../utils/README.md) — документация утилит
- [Скрипты (scripts/)](../scripts/README.md) — документация скриптов
- [Shell скрипты](../scripts/SHELL_SCRIPTS.md) — документация shell скриптов
- [Autonomous Improver](../infrastructure/autonomous_improver/README.md) — документация Autonomous Improver

---

**Последнее обновление:** 2026-01-23
