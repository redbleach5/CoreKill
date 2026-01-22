# Quick Start Checklist

Быстрый чек-лист для начала работы над улучшениями проекта Cursor Killer.

---

## 🎯 Шаг 1: Ознакомление (1-2 часа)

### Прочитать документацию
- [ ] [PROJECT_ANALYSIS_SUMMARY.md](PROJECT_ANALYSIS_SUMMARY.md) (10 минут)
- [ ] [README.md](README.md) в future/ (5 минут)
- [ ] [ROADMAP_2026.md](ROADMAP_2026.md) (15 минут)
- [ ] [QUALITY_IMPROVEMENT_PLAN.md](QUALITY_IMPROVEMENT_PLAN.md) - секция "Критические проблемы" (20 минут)

### Понять приоритеты
- [ ] Определить свою роль (разработчик/DevOps/менеджер)
- [ ] Выбрать релевантные задачи
- [ ] Согласовать с командой

---

## 🔴 СПРИНТ 1: Критические проблемы (2 недели)

### Неделя 1: Безопасность + Observability

#### День 1-2: Безопасность
- [ ] **Утро Day 1:**
  - [ ] Установить зависимости для security
    ```bash
    pip install slowapi python-jose[cryptography] passlib[bcrypt]
    ```
  - [ ] Создать `backend/security/` директорию
  - [ ] Реализовать `auth.py` (API keys)
  - [ ] Реализовать `validation.py` (input validation)

- [ ] **День Day 1:**
  - [ ] Добавить валидацию в `backend/routers/agent.py`
  - [ ] Тесты для security модуля
  - [ ] Базовый rate limiting

- [ ] **День Day 2:**
  - [ ] Документация по безопасности
  - [ ] Code review
  - [ ] Деплой на staging

#### День 3-4: Observability
- [ ] **День 3:**
  - [ ] Установить зависимости
    ```bash
    pip install prometheus-client structlog
    ```
  - [ ] Создать `infrastructure/telemetry.py`
  - [ ] Реализовать MetricsCollector
  - [ ] Добавить structured logging

- [ ] **День 4:**
  - [ ] Интеграция metrics в агенты
  - [ ] Prometheus endpoint `/metrics`
  - [ ] Базовые дашборды
  - [ ] Тесты

#### День 5: Code Review + Fixes
- [ ] Code review всего кода недели
- [ ] Исправление багов
- [ ] Обновление документации
- [ ] Демо команде

---

### Неделя 2: Рефакторинг

#### День 1-2: BaseAgent
- [ ] **День 1:**
  - [ ] Создать `agents/base.py`
  - [ ] Реализовать BaseAgent класс
  - [ ] Реализовать AgentConfig
  - [ ] Тесты для BaseAgent

- [ ] **День 2:**
  - [ ] Рефакторинг CoderAgent
  - [ ] Рефакторинг PlannerAgent
  - [ ] Тесты для рефакторенных агентов

#### День 3-4: Остальные агенты
- [ ] Рефакторинг TestGeneratorAgent
- [ ] Рефакторинг DebuggerAgent
- [ ] Рефакторинг ReflectionAgent
- [ ] Рефакторинг CriticAgent
- [ ] Тесты для всех

#### День 5: Cleanup + Review
- [ ] Удаление дублирующегося кода
- [ ] Code review
- [ ] Обновление документации
- [ ] Финальные тесты
- [ ] Деплой на staging

---

### Критерии готовности Спринта 1
- [ ] Test coverage >= 70%
- [ ] Authentication работает
- [ ] Input validation везде
- [ ] Structured logging
- [ ] Prometheus metrics доступны
- [ ] Нет critical linter warnings
- [ ] Все тесты проходят
- [ ] Документация обновлена

---

## 🟡 СПРИНТ 2: Важные улучшения (2 недели)

### Неделя 1: Context Engine v2

