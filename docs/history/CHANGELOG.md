# История изменений проекта

**Последнее обновление:** 2026-01-23

---

## 2026-01-23

### ✅ Реструктуризация документации

#### Организация по категориям
- ✅ Создана структура папок для документации:
  - `guides/` — руководства (TESTING, CODE_QUALITY, SECURITY, THINKING_STREAMING, AUTONOMOUS_IMPROVER_TROUBLESHOOTING)
  - `refactoring/` — рефакторинг (REFACTORING_HISTORY, PHASE2_COMPLETION_SUMMARY, DEPENDENCIES_REFACTORING_SUMMARY)
  - `history/` — история (CHANGELOG, CODE_POLISH)
  - `tools/` — инструменты (TOOLS_INDEX, TOOLS_CATALOG)
  - `research/` — исследования (VLLM_SGLANG_ANALYSIS)
  - `setup/` — настройка (REMOTE_OLLAMA_SETUP)
  - `issues/` — проблемы (CRITICAL_ISSUES_AND_FIXES)
- ✅ Перемещены все документы по категориям (17 файлов)
- ✅ Обновлены все ссылки в документах (README.md, DOCS_INDEX.md, PROJECT_STATUS.md, CHANGELOG.md)
- ✅ Обновлен `docs/README.md` с новой структурой и навигацией

**Результат:** Документация организована логично, легко найти нужный документ по категории

---

### ✅ Рефакторинг Phase 1 и Phase 2

#### Phase 1: Критические исправления
- ✅ **Исправлен `error_handler.py`**: Заменен `asyncio.run(asyncio.sleep())` на `time.sleep()` в `sync_retry` для предотвращения блокировки event loop
- ✅ **Улучшена безопасность `code_executor.py`**: 
  - Реализован AST-based валидатор (`ASTSecurityValidator`) вместо строковых проверок
  - Добавлены ограничения памяти (128MB по умолчанию) через `resource.setrlimit`
  - Улучшена обработка временных файлов
- ✅ **Созданы тесты**: `tests/test_error_handler.py` и `tests/test_code_executor_security.py` с покрытием >80%

#### Phase 2: Архитектурные улучшения
- ✅ **Разделение `backend/routers/agent.py`**:
  - Создана структура `backend/routers/agent_handlers/`
  - Вынесены handlers: `analyze_handler.py` (187 строк), `chat_handler.py` (163 строки), `workflow_handler.py` (383 строки)
  - `agent.py` уменьшен с 2278 до 1556 строк (-32%)
- ✅ **Рефакторинг `backend/dependencies.py`**:
  - Созданы generic методы `_get_agent_with_params()` и `_get_streaming_agent_with_params()`
  - Упрощены 12 методов получения агентов (с ~15-20 строк до ~8-12 строк)
  - Устранено ~84-120 строк дублирующегося кода

#### Результаты
- ✅ Все тесты проходят (480 passed)
- ✅ Улучшена поддерживаемость кода
- ✅ Улучшена безопасность выполнения кода
- ✅ Создана документация: `PHASE1_REFACTORING_PLAN.md`, `PHASE2_REFACTORING_PLAN.md`, `PHASE2_COMPLETION_SUMMARY.md`, `DEPENDENCIES_REFACTORING_SUMMARY.md`

**Детали:** См. [docs/archive/PHASE1_REFACTORING_PLAN.md](docs/archive/PHASE1_REFACTORING_PLAN.md), [docs/refactoring/PHASE2_COMPLETION_SUMMARY.md](docs/refactoring/PHASE2_COMPLETION_SUMMARY.md), [docs/refactoring/DEPENDENCIES_REFACTORING_SUMMARY.md](docs/refactoring/DEPENDENCIES_REFACTORING_SUMMARY.md)

---

### ✅ Документация инструментов проекта

#### Документирование всех инструментов
- ✅ Создан `utils/README.md` — индекс всех утилит (13 файлов)
- ✅ Создан `scripts/README.md` — обновлен с описанием всех скриптов (9 файлов)
- ✅ Создан `scripts/SHELL_SCRIPTS.md` — документация shell скриптов
- ✅ Создан `docs/TOOLS_INDEX.md` — единый индекс всех инструментов (40+)
- ✅ Улучшены docstrings во всех утилитах с примерами использования
- ✅ Добавлен argparse help в скрипты

#### Наведение порядка в документации
- ✅ Объединены `CRITICAL_ISSUES.md` и `FIX_SUMMARY.md` → `CRITICAL_ISSUES_AND_FIXES.md`
- ✅ Перемещены мета-документы о документации в архив:
  - `DOCUMENTATION_CLEANUP_PLAN.md` (выполнен)
  - `DOCUMENTATION_CLEANUP_SUMMARY.md` (итоговая сводка)
  - `ORGANIZATION_PLAN_SIMPLE.md` (выполнен)
  - `ORGANIZATION_SUMMARY.md` (сводка планов)
  - `FIX_PLAN.md` (задачи выполнены)
  - `DOCUMENTATION_CLEANUP_2026_01_23.md` (мета-документ)
- ✅ Исправлены ссылки на несуществующий `EXECUTIVE_DASHBOARD.md`
- ✅ Обновлены ссылки на перемещенные документы во всех файлах
- ✅ Обновлен `DOCS_INDEX.md` — удалены ссылки на перемещенные документы
- ✅ Обновлен `docs/archive/README.md` — добавлена информация о мета-документах

**Детали:** См. [docs/archive/ORGANIZATION_PLAN_SIMPLE.md](docs/archive/ORGANIZATION_PLAN_SIMPLE.md)

---

## 2026-01-21

### ✅ Завершен полный рефакторинг проекта

#### Backend рефакторинг
- **Фаза 1:** Создан `BaseAgent`, устранено ~1400 строк дублирующегося кода
- **Фаза 2:** Унифицирована логика создания агентов и промптов, устранено ~450 строк дублирующегося кода
- **Итого:** Устранено ~1850 строк дублирующегося кода

#### Frontend рефакторинг
- **Фаза 1:** Создан централизованный API клиент, мигрировано 9 компонентов, устранено ~200 строк дублирующегося кода
- **Фаза 2:** Устранено дублирование типов, созданы кастомные хуки, мигрировано 4 компонента, устранено ~100 строк дублирующегося кода
- **Фаза 3:** Созданы общие UI компоненты и helper для SSE, оптимизированы компоненты, устранено ~160 строк дублирующегося кода
- **Итого:** Устранено ~460 строк дублирующегося кода

#### Общие улучшения
- Улучшена поддерживаемость кода
- Улучшена читаемость
- Улучшена типобезопасность
- Единые точки для изменений
- Упрощена поддержка и развитие

**Детали:** См. [docs/refactoring/REFACTORING_HISTORY.md](docs/refactoring/REFACTORING_HISTORY.md)

---

## Ранее

### Исправления стриминга
- Исправлены проблемы с memory leaks в EventStore
- Добавлена периодическая очистка сессий
- Улучшена обработка ошибок в reasoning_stream.py
- Добавлены missing events (thinking_completed, thinking_interrupted)

### Улучшения архитектуры
- Потокобезопасный кэш стриминговых агентов
- Централизованная конфигурация (WorkflowConfig)
- Декоратор @streaming_node для унификации стриминга
- EventStore для оптимизации памяти
- Circuit Breaker для защиты от каскадных сбоев

### Улучшения IntentAgent
- Кэширование результатов
- Калибровка confidence
- Определение языка запроса

---

**Для полной истории изменений см. git log**
