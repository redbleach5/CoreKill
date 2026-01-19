# IDE и функционал выполнения кода

## Обзор

Cursor Killer теперь включает встроенную IDE с поддержкой:

- **Редактирование кода** с подсветкой синтаксиса для Python
- **Выполнение кода** в изолированной среде с таймаутом
- **Множественные файлы** - работа с несколькими файлами одновременно
- **Три режима макета**:
  - **Chat** - только чат с системой
  - **IDE** - только редактор кода
  - **Split** - чат и IDE рядом

## Компоненты

### Frontend компоненты

#### 1. CodeEditor.tsx
Основной компонент редактора кода с поддержкой:

- Подсветка синтаксиса Python
- Нумерация строк
- Синхронизация скролла
- Кнопки: Выполнить, Копировать, Скачать, Сбросить
- Панель результатов выполнения

**Использование:**
```tsx
<CodeEditor
  initialCode="print('Hello')"
  language="python"
  onCodeChange={(code) => console.log(code)}
  onExecute={async (code) => {
    const result = await fetch('/api/code/execute', {
      method: 'POST',
      body: JSON.stringify({ code, language: 'python' })
    })
    return result.json()
  }}
  isExecuting={false}
/>
```

#### 2. IDEPanel.tsx
Полноценная IDE с поддержкой:

- Управление несколькими файлами
- Вкладки для быстрого переключения
- Добавление/удаление файлов
- Отслеживание изменений (индикатор ●)

**Использование:**
```tsx
<IDEPanel
  initialCode="print('Hello')"
  onCodeChange={(code) => setCode(code)}
  onExecute={executeCode}
  isExecuting={isExecuting}
/>
```

#### 3. AppWithIDE.tsx
Главное приложение с интеграцией IDE:

- Три режима макета (chat, ide, split)
- Интеграция с системой генерации кода
- Выполнение кода прямо в интерфейсе
- Сохранение состояния

### Backend endpoints

#### POST /api/code/execute
Выполняет Python код в изолированной среде.

**Запрос:**
```json
{
  "code": "print('Hello, World!')",
  "language": "python",
  "timeout": 10
}
```

**Ответ:**
```json
{
  "success": true,
  "output": "Hello, World!\n",
  "error": null,
  "execution_time": 0.123
}
```

**Ограничения безопасности:**
- Запрещены: `import os`, `import subprocess`, `__import__`, `eval()`, `exec()`, `open()`, `os.system`, `subprocess.run`
- Таймаут выполнения: 10 секунд (настраивается)
- Лимит памяти: 1MB на буфер вывода

#### POST /api/code/validate
Валидирует синтаксис кода без выполнения.

**Запрос:**
```json
{
  "code": "print('Hello')",
  "language": "python"
}
```

**Ответ (успех):**
```json
{
  "valid": true,
  "error": null
}
```

**Ответ (ошибка):**
```json
{
  "valid": false,
  "error": "unexpected EOF while parsing",
  "line": 1,
  "offset": 10
}
```

## Hooks

### useCodeExecution
Hook для выполнения кода:

```tsx
const { isExecuting, error, output, executeCode, clearOutput } = useCodeExecution()

// Выполнить код
const result = await executeCode('print("Hello")', 10)
console.log(result.output)
```

### useCodeValidation
Hook для валидации синтаксиса:

```tsx
const { isValidating, validateCode } = useCodeValidation()

const result = await validateCode('print("Hello")')
if (result.valid) {
  console.log('Синтаксис верный')
} else {
  console.log('Ошибка:', result.error)
}
```

## Примеры использования

### Пример 1: Простое выполнение кода
```tsx
import { CodeEditor } from './components/CodeEditor'
import { useCodeExecution } from './hooks/useCodeExecution'

function MyComponent() {
  const { executeCode, isExecuting } = useCodeExecution()

  return (
    <CodeEditor
      initialCode="print('Hello')"
      onExecute={executeCode}
      isExecuting={isExecuting}
    />
  )
}
```

