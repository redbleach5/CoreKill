# Тестирование

**Обновлено:** 2026-01-21

---

## 📋 Обзор

Проект использует два типа тестов:
- **Backend тесты** — pytest (Python)
- **Frontend тесты** — vitest (TypeScript/React)

---

## 🔧 Backend тесты

### Запуск

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

### Структура

```
tests/
├── conftest.py              # Конфигурация pytest
├── factories.py             # Фабрики для тестовых данных
├── test_utils.py            # Утилиты для тестов
├── test_frontend_imports.py # Тесты проверки импортов frontend
├── test_undefined_check.py  # Тесты проверки неопределенных переменных
├── test_workflow_langgraph.py
├── test_coder.py
└── ...
```

### Новые тесты

**`tests/test_frontend_imports.py`** — проверяет корректность импортов в frontend коде
- Использует скрипт `scripts/check_imports.py`
- Маркер: `@pytest.mark.frontend`

**`tests/test_undefined_check.py`** — проверяет отсутствие неопределенных переменных
- Использует скрипт `scripts/check_undefined.py`
- Проверяет критические проблемы

---

## 🎨 Frontend тесты

### Запуск

```bash
cd frontend
npm test
# или
npm run test:watch
```

### Структура

```
frontend/src/__tests__/
├── setup.ts                 # Настройка тестов
├── imports.test.ts          # Проверка импортов
├── apiClient.test.ts        # Тесты API клиента
├── hooks.test.tsx           # Тесты хуков
├── components.test.tsx      # Тесты компонентов
└── utils/
    ├── mocks.ts             # Общие моки
    ├── testHelpers.tsx      # Хелперы для тестов
    └── constants.ts         # Константы для тестов
```

### Покрытие

- ✅ API клиент (`apiClient.test.ts`)
- ✅ Хуки (`hooks.test.tsx`)
- ✅ Компоненты (`components.test.tsx`)
- ✅ Проверка импортов (`imports.test.ts`)

---

## 📊 Масштабируемость тестов

### Фабрики и утилиты

**Backend:**
- `tests/factories.py` — фабрики для создания тестовых данных
- `tests/test_utils.py` — общие утилиты для тестов

**Frontend:**
- `frontend/src/__tests__/utils/mocks.ts` — общие моки
- `frontend/src/__tests__/utils/testHelpers.tsx` — хелперы
- `frontend/src/__tests__/utils/constants.ts` — константы

---

## ✅ Автоматические проверки

### Скрипты

1. **`scripts/check_imports.py`** — проверка импортов
2. **`scripts/check_undefined.py`** — проверка неопределенных переменных
3. **`scripts/test_thinking_streaming.py`** — тесты thinking стриминга
4. **`scripts/test_thinking_integration.py`** — интеграционные тесты thinking

**Запуск:**
```bash
python scripts/check_imports.py
python scripts/check_undefined.py
python scripts/test_thinking_streaming.py
python scripts/test_thinking_integration.py
```

---

## 📋 Чеклист перед коммитом

- [ ] Запустить `pytest` (backend тесты)
- [ ] Запустить `npm test` (frontend тесты)
- [ ] Запустить `python scripts/check_imports.py`
- [ ] Запустить `python scripts/check_undefined.py`
- [ ] Проверить линтер: `npm run lint` (frontend)

---

## 🔗 Связанные документы

- `docs/CODE_QUALITY.md` — гарантии качества кода
- `scripts/README.md` — описание скриптов
