# 📚 Документация проекта: Путеводитель

**Обновлено:** 2026-01-21  
**Версия:** 2.1 (после очистки документации)

---

## 🎯 Начать здесь

### Для менеджмента
**→ [EXECUTIVE_DASHBOARD.md](EXECUTIVE_DASHBOARD.md)** — главный документ
- Текущий статус проекта (7/10)
- Критические проблемы
- План на ближайшие спринты
- Метрики и бюджет

**Время чтения:** 10 минут

---

### Для разработчиков
**→ [future/IMPLEMENTATION_STATUS.md](future/IMPLEMENTATION_STATUS.md)** — что сделано и что делать
- ✅ Фазы 1-6 реализованы
- 📋 Фаза 7: Under The Hood (5 дней)
- 🔴 Критические задачи (Security, Observability)

**Время чтения:** 15 минут

---

### Для архитекторов
**→ [ARCHITECTURE.md](ARCHITECTURE.md)** — архитектура системы  
**→ [future/SCALABILITY_AND_ARCHITECTURE_PLAN.md](future/SCALABILITY_AND_ARCHITECTURE_PLAN.md)** — план масштабирования

**Время чтения:** 30 минут

---

## 📂 Структура документации

```
/
├── README.md                    # Главный README проекта
├── EXECUTIVE_DASHBOARD.md       # ⭐ ГЛАВНЫЙ - для менеджмента
├── ARCHITECTURE.md              # Архитектура системы
├── DEPLOYMENT.md                # Деплой
├── DEPRECATION.md               # Устаревший код
├── DOCS_INDEX.md                # 👈 ВЫ ЗДЕСЬ - индекс документации
│
└── future/                      # Планы и roadmap
    ├── README.md                # Индекс файлов в future/
    ├── IMPLEMENTATION_STATUS.md # ⭐ Актуальный статус всех фич
    ├── ROADMAP_2026.md          # Roadmap (7 фаз)
    ├── UNDER_THE_HOOD_VISUALIZATION.md  # Фаза 7 (5 дней)
    ├── QUALITY_IMPROVEMENT_PLAN.md      # План улучшений
    ├── SCALABILITY_AND_ARCHITECTURE_PLAN.md  # Масштабирование
    ├── QUICK_START_CHECKLIST.md # Quick start
    │
    ├── code_retrieval.md        # ✅ Фаза 4 (реализовано)
    ├── multi_agent_debate.md    # ✅ Фаза 5 (реализовано)
    ├── context_engine_ast_parsing.md  # ✅ Фаза 6 (реализовано)
    ├── tree_sitter_multilang.md # 🔮 Будущее
    ├── russia.md                # РФ специфика
    ├── unreal.md                # Идеи для вдохновения
    └── legacy_architecture_contract.md  # Паттерны из старых проектов
```

---

## 🚀 Быстрый старт

### Хочу понять проект за 10 минут
1. [EXECUTIVE_DASHBOARD.md](EXECUTIVE_DASHBOARD.md)
2. [future/IMPLEMENTATION_STATUS.md](future/IMPLEMENTATION_STATUS.md)

### Хочу начать разработку
1. [README.md](README.md) — установка и запуск
2. [future/QUICK_START_CHECKLIST.md](future/QUICK_START_CHECKLIST.md)
3. [future/IMPLEMENTATION_STATUS.md](future/IMPLEMENTATION_STATUS.md) — выбрать задачу

### Хочу понять архитектуру
1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [future/SCALABILITY_AND_ARCHITECTURE_PLAN.md](future/SCALABILITY_AND_ARCHITECTURE_PLAN.md)

---

## 📋 Что реализовано

