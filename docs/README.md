# Документация проекта

**Обновлено:** 2026-01-25

---

## 🎯 Быстрый старт

### Для менеджмента
→ **[PROJECT_STATUS.md](PROJECT_STATUS.md)** — статус проекта, готовность к Production (75%)

### Для разработчиков
→ **[guides/TESTING.md](guides/TESTING.md)** — руководство по тестированию  
→ **[guides/CODE_QUALITY.md](guides/CODE_QUALITY.md)** — гарантии качества кода  
→ **[guides/SECURITY.md](guides/SECURITY.md)** — безопасность

### Для архитекторов
→ **[refactoring/REFACTORING_HISTORY.md](refactoring/REFACTORING_HISTORY.md)** — история рефакторинга  
→ **[../ARCHITECTURE.md](../ARCHITECTURE.md)** — архитектура системы

---

## 📂 Структура документации

```
docs/
├── README.md                    # 👈 ВЫ ЗДЕСЬ
├── PROJECT_STATUS.md            # Статус проекта (для менеджмента)
│
├── guides/                      # 📖 Руководства
│   ├── TESTING.md              # Тестирование (backend + frontend)
│   ├── CODE_QUALITY.md         # Гарантии качества кода
│   ├── SECURITY.md             # Безопасность (prompt injection, валидация)
│   ├── THINKING_STREAMING.md   # Thinking стриминг (реализация, UX)
│   └── AUTONOMOUS_IMPROVER_TROUBLESHOOTING.md  # Troubleshooting
│
├── refactoring/                 # 🔧 Рефакторинг
│   ├── REFACTORING_HISTORY.md   # Полная история рефакторинга
│   ├── PHASE2_COMPLETION_SUMMARY.md  # Завершение Phase 2
│   └── DEPENDENCIES_REFACTORING_SUMMARY.md  # Рефакторинг dependencies.py
│
├── history/                     # 📜 История
│   ├── CHANGELOG.md            # История изменений проекта
│   └── CODE_POLISH.md          # История полировки кода
│
├── tools/                       # 🛠️ Инструменты
│   ├── TOOLS_INDEX.md          # Единый индекс всех инструментов (40+)
│   └── TOOLS_CATALOG.md        # Каталог инструментов
│
├── research/                    # 🔬 Исследования
│   └── VLLM_SGLANG_ANALYSIS.md # Анализ необходимости vLLM/SGLang
│
├── setup/                       # ⚙️ Настройка
│   └── REMOTE_OLLAMA_SETUP.md  # Настройка удаленного Ollama
│
├── issues/                      # ⚠️ Проблемы
│   └── CRITICAL_ISSUES_AND_FIXES.md  # Критические проблемы и исправления
│
└── archive/                     # 📦 Архив старых документов
    ├── scripts/                # Тестовые документы
    └── [выполненные планы рефакторинга]
```

---

## 📚 Основные документы по категориям

### 📖 Руководства (guides/)
- **[TESTING.md](guides/TESTING.md)** — руководство по тестированию (backend + frontend)
- **[CODE_QUALITY.md](guides/CODE_QUALITY.md)** — гарантии качества кода, автоматические проверки
- **[SECURITY.md](guides/SECURITY.md)** — безопасность (prompt injection, валидация)
- **[THINKING_STREAMING.md](guides/THINKING_STREAMING.md)** — thinking стриминг (реализация, UX)
- **[AUTONOMOUS_IMPROVER_TROUBLESHOOTING.md](guides/AUTONOMOUS_IMPROVER_TROUBLESHOOTING.md)** — troubleshooting

### 🔧 Рефакторинг (refactoring/)
- **[REFACTORING_HISTORY.md](refactoring/REFACTORING_HISTORY.md)** — полная история рефакторинга проекта
- **[PHASE2_COMPLETION_SUMMARY.md](refactoring/PHASE2_COMPLETION_SUMMARY.md)** — завершение Phase 2 (разделение agent.py)
- **[DEPENDENCIES_REFACTORING_SUMMARY.md](refactoring/DEPENDENCIES_REFACTORING_SUMMARY.md)** — рефакторинг dependencies.py

### 📜 История (history/)
- **[CHANGELOG.md](history/CHANGELOG.md)** — история изменений проекта
- **[CODE_POLISH.md](history/CODE_POLISH.md)** — история полировки кода

### 🛠️ Инструменты (tools/)
- **[TOOLS_INDEX.md](tools/TOOLS_INDEX.md)** — единый индекс всех инструментов (40+)
- **[TOOLS_CATALOG.md](tools/TOOLS_CATALOG.md)** — каталог инструментов

### 🔬 Исследования (research/)
- **[VLLM_SGLANG_ANALYSIS.md](research/VLLM_SGLANG_ANALYSIS.md)** — анализ необходимости vLLM/SGLang

### ⚙️ Настройка (setup/)
- **[REMOTE_OLLAMA_SETUP.md](setup/REMOTE_OLLAMA_SETUP.md)** — настройка удаленного Ollama

### ⚠️ Проблемы (issues/)
- **[CRITICAL_ISSUES_AND_FIXES.md](issues/CRITICAL_ISSUES_AND_FIXES.md)** — критические проблемы и исправления

---

## 🔗 Связанные документы

- **[DOCS_INDEX.md](../DOCS_INDEX.md)** — главный индекс документации
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)** — для менеджмента и разработчиков
- **[future/IMPLEMENTATION_STATUS.md](../future/IMPLEMENTATION_STATUS.md)** — статус фич
- **[infrastructure/fast_advisor.md](../infrastructure/fast_advisor.md)** — Fast Advisor
- **[infrastructure/autonomous_improver/README.md](../infrastructure/autonomous_improver/README.md)** — Autonomous Improver

---

## 💡 Как использовать

1. **Начинайте с PROJECT_STATUS.md** — общий обзор проекта
2. **Используйте категории** — все документы организованы по темам
3. **Смотрите в archive/** — выполненные планы и старые документы
4. **Обновляйте даты** — при изменении документа обновляйте дату в header
