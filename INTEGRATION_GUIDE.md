# Руководство по интеграции IDE и функционала выполнения кода

## Быстрый старт

### 1. Обновление frontend приложения

Замените содержимое `frontend/src/main.tsx`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import AppWithIDE from './AppWithIDE'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppWithIDE />
  </React.StrictMode>,
)
```

### 2. Установка зависимостей

```bash
# Backend зависимости уже установлены

# Frontend зависимости
cd frontend
npm install
```

### 3. Запуск приложения

```bash
# Вариант 1: Автоматический запуск (рекомендуется)
python run.py

# Вариант 2: Ручной запуск
# Terminal 1 - Backend
uvicorn backend.api:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Откройте браузер: `http://localhost:5173`

## Архитектура

### Frontend структура

```
frontend/src/
├── App.tsx                    # Старое приложение (сохранено для совместимости)
├── AppWithIDE.tsx            # Новое приложение с IDE
├── components/
│   ├── CodeEditor.tsx        # Редактор кода
│   ├── IDEPanel.tsx          # IDE с управлением файлами
│   ├── EnhancedSettingsPanel.tsx  # Улучшенные настройки
│   ├── TaskHistory.tsx       # История задач
│   ├── EnhancedResultDisplay.tsx  # Улучшенное отображение результатов
│   ├── AgentProgress.tsx     # Отображение прогресса
│   └── SettingsPanel.tsx     # Старая панель настроек
├── hooks/
│   ├── useAgentStream.ts     # Hook для потока агентов
│   └── useCodeExecution.ts   # Hook для выполнения кода
└── lib/
    └── utils.ts              # Утилиты
```

### Backend структура

```
backend/
├── api.py                    # Главное приложение
├── routers/
│   ├── agent.py             # API для агентов
│   └── code_executor.py     # API для выполнения кода (новый)
├── types.py                 # Типы данных
├── validators.py            # Валидаторы
└── middleware/
    └── rate_limiter.py      # Rate limiting
```

## Компоненты и их взаимодействие

### Диаграмма взаимодействия

```
┌─────────────────────────────────────────────────────────┐
│                    AppWithIDE                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │   Chat View      │    │    IDE View      │          │
│  │                  │    │                  │          │
│  │ - Messages       │    │ - CodeEditor     │          │
│  │ - Input          │    │ - IDEPanel       │          │
│  │ - Progress       │    │ - Output         │          │
│  └────────┬─────────┘    └────────┬─────────┘          │
│           │                       │                    │
│           └───────────┬───────────┘                    │
│                       │                                │
│           ┌───────────▼──────────┐                    │
│           │   useAgentStream     │                    │
│           │   useCodeExecution   │                    │
│           └───────────┬──────────┘                    │
│                       │                                │
└───────────────────────┼────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          │                            │
    ┌─────▼──────┐           ┌────────▼──────┐
    │  Backend   │           │   Backend     │
    │  /api/task │           │ /api/code/*   │
    └────────────┘           └───────────────┘
```

## Использование компонентов

### CodeEditor

Простой редактор с подсветкой синтаксиса:

```tsx
import { CodeEditor } from './components/CodeEditor'

function MyComponent() {
  const [code, setCode] = useState('print("Hello")')

  return (
    <CodeEditor
      initialCode={code}
      language="python"
      readOnly={false}
      onCodeChange={setCode}
      onExecute={async (code) => {
        const response = await fetch('/api/code/execute', {
          method: 'POST',
          body: JSON.stringify({ code, language: 'python' })
        })
        return response.json()
      }}
      isExecuting={false}
    />
  )
}
```

### IDEPanel

Полная IDE с управлением файлами:

```tsx
import { IDEPanel } from './components/IDEPanel'

function MyIDE() {
  return (
    <IDEPanel
      initialCode="# Начальный код"
      onCodeChange={(code) => console.log(code)}
      onExecute={async (code) => {
        // Выполнить код
      }}
      isExecuting={false}
    />
  )
}
```

### EnhancedSettingsPanel

Панель настроек:

```tsx
import { EnhancedSettingsPanel } from './components/EnhancedSettingsPanel'

function Settings() {
  return (
    <EnhancedSettingsPanel
      onClose={() => setShowSettings(false)}
      availableModels={['model1', 'model2']}
      currentSettings={{
        model: 'model1',
        temperature: 0.25,
        maxIterations: 3,
        disableWebSearch: false
      }}
      onSettingsChange={(settings) => console.log(settings)}
    />
  )
}
```

### TaskHistory

История задач:

```tsx
import { TaskHistory } from './components/TaskHistory'

function History() {
  const tasks = [
    {
      id: '1',
      title: 'Создать функцию',
      description: 'Функция для сортировки',
      status: 'completed',
      timestamp: new Date(),
      duration: 5000,
      quality: 0.9,
      code: 'def sort_list(items):\n  return sorted(items)'
    }
  ]

  return (
    <TaskHistory
      tasks={tasks}
      onTaskSelect={(task) => console.log(task)}
      onTaskDelete={(taskId) => console.log(taskId)}
    />
  )
}
```

### EnhancedResultDisplay

Отображение результатов:

