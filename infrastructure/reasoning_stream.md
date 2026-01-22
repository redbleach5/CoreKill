# Reasoning Stream Module

## Назначение

Модуль `reasoning_stream.py` обеспечивает **real-time стриминг** рассуждений reasoning моделей (DeepSeek-R1, QwQ) в UI.

## Зачем это нужно

Reasoning модели возвращают рассуждения в `<think>` блоках. Вместо того чтобы скрывать их:

1. **Показываем пользователю в реальном времени** — он видит ход мысли модели по мере генерации
2. **Позволяем прервать** — если модель идёт не туда, можно остановить
3. **Повышаем доверие** — прозрачность рассуждений
4. **Фундамент для стриминга кода** — та же архитектура используется для real-time отображения генерации кода

## SSE События

| Событие | Когда отправляется | Данные |
|---------|-------------------|--------|
| `thinking_started` | Начало `<think>` блока | stage, total_chars |
| `thinking_in_progress` | Каждый чанк | content, elapsed_ms |
| `thinking_completed` | `</think>` получен | content, summary |
| `thinking_interrupted` | Прервано пользователем | content |

## Использование

### Real-time стриминг (рекомендуется)

```python
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.local_llm import create_llm_for_stage

llm = create_llm_for_stage("coding", model="deepseek-r1:7b")
manager = get_reasoning_stream_manager()

# Real-time стриминг с разделением thinking и content
async for event_type, data in manager.stream_from_llm(llm, prompt, "coding"):
    if event_type == "thinking":
        yield data  # SSE событие для thinking блока
    elif event_type == "content":
        yield create_code_chunk_event(data)  # Чанк кода
    elif event_type == "done":
        final_code = extract_code_from_reasoning(data)
```

### Post-hoc обработка (для совместимости)

```python
from infrastructure.reasoning_stream import get_reasoning_stream_manager

manager = get_reasoning_stream_manager()

# После получения готового ответа от LLM
async for event in manager.process_response_with_thinking(
    response=llm_response,
    stage="coding"
):
    yield event  # Отправляем в SSE stream
```

### В workflow node

```python
from infrastructure.reasoning_stream import get_reasoning_stream_manager

@workflow_node(stage="coding")
async def coder_node(state: AgentState) -> AgentState:
    manager = get_reasoning_stream_manager()
    
    response = await asyncio.to_thread(llm.generate, prompt)
    
    # Стримим thinking если есть
    async for event in manager.process_response_with_thinking(
        response=response,
        stage="coding"
    ):
        # Отправка через SSE (если enable_sse=True)
        if state.get("enable_sse"):
            yield event
    
    # Парсим ответ для state
    parsed = parse_reasoning_response(response)
    state["code"] = parsed.answer
    
    return state
```

### Прерывание

```python
# В обработчике "Стоп" кнопки
manager = get_reasoning_stream_manager()
manager.interrupt()
```

## Конфигурация

### config.toml

```toml
[reasoning]
show_thinking = true        # Показывать <think> блоки в UI

[streaming]
enabled = true              # Включить real-time стриминг
thinking_chunk_size = 100   # Размер чанка thinking (символов)
thinking_debounce_ms = 50   # Задержка между чанками
max_thinking_time_ms = 120000  # Макс. время рассуждения
use_streaming_agents = true # Использовать StreamingCoderAgent
```

### Программно

```python
from infrastructure.reasoning_stream import (
    ReasoningStreamManager,
    ReasoningStreamConfig
)

config = ReasoningStreamConfig(
    enabled=True,
    chunk_size=200,
    debounce_ms=100
)

manager = ReasoningStreamManager(config)
```

## Frontend интеграция

### Обработка событий

```typescript
eventSource.addEventListener('thinking_started', (e) => {
  const data = JSON.parse(e.data);
  showThinkingIndicator(data.stage, data.total_chars);
});

eventSource.addEventListener('thinking_in_progress', (e) => {
  const data = JSON.parse(e.data);
  appendThinkingContent(data.content);
  updateProgress(data.elapsed_ms);
});

eventSource.addEventListener('thinking_completed', (e) => {
  const data = JSON.parse(e.data);
  showThinkingSummary(data.summary);
  hideThinkingIndicator();
});

eventSource.addEventListener('thinking_interrupted', (e) => {
  showInterruptedMessage();
});
```

### UI компонент (пример)

