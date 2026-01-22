# Phase 7: Under The Hood Visualization

## Статус: ✅ РЕАЛИЗОВАНО

## Цель

Прозрачность работы AI как у Manus AI — показывать пользователю **что именно делает система** в реальном времени.

## Принцип: "Show me what you're thinking"

Вместо скрытой работы — полная видимость:
- Какие LLM вызовы происходят
- Какие инструменты используются
- Сколько токенов и времени тратится
- Где находимся в workflow

---

## Текущее состояние

### ✅ Готово (90% backend)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| SSE Infrastructure | ✅ | Real-time события из backend |
| Streaming Agents | ✅ | 6 агентов со стримингом thinking |
| ThinkingBlock | ✅ | UI компонент для `<think>` блоков |
| MetricsDashboard | ✅ | Базовая визуализация метрик |
| Performance Metrics | ✅ | Сбор времени по этапам |

### ❌ Осталось (10% — UI панели)

| Компонент | Статус | Сложность |
|-----------|--------|-----------|
| Live Logs Panel | ❌ | 1 день |
| Tool Calls Tracker | ❌ | 1 день |
| Workflow Graph View | ❌ | 2 дня |
| Unified Debug Panel | ❌ | 1 день |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Under The Hood Panel                      │
├─────────────────────────────────────────────────────────────┤
│  [Logs] [Tools] [Graph] [Metrics]                    [Close] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Workflow Graph    │  │      Live Activity Feed     │   │
│  │                     │  │                             │   │
│  │  [Intent]──►[Plan]  │  │  22:58:43 🧠 LLM: intent   │   │
│  │      │              │  │  22:58:44 📋 Plan created  │   │
│  │      ▼              │  │  22:58:45 🧪 Tests gen...  │   │
│  │   [Tests]──►[Code]  │  │  22:58:50 💻 Code gen...   │   │
│  │      │              │  │  22:58:55 ✅ Validation    │   │
│  │      ▼              │  │                             │   │
│  │  [Validate]         │  │  ────────────────────────── │   │
│  │                     │  │  Tokens: 2,456 | Time: 32s  │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Компоненты

### 1. Live Logs Panel ⏱️ 1 день

Real-time логи всех операций с фильтрацией.

```tsx
// frontend/src/components/debug/LiveLogsPanel.tsx

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'debug'
  stage: string
  message: string
  details?: Record<string, unknown>
}

function LiveLogsPanel({ logs }: { logs: LogEntry[] }) {
  const [filter, setFilter] = useState<string>('all')
  
  return (
    <div className="h-full flex flex-col">
      {/* Фильтры */}
      <div className="flex gap-2 p-2 border-b border-gray-700">
        {['all', 'llm', 'tools', 'errors'].map(f => (
          <button 
            key={f}
            onClick={() => setFilter(f)}
            className={filter === f ? 'bg-purple-500/20' : ''}
          >
            {f}
          </button>
        ))}
      </div>
      
      {/* Логи */}
      <div className="flex-1 overflow-auto font-mono text-xs">
        {logs.filter(filterFn).map((log, i) => (
          <LogLine key={i} log={log} />
        ))}
      </div>
    </div>
  )
}
```

**Backend изменения:**
```python
# Новое SSE событие
SSE_EVENTS["LOG"] = "log"

# В workflow_nodes.py добавить emit
async def emit_log(stage: str, message: str, level: str = "info", details: dict = None):
    await sse_manager.emit({
        "type": "log",
        "stage": stage,
        "message": message,
        "level": level,
        "details": details,
        "timestamp": datetime.now().isoformat()
    })
```

---

### 2. Tool Calls Tracker ⏱️ 1 день

Визуализация каждого вызова LLM/инструмента.

```tsx
// frontend/src/components/debug/ToolCallsPanel.tsx

interface ToolCall {
  id: string
  type: 'llm' | 'validation' | 'search' | 'file'
  name: string
  input: string
  output?: string
  tokens_in?: number
  tokens_out?: number
  duration_ms: number
  status: 'running' | 'success' | 'error'
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  
  const icons = {
    llm: <Brain />,
    validation: <CheckCircle />,
    search: <Search />,
    file: <FileCode />
  }
  
  return (
    <div className="border border-gray-700 rounded-lg p-3 mb-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icons[call.type]}
          <span className="font-medium">{call.name}</span>
          {call.status === 'running' && <Loader2 className="animate-spin" />}
        </div>
        <div className="text-xs text-gray-400">
          {call.duration_ms}ms
          {call.tokens_in && ` | ${call.tokens_in}→${call.tokens_out} tok`}
        </div>
      </div>
      
      {expanded && (
        <div className="mt-2 text-xs">
          <div className="bg-gray-900 p-2 rounded">
            <div className="text-gray-500">Input:</div>
            <pre>{call.input.slice(0, 500)}</pre>
          </div>
          {call.output && (
            <div className="bg-gray-900 p-2 rounded mt-1">
              <div className="text-gray-500">Output:</div>
              <pre>{call.output.slice(0, 500)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

**Backend изменения:**
```python
# Новое SSE событие
SSE_EVENTS["TOOL_CALL_START"] = "tool_call_start"
SSE_EVENTS["TOOL_CALL_END"] = "tool_call_end"