```tsx
import { EnhancedResultDisplay } from './components/EnhancedResultDisplay'

function Results() {
  return (
    <EnhancedResultDisplay
      code="def hello():\n  print('Hello')"
      tests="def test_hello():\n  assert hello() is None"
      metrics={{
        quality: 0.85,
        coverage: 0.90,
        complexity: 0.3,
        executionTime: 1.5
      }}
      stages={{
        intent: { success: true, duration: 100 },
        planner: { success: true, duration: 200 },
        coder: { success: true, duration: 500 }
      }}
    />
  )
}
```

## Hooks

### useCodeExecution

```tsx
import { useCodeExecution } from './hooks/useCodeExecution'

function MyComponent() {
  const { isExecuting, error, output, executeCode, clearOutput } = useCodeExecution()

  const handleRun = async () => {
    const result = await executeCode('print("Hello")', 10)
    console.log(result.output)
  }

  return (
    <div>
      <button onClick={handleRun} disabled={isExecuting}>
        {isExecuting ? 'Выполнение...' : 'Выполнить'}
      </button>
      {error && <p className="text-red-500">{error}</p>}
      {output && <pre>{output}</pre>}
    </div>
  )
}
```

### useCodeValidation

```tsx
import { useCodeValidation } from './hooks/useCodeExecution'

function MyComponent() {
  const { isValidating, validateCode } = useCodeValidation()

  const handleValidate = async () => {
    const result = await validateCode('print("Hello")')
    if (result.valid) {
      console.log('Код валиден')
    } else {
      console.log('Ошибка:', result.error)
    }
  }

  return (
    <button onClick={handleValidate} disabled={isValidating}>
      Проверить
    </button>
  )
}
```

## API endpoints

### POST /api/code/execute

Выполняет код:

```bash
curl -X POST http://localhost:8000/api/code/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello\")",
    "language": "python",
    "timeout": 10
  }'
```

Ответ:
```json
{
  "success": true,
  "output": "Hello\n",
  "error": null,
  "execution_time": 0.123
}
```

### POST /api/code/validate

Валидирует код:

```bash
curl -X POST http://localhost:8000/api/code/validate \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello\")",
    "language": "python"
  }'
```

Ответ:
```json
{
  "valid": true,
  "error": null
}
```

## Конфигурация

### Environment переменные

```bash
# Backend
CODE_EXECUTION_TIMEOUT=10
CODE_EXECUTION_MAX_OUTPUT=1048576
CODE_EXECUTION_ENABLED=true

# Frontend
VITE_API_URL=http://localhost:8000
```

### config.toml

```toml
[code_execution]
timeout = 10
max_output = 1048576
enabled = true
```

## Развёртывание

### Development

```bash
python run.py
```

### Production

```bash
# Установить зависимости
pip install -r requirements.txt
cd frontend && npm install && npm run build

# Запустить backend
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --workers 4

# Запустить frontend (nginx или другой веб-сервер)
```

## Тестирование

### Unit тесты

```bash
# Backend
pytest tests/

# Frontend
npm test
```

### E2E тесты

```bash
npm run test:e2e
```

### Ручное тестирование

1. Откройте http://localhost:5173
2. Переключайтесь между режимами (Chat, IDE, Split)
3. Напишите код в IDE
4. Нажмите "Выполнить"
5. Проверьте результаты

## Troubleshooting

### Ошибка: "Cannot find module"
```bash
# Переустановите зависимости
cd frontend && npm install
```

### Ошибка: "Port 8000 already in use"
```bash
# Найдите процесс на порту 8000
lsof -i :8000

# Убейте процесс
kill -9 <PID>
```

### Ошибка: "CORS error"
Убедитесь, что backend запущен на http://localhost:8000 и frontend на http://localhost:5173

### Ошибка: "Code execution failed"
Проверьте логи backend:
```bash
tail -f logs/app.log
```

## Расширение функционала

### Добавление нового компонента

1. Создайте файл `frontend/src/components/MyComponent.tsx`
2. Экспортируйте компонент
3. Импортируйте в `AppWithIDE.tsx`
4. Добавьте в нужное место в UI

### Добавление нового API endpoint

1. Создайте функцию в `backend/routers/code_executor.py`
2. Добавьте декоратор `@router.post()`
3. Добавьте в `backend/api.py`
4. Создайте hook в frontend для вызова

### Добавление поддержки другого языка

1. Создайте функцию `execute_<language>_code()` в `backend/routers/code_executor.py`
2. Добавьте в условие в `execute_code()` endpoint
3. Обновите frontend компоненты для подсветки синтаксиса
4. Добавьте в конфигурацию

## Производительность

### Оптимизации

- Ленивая загрузка компонентов
- Мемоизация дорогих вычислений
- Виртуализация длинных списков
- Оптимизация re-renders

### Мониторинг

```bash
# Lighthouse аудит
npm run audit

# Performance профилирование
npm run profile
```

## Безопасность

### Защита от опасного кода

Backend проверяет опасные паттерны перед выполнением:
- `import os`
- `import subprocess`
- `__import__`
- `eval()`
- `exec()`
- `open()`
- `os.system`
- `subprocess.run`

### Rate limiting

Все endpoints защищены rate limiting (100 запросов в минуту по умолчанию).

### HTTPS

В production используйте HTTPS с SSL сертификатом.

## Поддержка

Для вопросов и проблем создавайте issues на GitHub.

## Лицензия

MIT