### Пример 2: IDE с несколькими файлами
```tsx
import { IDEPanel } from './components/IDEPanel'
import { useCodeExecution } from './hooks/useCodeExecution'

function MyIDE() {
  const { executeCode, isExecuting } = useCodeExecution()

  return (
    <IDEPanel
      onExecute={executeCode}
      isExecuting={isExecuting}
    />
  )
}
```

### Пример 3: Полное приложение с чатом и IDE
```tsx
import AppWithIDE from './AppWithIDE'

export default AppWithIDE
```

## Безопасность

### Защита от опасного кода

Backend проверяет опасные паттерны:
- `import os` - доступ к файловой системе
- `import subprocess` - выполнение системных команд
- `__import__` - динамический импорт
- `eval()` - выполнение произвольного кода
- `exec()` - выполнение произвольного кода
- `open()` - доступ к файлам
- `os.system` - системные команды
- `subprocess.run` - системные команды

### Таймауты и лимиты

- **Таймаут выполнения**: 10 секунд (настраивается от 1 до 60)
- **Лимит памяти**: 1MB на буфер вывода
- **Изолированная среда**: Код выполняется в отдельном процессе

## Конфигурация

### Environment переменные

```bash
# Таймаут выполнения кода (секунды)
CODE_EXECUTION_TIMEOUT=10

# Максимальный размер вывода (байты)
CODE_EXECUTION_MAX_OUTPUT=1048576

# Включить/отключить выполнение кода
CODE_EXECUTION_ENABLED=true
```

### config.toml

```toml
[code_execution]
# Таймаут выполнения в секундах
timeout = 10

# Максимальный размер вывода
max_output = 1048576

# Включить выполнение кода
enabled = true
```

## Расширение функционала

### Добавление поддержки других языков

1. Создайте функцию выполнения для языка:
```python
async def execute_javascript_code(code: str, timeout: int = 10) -> Dict[str, Any]:
    # Реализация выполнения JavaScript
    pass
```

2. Добавьте поддержку в endpoint:
```python
if request.language == "javascript":
    result = await execute_javascript_code(request.code, request.timeout)
```

3. Обновите frontend компоненты для подсветки синтаксиса

### Добавление новых функций редактора

1. Добавьте кнопку в toolbar CodeEditor
2. Реализуйте функцию обработки
3. Обновите стили

Пример - добавление кнопки форматирования:
```tsx
<button
  onClick={() => {
    // Форматирование кода через black/prettier
    const formatted = await formatCode(code)
    setCode(formatted)
  }}
  className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded"
  title="Форматировать"
>
  <Wand2 className="w-4 h-4" />
</button>
```

## Известные ограничения

1. **Синтаксис Python**: Подсветка синтаксиса - базовая, не полная
2. **Производительность**: Большие файлы (>100KB) могут работать медленнее
3. **Языки**: Поддерживается только Python (JavaScript в планах)
4. **Отладка**: Нет встроенного дебаггера (используйте print для отладки)
5. **Импорты**: Ограничены для безопасности

## Планы развития

- [ ] Поддержка JavaScript/TypeScript
- [ ] Встроенный дебаггер
- [ ] Форматирование кода (Black, Prettier)
- [ ] Автодополнение (LSP)
- [ ] Сохранение файлов на диск
- [ ] Совместное редактирование
- [ ] Темы оформления
- [ ] Плагины для расширения функционала

## Troubleshooting

### Ошибка: "Код содержит опасную операцию"
Убедитесь, что вы не используете запрещённые операции. Для работы с файлами используйте временные файлы через tempfile.

### Ошибка: "Выполнение превышило таймаут"
Код работает слишком долго. Оптимизируйте алгоритм или увеличьте таймаут.

### Ошибка: "Неизвестная ошибка"
Проверьте консоль браузера и логи backend для деталей.

## Поддержка

Для вопросов и предложений создавайте issues на GitHub.