```tsx
function ThinkingBlock({ stage, content, status, summary }) {
  const [expanded, setExpanded] = useState(false);
  
  if (status === 'completed') {
    return (
      <div className="thinking-block">
        <button onClick={() => setExpanded(!expanded)}>
          💭 {expanded ? 'Скрыть' : 'Показать'} рассуждения
        </button>
        {!expanded && <p className="summary">{summary}</p>}
        {expanded && <pre className="thinking-content">{content}</pre>}
      </div>
    );
  }
  
  return (
    <div className="thinking-block in-progress">
      <span className="spinner" />
      <span>Рассуждаю...</span>
      <pre className="thinking-content">{content}</pre>
    </div>
  );
}
```

## Архитектура

### Real-time стриминг (новый)

```
┌─────────────────────┐
│   LocalLLM          │
│   generate_stream() │ ◄── Ollama streaming API
└────────┬────────────┘
         │ StreamChunk (is_thinking, content)
         ▼
┌─────────────────────────┐
│ ReasoningStreamManager  │
│ stream_from_llm()       │
└────────┬────────────────┘
         │ ("thinking", event) / ("content", chunk) / ("done", full)
         ▼
┌─────────────────┐
│   agent.py      │ ◄── Формирует SSE события
│   SSEManager    │
└────────┬────────┘
         │ SSE events
         ▼
┌─────────────────┐
│   Frontend      │
│   EventSource   │
└─────────────────┘
```

### Post-hoc обработка (legacy)

```
┌─────────────────┐
│   LocalLLM      │
│   generate()    │
└────────┬────────┘
         │ полный response с <think>
         ▼
┌─────────────────────────┐
│ ReasoningStreamManager  │
│ process_response_with_  │
│ thinking()              │
└────────┬────────────────┘
         │ SSE events (эмуляция стриминга)
         ▼
┌─────────────────┐
│   Frontend      │
└─────────────────┘
```

## Связанные файлы

- `infrastructure/reasoning_utils.py` — парсинг `<think>` блоков
- `backend/sse_manager.py` — базовые SSE события
- `infrastructure/local_llm.py` — генерация ответов
- `.cursor/rules/models.md` — документация по моделям

## Статус реализации

- [x] Backend модуль `reasoning_stream.py`
- [x] SSE события: `thinking_started`, `thinking_in_progress`, `thinking_completed`, `thinking_interrupted`
- [x] Frontend константы в `constants/sse.ts`
- [x] Hook обработка в `useAgentStream.ts`
- [x] UI компонент `ThinkingBlock.tsx` (сворачиваемый, как в ChatGPT)
- [x] Интеграция в `ProgressSteps.tsx` (внутри каждого этапа)
- [x] Real-time стриминг через `LocalLLM.generate_stream()`
- [x] `stream_from_llm()` — real-time разделение thinking/content
- [x] Стриминговые агенты: `StreamingPlannerAgent`, `StreamingCoderAgent` и др.
- [x] Стриминговые узлы в `workflow_nodes.py`: `stream_planner_node()`, `stream_coder_node()` и др.
- [x] Интеграция в `agent.py`: `run_workflow_stream_with_thinking()`
- [x] Автопереключение через `_is_streaming_enabled()` из config.toml
- [ ] Добавить стриминг кода в IDE panel

## Как включить стриминг

### config.toml

```toml
[streaming]
use_streaming_agents = true   # Включает thinking стриминг
```

### Что происходит

1. `_is_streaming_enabled()` проверяет флаг
2. Если `true` → `run_workflow_stream_with_thinking()` 
3. Если `false` → `run_workflow_stream()` (старое поведение)

### Архитектура (реализовано)

```
backend/routers/agent.py
    │
    ├── _is_streaming_enabled() проверяет config.toml
    │
    ├── run_workflow_stream_with_thinking()
    │   ├── stream_planner_node() → thinking SSE
    │   ├── stream_generator_node() → thinking SSE
    │   ├── stream_coder_node() → thinking + code_chunk SSE
    │   ├── stream_debugger_node() → thinking SSE
    │   ├── stream_fixer_node() → thinking + code_chunk SSE
    │   ├── stream_reflection_node() → thinking SSE
    │   └── stream_critic_node() → thinking SSE
    │
    └── run_workflow_stream() (legacy, LangGraph)
```

## TODO

- [ ] Обновить `backend/routers/agent.py` для использования stream_*_node()
- [ ] Добавить кнопку "Стоп" для прерывания рассуждений
- [ ] Сохранять thinking в историю разговора
- [ ] Добавить метрики времени рассуждения в performance_metrics
- [ ] Стриминг создания файлов и структуры проекта

## План удаления старого кода

См. `DEPRECATION.md` в корне проекта.