| Фаза | Название | Статус | Документ |
|------|----------|--------|----------|
| 1 | Reasoning Models | ✅ 100% | Встроено в систему |
| 2 | Structured Output | ✅ 100% | Встроено в систему |
| 3 | Compiler-in-the-Loop | ✅ 100% | Встроено в систему |
| 4 | Code Retrieval | ✅ 100% | [code_retrieval.md](future/code_retrieval.md) |
| 5 | Multi-Agent Debate | ✅ 100% | [multi_agent_debate.md](future/multi_agent_debate.md) |
| 6 | AST Analysis | ✅ 100% | [context_engine_ast_parsing.md](future/context_engine_ast_parsing.md) |
| **7** | **Under The Hood** | **📋 Plan** | **[UNDER_THE_HOOD_VISUALIZATION.md](future/UNDER_THE_HOOD_VISUALIZATION.md)** |

---

## 🔴 Что делать дальше

### Критические задачи (блокируют production)
1. **Безопасность** (2-3 дня) — нет auth
2. **Observability** (3-4 дня) — нет мониторинга

### Важные фичи (конкурентное преимущество)
3. **Фаза 7: Under The Hood** (5 дней) — прозрачность как у Manus AI

### Долгосрочные планы
4. **Масштабирование** (8-12 недель) — task queues, clustering
5. **Tree-sitter** — мультиязычность

**Детали:** [future/IMPLEMENTATION_STATUS.md](future/IMPLEMENTATION_STATUS.md)

---

## 📖 Детальные планы

### Улучшение качества
**[future/QUALITY_IMPROVEMENT_PLAN.md](future/QUALITY_IMPROVEMENT_PLAN.md)**
- Безопасность
- Observability
- Рефакторинг
- Context Engine v2
- Learning System

### Масштабирование
**[future/SCALABILITY_AND_ARCHITECTURE_PLAN.md](future/SCALABILITY_AND_ARCHITECTURE_PLAN.md)**
- Task queues (Redis + Celery)
- PostgreSQL
- Load balancer
- Ollama cluster

### Фаза 7: Under The Hood
**[future/UNDER_THE_HOOD_VISUALIZATION.md](future/UNDER_THE_HOOD_VISUALIZATION.md)**
- Live Logs Panel
- Tool Calls Tracker
- Workflow Graph View
- 5 дней реализации

---

## 🗑️ Удалённые/перемещённые документы

### Удалены (временные файлы)
- `DOCS_CLEANUP_DONE.md` → временный summary файл
- `REORGANIZATION_SUMMARY.md` → временный summary файл

### Перемещены в `future/`
- `unreal.md` → `future/unreal.md` (идеи для вдохновения)
- `legacy_architecture_contract.md` → `future/legacy_architecture_contract.md` (паттерны из старых проектов)

### Ранее удалённые/объединённые
- `future/PROJECT_ANALYSIS_SUMMARY.md` → объединён в `EXECUTIVE_DASHBOARD.md`
- `future/CHANGELOG_2026_01_21.md` → не нужен как отдельный файл
- `future/VISUAL_PROJECT_MAP.md` → информация в других документах

---

## 💡 Соглашения

### Обновление документов
- Обновляйте дату в header при изменениях
- Один документ = одна тема
- Избегайте дубликатов информации
- Ссылайтесь на другие документы вместо копирования

### Приоритеты документов
1. **EXECUTIVE_DASHBOARD.md** — главный источник истины
2. **IMPLEMENTATION_STATUS.md** — актуальный статус
3. **Остальное** — детали по конкретным темам

---

## 🔗 Внешние ресурсы

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [DeepSeek Models](https://www.deepseek.com/)

---

## ❓ FAQ

**Q: Какой документ читать первым?**  
A: [EXECUTIVE_DASHBOARD.md](EXECUTIVE_DASHBOARD.md)

**Q: Где актуальный статус фич?**  
A: [future/IMPLEMENTATION_STATUS.md](future/IMPLEMENTATION_STATUS.md)

**Q: Что делать дальше?**  
A: Смотрите раздел "🔴 Что делать дальше" выше

**Q: Где детальные планы?**  
A: В папке `future/` — каждая тема в отдельном файле

---

**Поддержка:** Создайте issue в GitHub  
**Последнее обновление:** 2026-01-21  
**Автор:** AI Assistant + команда разработчиков
