# Streaming ответов LLM

## 📋 Обзор

Streaming позволяет отображать текст ответа по мере его генерации, как в ChatGPT или Cursor.

**Статус:** 🔮 Планируется  
**Приоритет:** Высокий (значительное улучшение UX)  
**Сложность:** Средняя

---

## 🎯 Зачем нужен

| Без streaming | С streaming |
|---------------|-------------|
| Пользователь ждёт 10-30 сек | Текст появляется сразу |
| Непонятно работает ли система | Видно что идёт генерация |
| Нельзя прервать плохой ответ | Можно остановить на полпути |

---

## 📊 Текущее состояние

```
Backend:
- SSE события отправляются ✅
- ollama.generate(stream=False) — ждёт полный ответ ❌
- LangGraph astream() — стримит по этапам, не по токенам ❌

Frontend:
- Получает SSE события ✅
- Обновляет UI при stage_update ✅
- Посимвольное отображение ❌
```

---

## 🔧 План реализации

### Этап 1: Streaming для Chat режима

**Файл:** `agents/chat.py`

```python
async def chat_stream(
    self,
    message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> AsyncGenerator[str, None]:
    """Стриминг ответа по токенам."""
    prompt = self._build_prompt(message, conversation_history)
    
    async for chunk in self.llm.generate_stream(prompt):
        yield chunk
```

**Файл:** `infrastructure/local_llm.py`

```python
async def generate_stream(
    self,
    prompt: str,
    **kwargs
) -> AsyncGenerator[str, None]:
    """Стриминг генерации через Ollama."""
    from infrastructure.connection_pool import get_ollama_pool
    
    pool = await get_ollama_pool()
    payload = {
        "model": self.model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": self.temperature}
    }
    
    async for chunk in pool.stream("POST", "/api/generate", json=payload):
        data = json.loads(chunk)
        if "response" in data:
            yield data["response"]
```

### Этап 2: SSE события для токенов

**Файл:** `backend/sse_manager.py`

```python
@staticmethod
async def stream_token(token: str) -> str:
    """SSE событие для одного токена."""
    return SSEManager._create_event("token", {"text": token})
```

**Файл:** `backend/routers/agent.py`

```python
async def run_chat_stream_tokens(...):
    """Chat с токен-стримингом."""
    chat_agent = get_chat_agent(model)
    
    async for token in chat_agent.chat_stream(message, history):
        yield await SSEManager.stream_token(token)
        await asyncio.sleep(0.01)  # Throttle
```

### Этап 3: Frontend — посимвольное отображение

**Файл:** `frontend/src/hooks/useAgentStream.ts`

```typescript
// Обработка токенов
case 'token':
  setPartialResponse(prev => prev + data.text)
  break
```

**Файл:** `frontend/src/components/chat/MessageList.tsx`

```tsx
function StreamingMessage({ content }: { content: string }) {
  return (
    <div className="text-gray-200">
      {content}
      <span className="animate-pulse">▊</span>
    </div>
  )
}
```

### Этап 4: Streaming для Code workflow

Более сложная задача — код генерируется в середине workflow.

Варианты:
1. **Стримить только coding этап** — показывать код по мере генерации
2. **Итоговый результат** — стримить финальный ответ critic агента

```python
# В coder_node:
async for token in coder_agent.generate_code_stream(...):
    await sse_manager.send_token(task_id, token)
    full_code += token

state["code"] = full_code
```

---

## ⚠️ Сложности

1. **Connection pool** — нужно адаптировать для streaming
2. **Throttling** — нельзя отправлять слишком много SSE событий
3. **Буферизация** — нужно группировать токены (1-3 за раз)
4. **Отмена** — нужен механизм прерывания генерации

---

## 📁 Файлы для изменения

```
infrastructure/
├── local_llm.py          # Добавить generate_stream()
├── connection_pool.py    # Адаптировать stream() метод

agents/
├── chat.py               # Добавить chat_stream()
├── coder.py              # Добавить generate_code_stream() (опционально)

backend/
├── sse_manager.py        # Добавить stream_token()
├── routers/agent.py      # Использовать streaming

frontend/
├── hooks/useAgentStream.ts    # Обработка token событий
├── components/chat/MessageList.tsx  # Streaming рендеринг
```

---

## 📅 Оценка

| Этап | Сложность | Влияние |
|------|-----------|---------|
| Chat streaming | Низкая | Высокое |
| SSE токены | Низкая | Среднее |
| Frontend | Средняя | Высокое |
| Code workflow | Высокая | Среднее |

**Рекомендация:** Начать с Chat streaming — минимум изменений, максимум эффекта.
