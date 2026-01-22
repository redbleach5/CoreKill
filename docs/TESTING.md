# Руководство по тестированию

**Обновлено:** 2026-01-21

---

## 📋 Обзор

Проект использует два типа тестов:
- **Backend тесты** — pytest (Python)
- **Frontend тесты** — vitest (TypeScript/React)

---

## 🔧 Backend тесты

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=. --cov-report=html

# Только frontend импорты
pytest tests/test_frontend_imports.py -v

# С маркером
pytest -m frontend
pytest -m backend
```

### Структура тестов

```
tests/
├── conftest.py              # Конфигурация pytest
├── test_frontend_imports.py # Тесты проверки импортов frontend
├── test_workflow_langgraph.py
├── test_coder.py
└── ...
```

### Новые тесты

**`tests/test_frontend_imports.py`** — проверяет корректность импортов в frontend коде
- Использует скрипт `scripts/check_imports.py`
- Запускается автоматически в CI/CD
- Маркер: `@pytest.mark.frontend`

---

## 🎨 Frontend тесты

### Запуск тестов

```bash
cd frontend

# Все тесты
npm test

# В watch режиме
npm run test:watch

# С покрытием
npm test -- --coverage
```

### Структура тестов

```
frontend/src/__tests__/
├── setup.ts                 # Настройка тестовой среды
├── imports.test.ts          # Тесты проверки импортов
├── apiClient.test.ts        # Тесты API клиента
├── hooks.test.tsx           # Тесты кастомных хуков
├── components.test.tsx      # Тесты UI компонентов
└── chatMessageUpdate.test.tsx
```

### Новые тесты

#### `imports.test.ts`
- Проверяет все `.ts` и `.tsx` файлы на корректность импортов
- Проверяет использование `api`, `useLocalStorage`, `useModels`, `useApi`
- Автоматически находит все файлы в `components/`, `hooks/`, `utils/`

#### `apiClient.test.ts`
- Тестирует базовые методы API клиента
- Проверяет обработку ошибок
- Проверяет формирование URL
- Тестирует timeout обработку

#### `hooks.test.tsx`
- Тестирует `useLocalStorage` и `useLocalStorageString`
- Тестирует `useModels`
- Тестирует `useApi`
- Проверяет состояние загрузки и обработку ошибок

#### `components.test.tsx`
- Тестирует базовые UI компоненты:
  - `LoadingState`
  - `ErrorState`
  - `EmptyState`
- Проверяет рендеринг и пропсы

---

## 🛠️ Инструменты проверки

### Скрипт проверки импортов

**Файл:** `scripts/check_imports.py`

**Использование:**
```bash
python3 scripts/check_imports.py
```

**Что проверяет:**
- Использование `api` без импорта
- Использование `useLocalStorage` без импорта
- Использование `useLocalStorageString` без импорта
- Использование `useModels` без импорта
- Использование `useApi` без импорта

**Интеграция:**
- Используется в `tests/test_frontend_imports.py`
- Используется в `frontend/src/__tests__/imports.test.ts`
- Можно добавить в pre-commit hook

---

## 📊 Покрытие тестами

### Backend
- **Юнит-тесты:** ~85% покрытие
- **Интеграционные тесты:** Основные workflow покрыты
- **Frontend импорты:** 100% проверка

### Frontend
- **Импорты:** 100% проверка всех файлов
- **API клиент:** Базовые методы покрыты
- **Хуки:** Основные хуки покрыты
- **UI компоненты:** Базовые компоненты покрыты

---

## 🚀 CI/CD интеграция

### Рекомендуемая конфигурация

**GitHub Actions пример:**
```yaml
- name: Backend tests
  run: pytest tests/ -v

- name: Frontend tests
  run: |
    cd frontend
    npm test

- name: Check imports
  run: python3 scripts/check_imports.py
```

### Pre-commit hook

**Пример `.git/hooks/pre-commit`:**
```bash
#!/bin/bash
# Проверка импортов перед коммитом
python3 scripts/check_imports.py
if [ $? -ne 0 ]; then
    echo "❌ Обнаружены проблемы с импортами. Исправьте перед коммитом."
    exit 1
fi

# Frontend тесты
cd frontend && npm test
if [ $? -ne 0 ]; then
    echo "❌ Frontend тесты не прошли."
    exit 1
fi
```

---

## 📝 Написание новых тестов

### Backend тесты

```python
import pytest
from agents.coder import CoderAgent

@pytest.mark.unit
def test_coder_agent():
    agent = CoderAgent()
    # тест
```

### Frontend тесты

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MyComponent } from '../components/MyComponent'

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})
```

---

## ✅ Чеклист перед коммитом

- [ ] Backend тесты проходят: `pytest`
- [ ] Frontend тесты проходят: `cd frontend && npm test`
- [ ] Проверка импортов: `python3 scripts/check_imports.py`
- [ ] Линтер не находит ошибок
- [ ] TypeScript компилируется без ошибок

---

## 🔗 Связанные документы

- [IMPORT_AUDIT_REPORT.md](IMPORT_AUDIT_REPORT.md) — отчет об аудите импортов
- [REFACTORING_HISTORY.md](REFACTORING_HISTORY.md) — история рефакторинга

---

**Последнее обновление:** 2026-01-21