#### День 1-2: AST Analyzer
- [ ] Создать `infrastructure/context_engine_v2/`
- [ ] Реализовать `ast_analyzer.py`
- [ ] Тесты для AST парсинга
- [ ] Интеграция с существующим Context Engine

#### День 3-4: Dependency Graph
- [ ] Установить networkx
  ```bash
  pip install networkx
  ```
- [ ] Реализовать `dependency_graph.py`
- [ ] PageRank для важности
- [ ] Тесты

#### День 5: Интеграция
- [ ] Интеграция с ResearcherAgent
- [ ] Кэширование графа
- [ ] Performance тесты
- [ ] Документация

---

### Неделя 2: Learning System + Performance

#### День 1-2: Learning System
- [ ] Создать `infrastructure/learning_system.py`
- [ ] SQLite schema
- [ ] CRUD operations
- [ ] Интеграция в workflow

#### День 3-4: Performance
- [ ] Connection pooling для Ollama
- [ ] LRU cache для частых запросов
- [ ] Оптимизация промптов
- [ ] Benchmark тесты

#### День 5: Review
- [ ] Code review
- [ ] Performance profiling
- [ ] Документация
- [ ] Деплой

---

### Критерии готовности Спринта 2
- [ ] Context Engine v2 работает
- [ ] AST парсинг для Python
- [ ] Граф зависимостей строится
- [ ] Learning System записывает данные
- [ ] Performance улучшен на 20-30%
- [ ] Тесты проходят
- [ ] Документация

---

## 🟢 СПРИНТ 3: Дополнительные фичи (2 недели)

### Неделя 1: Frontend + Testing

#### День 1-2: ThinkingBlock компонент
- [ ] Создать `frontend/src/components/ThinkingBlock.tsx`
- [ ] Интеграция в MessageList
- [ ] Стили и анимации
- [ ] Тесты (vitest)

#### День 3-4: ProgressBar + улучшения
- [ ] WorkflowProgress компонент
- [ ] Интеграция с SSE
- [ ] Улучшение UX
- [ ] Accessibility (WCAG)

#### День 5: Testing
- [ ] Написать unit тесты для недостающих модулей
- [ ] Integration тесты
- [ ] Достичь 80% coverage
- [ ] Load тесты (locust)

---

### Неделя 2: Code Retrieval

#### День 1-2: CodeRetriever
- [ ] Установить зависимости
  ```bash
  pip install sentence-transformers
  ```
- [ ] Создать `infrastructure/code_retrieval.py`
- [ ] Реализовать CodeRetriever
- [ ] Тесты

#### День 3-4: Интеграция
- [ ] Интеграция в CoderAgent
- [ ] Периодическая индексация
- [ ] GitHub Code Search (опционально)
- [ ] Тесты

#### День 5: Polish + Review
- [ ] Code review
- [ ] Документация
- [ ] Примеры использования
- [ ] Деплой

---

### Критерии готовности Спринта 3
- [ ] ThinkingBlock работает в UI
- [ ] ProgressBar показывает этапы
- [ ] Test coverage >= 80%
- [ ] E2E тесты проходят
- [ ] Code Retrieval работает
- [ ] Качество генерации улучшено
- [ ] Документация

---

## 📊 Ежедневные ритуалы

### Каждое утро (15 минут)
- [ ] Standup: что сделано вчера, что сегодня, блокеры
- [ ] Обновить GitHub project board
- [ ] Проверить CI/CD статус

### В течение дня
- [ ] Commit часто (atomic commits)
- [ ] Писать тесты вместе с кодом
- [ ] Обновлять документацию
- [ ] Code review для коллег

### Каждый вечер (10 минут)
- [ ] Проверить что все тесты проходят
- [ ] Push все изменения
- [ ] Обновить задачи в project board
- [ ] Записать заметки для завтра

---

## 🔧 Инструменты разработки

### IDE Setup
```bash
# VS Code extensions
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
code --install-extension esbenp.prettier-vscode
```

### Pre-commit hooks
```bash
pip install pre-commit
pre-commit install
```

### Running tests
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=agents --cov=infrastructure --cov-report=html

