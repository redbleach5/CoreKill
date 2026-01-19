# Интеграция асинхронного Ollama Connection Pool

## Статус: Запланировано

## Текущее состояние

`infrastructure/connection_pool.py` содержит готовую реализацию async пула соединений,
но она **не интегрирована** в workflow. Система использует синхронный `LocalLLM`.

## Проблема текущего решения

```
Синхронный LocalLLM:
- Блокирует поток на 30-120 секунд при каждом LLM запросе
- При одновременных запросах все пользователи ждут в очереди
- FastAPI workers простаивают, ожидая ответ от Ollama
- Плохо масштабируется
```

## Преимущества async решения

```
Асинхронный OllamaConnectionPool:
- Не блокирует event loop
- Несколько пользователей работают параллельно
- HTTP/2 multiplexing для эффективности
- Semaphore для контроля нагрузки
- Connection pooling уменьшает latency
```

## План интеграции

### Этап 1: AsyncLocalLLM

Создать `infrastructure/async_local_llm.py`:

```python
from infrastructure.connection_pool import get_ollama_pool

class AsyncLocalLLM:
    async def generate(self, prompt: str, **options) -> str:
        pool = await get_ollama_pool()
        return await pool.generate(
            model=self.model,
            prompt=prompt,
            options=options
        )
```

### Этап 2: Async агенты

Переписать агенты с async методами:

```python
class CoderAgent:
    async def generate_code(self, plan: str, tests: str, ...) -> str:
        response = await self.llm.generate(prompt)
        return self._clean_code(response)
```

### Этап 3: Async workflow nodes

Обновить `infrastructure/workflow_nodes.py`:

```python
async def coder_node(state: AgentState) -> AgentState:
    code = await _coder_agent.generate_code(...)
    state["code"] = code
    return state
```

### Этап 4: LangGraph async execution

LangGraph поддерживает async:

```python
graph = workflow.compile()
async for event in graph.astream(initial_state):
    # Уже используется в routers/agent.py
    ...
```

### Этап 5: Lifespan management

Обновить `backend/api.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - пул инициализируется lazy
    yield
    # Shutdown
    await close_ollama_pool()
```

## Оценка трудозатрат

| Компонент | Сложность | Описание |
|-----------|-----------|----------|
| AsyncLocalLLM | Низкая | Обёртка над пулом |
| Async агенты | Средняя | 9 агентов переписать |
| Async nodes | Средняя | 10 узлов переписать |
| Тесты | Средняя | pytest-asyncio |

## Риски

1. **Совместимость**: Некоторые зависимости могут не поддерживать async
2. **Отладка**: Async код сложнее отлаживать
3. **Тестирование**: Нужен pytest-asyncio

## Когда делать

- Когда появится необходимость в многопользовательском режиме
- Когда текущее решение станет узким местом (bottleneck)
- После стабилизации основного функционала

## Файлы для изменения

```
infrastructure/
├── connection_pool.py    # ✅ Готов
├── async_local_llm.py    # Создать
├── local_llm.py          # Deprecate или оставить для CLI
├── workflow_nodes.py     # Переписать на async
├── workflow_graph.py     # Без изменений (LangGraph уже async)

agents/
├── intent.py             # Добавить async execute()
├── planner.py            # Добавить async execute()
├── researcher.py         # Добавить async execute()
├── test_generator.py     # Добавить async execute()
├── coder.py              # Добавить async execute()
├── debugger.py           # Добавить async execute()
├── reflection.py         # Добавить async execute()
├── critic.py             # Добавить async execute()
└── memory.py             # Без изменений (ChromaDB sync)

backend/
├── api.py                # Обновить lifespan
└── routers/agent.py      # Уже async
```