# Декоратор для отслеживания
def track_tool_call(tool_type: str, name: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            call_id = str(uuid4())
            start = time.time()
            
            await emit_tool_call_start(call_id, tool_type, name, str(kwargs))
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                await emit_tool_call_end(call_id, "success", duration, str(result)[:1000])
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                await emit_tool_call_end(call_id, "error", duration, str(e))
                raise
        return wrapper
    return decorator
```

---

### 3. Workflow Graph View ⏱️ 2 дня

Интерактивный граф workflow с анимацией текущего этапа.

```tsx
// frontend/src/components/debug/WorkflowGraph.tsx

interface WorkflowNode {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'error'
  duration_ms?: number
}

const WORKFLOW_NODES: WorkflowNode[] = [
  { id: 'intent', label: 'Intent' },
  { id: 'planning', label: 'Planning' },
  { id: 'research', label: 'Research' },
  { id: 'testing', label: 'Tests' },
  { id: 'coding', label: 'Code' },
  { id: 'validation', label: 'Validate' },
  { id: 'critic', label: 'Review' },
]

function WorkflowGraph({ stages }: { stages: Record<string, StageStatus> }) {
  return (
    <svg viewBox="0 0 400 300" className="w-full h-full">
      {WORKFLOW_NODES.map((node, i) => {
        const status = stages[node.id]?.status || 'pending'
        const x = 50 + (i % 4) * 90
        const y = 50 + Math.floor(i / 4) * 100
        
        return (
          <g key={node.id}>
            {/* Связь к следующему */}
            {i < WORKFLOW_NODES.length - 1 && (
              <line 
                x1={x + 30} y1={y + 15} 
                x2={x + 60} y2={y + 15}
                stroke={status === 'completed' ? '#22c55e' : '#374151'}
                strokeWidth={2}
              />
            )}
            
            {/* Узел */}
            <rect 
              x={x} y={y} 
              width={60} height={30} 
              rx={6}
              fill={getNodeColor(status)}
              className={status === 'running' ? 'animate-pulse' : ''}
            />
            <text x={x + 30} y={y + 20} textAnchor="middle" fill="white" fontSize={10}>
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function getNodeColor(status: string): string {
  switch (status) {
    case 'running': return '#8b5cf6'  // purple
    case 'completed': return '#22c55e' // green
    case 'error': return '#ef4444'     // red
    default: return '#374151'          // gray
  }
}
```

---

### 4. Unified Debug Panel ⏱️ 1 день

Единая панель с табами, объединяющая все debug компоненты.

```tsx
// frontend/src/components/debug/UnderTheHoodPanel.tsx

type TabId = 'logs' | 'tools' | 'graph' | 'metrics'

function UnderTheHoodPanel({ isOpen, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>('logs')
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center">
      <div className="w-[90vw] h-[80vh] bg-gray-900 rounded-xl border border-gray-700 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold">Under The Hood</h2>
          </div>
          
          {/* Tabs */}
          <div className="flex gap-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={activeTab === tab.id ? 'bg-purple-500/20' : ''}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
          
          <button onClick={onClose}>
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'logs' && <LiveLogsPanel />}
          {activeTab === 'tools' && <ToolCallsPanel />}
          {activeTab === 'graph' && <WorkflowGraph />}
          {activeTab === 'metrics' && <MetricsDashboard />}
        </div>
      </div>
    </div>
  )
}
```

---

## SSE События (новые)

```typescript
// frontend/src/constants/sse.ts

export const SSE_EVENTS = {
  // Existing
  STAGE_START: 'stage_start',
  STAGE_PROGRESS: 'stage_progress',
  STAGE_END: 'stage_end',
  THINKING_STARTED: 'thinking_started',
  THINKING_IN_PROGRESS: 'thinking_in_progress',
  THINKING_COMPLETED: 'thinking_completed',
  
  // New for Phase 7
  LOG: 'log',
  TOOL_CALL_START: 'tool_call_start',
  TOOL_CALL_END: 'tool_call_end',
  METRICS_UPDATE: 'metrics_update',
}
```

---

## Plan

### День 1: Live Logs Panel
- [ ] Добавить SSE событие `log`
- [ ] Создать `LiveLogsPanel.tsx`
- [ ] Интегрировать в `useAgentStream`
- [ ] Добавить фильтрацию логов

### День 2: Tool Calls Tracker
- [ ] Добавить SSE события `tool_call_start/end`
- [ ] Создать `ToolCallsPanel.tsx`
- [ ] Добавить декоратор `@track_tool_call`
- [ ] Применить к LLM вызовам

### Дни 3-4: Workflow Graph View
- [ ] Создать `WorkflowGraph.tsx`
- [ ] Добавить анимации переходов
- [ ] Интегрировать с stages из `useAgentStream`
- [ ] Добавить tooltip с деталями

### День 5: Integration
- [ ] Создать `UnderTheHoodPanel.tsx`
- [ ] Добавить кнопку в header (иконка глаза)
- [ ] Тестирование и polish
- [ ] Обновить документацию

---

## Config

```toml
# config.toml

[debug]
# Включить Under The Hood панель
under_the_hood_enabled = true

# Уровень логирования для UI
log_level = "info"  # debug | info | warning | error

# Сохранять логи в файл
save_logs_to_file = false

# Максимум логов в памяти
max_logs_in_memory = 1000
```

---

## Checklist

- [x] Live Logs Panel — `LiveLogsPanel.tsx`
- [x] Tool Calls Tracker — `ToolCallsPanel.tsx`
- [x] Workflow Graph View — `WorkflowGraph.tsx`
- [x] Unified Debug Panel — `UnderTheHoodPanel.tsx`
- [x] Кнопка в header (иконка 👁️ Eye)
- [x] SSE события — `LOG`, `TOOL_CALL_START`, `TOOL_CALL_END`
- [x] Backend — `infrastructure/debug_events.py`
- [x] Конфигурация — `[debug]` в config.toml
- [x] Тесты — 17 тестов в `test_debug_events.py`
- [x] Интеграция в `useAgentStream` hook