# Specific test
pytest tests/test_coder.py -v

# Watch mode
pytest-watch tests/
```

### Linting
```bash
# Ruff (fast)
ruff check .

# MyPy (type checking)
mypy . --strict

# Format code
ruff format .
```

---

## 📋 Git Workflow

### Branch naming
```
feature/security-api-keys
fix/bug-ollama-timeout
refactor/base-agent
docs/update-readme
```

### Commit messages (Conventional Commits)
```
feat: add API key authentication
fix: resolve Ollama timeout issue
refactor: extract BaseAgent class
docs: update security documentation
test: add tests for BaseAgent
chore: update dependencies
```

### PR Template
```markdown
## Description
Brief description of changes

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring
- [ ] Documentation

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No linter warnings
- [ ] Code reviewed

## Related Issues
Fixes #123
```

---

## 🎯 Definition of Done

### Для любой задачи
- [ ] Код написан
- [ ] Тесты написаны и проходят
- [ ] Linter проходит без warnings
- [ ] Type hints добавлены
- [ ] Документация обновлена
- [ ] Code review пройден
- [ ] CI/CD проходит
- [ ] Задача закрыта в project board

### Для feature
- [ ] + E2E тест
- [ ] + Performance не деградировал
- [ ] + Backward compatibility
- [ ] + Migration guide (если нужно)

### Для bugfix
- [ ] + Regression тест
- [ ] + Root cause analysis
- [ ] + Prevention plan

---

## 💡 Советы

### Продуктивность
1. **Time-boxing:** 25 минут работы, 5 минут отдых (Pomodoro)
2. **Focus time:** Блокируй 2-3 часа для глубокой работы
3. **Pair programming:** Для сложных задач
4. **Breaks:** Каждый час - короткий перерыв

### Качество кода
1. **KISS:** Keep It Simple, Stupid
2. **DRY:** Don't Repeat Yourself
3. **YAGNI:** You Aren't Gonna Need It
4. **Test First:** TDD подход
5. **Small PRs:** Легче ревьювить

### Communication
1. **Over-communicate:** Лучше лишний раз спросить
2. **Document decisions:** ADR (Architecture Decision Records)
3. **Ask for help:** Не стесняйтесь
4. **Share knowledge:** Pair programming, tech talks

---

## 🆘 Troubleshooting

### Тесты не проходят
```bash
# Очистить кэш
pytest --cache-clear

# Verbose output
pytest -vv

# Конкретный тест
pytest tests/test_file.py::test_function -vv
```

### Linter errors
```bash
# Auto-fix
ruff check . --fix

# Format
ruff format .

# Ignore specific rule (не злоупотребляйте)
# noqa: E501
```

### Type checking errors
```bash
# Incremental
mypy .

# Full re-check
mypy . --no-incremental

# Ignore specific error
# type: ignore[error-code]
```

---

## ✅ Финальный чеклист перед production

### Безопасность
- [ ] Authentication реализован
- [ ] Input validation везде
- [ ] Rate limiting
- [ ] HTTPS в production
- [ ] Secrets не в коде
- [ ] Security audit пройден

### Производительность
- [ ] Load testing пройден
- [ ] Latency < целевого
- [ ] Memory usage в норме
- [ ] Connection pooling работает

### Надёжность
- [ ] Test coverage >= 80%
- [ ] Zero critical bugs
- [ ] Error handling везде
- [ ] Graceful degradation
- [ ] Backup strategy

### Мониторинг
- [ ] Structured logging
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Alerts настроены
- [ ] On-call rotation

### Документация
- [ ] README актуален
- [ ] API docs (OpenAPI)
- [ ] Deployment guide
- [ ] Runbook для инцидентов
- [ ] Changelog

---

**Готовы начать?** Начните с [PROJECT_ANALYSIS_SUMMARY.md](PROJECT_ANALYSIS_SUMMARY.md)!

---

**Обновлено:** 2026-01-21  
**Версия:** 1.0
