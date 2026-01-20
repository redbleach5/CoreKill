# Миграция агентов на нативный Ollama Chat API

## Статус: 📋 ПЛАНИРУЕТСЯ

## Контекст

В ходе исправления бага с отображением служебных тегов (`</assistant>`, `<user>`) в ответах
была выявлена архитектурная проблема: `ChatAgent` использовал кастомный XML-формат промптов,
который LLM интерпретировала как часть контента и продолжала генерировать.

## Проблема (исправлена для ChatAgent)

```
Было:
- ChatAgent использовал llm.generate() с кастомным форматом:
  <system>...</system>
  <user>...</user>
  <assistant>
  
- LLM видела этот паттерн и продолжала генерировать:
  Ответ...</assistant>
  <user>покажи пример...</user>
  
- Требовались хардкоды для очистки: _clean_response() с паттернами
```

## Решение (применено к ChatAgent)

```
Стало:
- ChatAgent использует llm.chat(messages=[...])
- Ollama автоматически применяет TEMPLATE из Modelfile модели
- Ollama автоматически применяет stop-токены из PARAMETER stop
- Никаких хардкодов и _clean_response()
```

## Как это работает

```
┌─────────────────────────────────────────────────────────────┐
│  Наш код: llm.chat(messages=[{"role": "user", ...}])        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Ollama автоматически применяет шаблон модели:              │
│                                                             │
│  Gemma 3:    <start_of_turn>user\n...<end_of_turn>          │
│  Qwen 2.5:   <|im_start|>user\n...<|im_end|>                │
│  Llama 3:    <|start_header_id|>user<|end_header_id|>\n...  │
│  DeepSeek:   <｜User｜>...<｜end▁of▁sentence｜>              │
└─────────────────────────────────────────────────────────────┘
```

## Текущее состояние агентов

| Агент | API | Формат | Статус |
|-------|-----|--------|--------|
| ChatAgent | `chat()` | messages | ✅ Мигрирован |
| CoderAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| PlannerAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| IntentAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| TestGeneratorAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| DebuggerAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| CriticAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| ReflectionAgent | `generate()` | instruction prompt | ⏳ Можно мигрировать |
| ConversationMemory | `generate()` | instruction prompt | ⏳ Можно мигрировать |

## Приоритет миграции

**Низкий** — текущие instruction-style промпты работают стабильно:
- Нет диалогового контекста
- Чёткий формат вывода (код, план, тесты)
- Нет проблемы "продолжения разговора"

## План миграции (опционально)

### Преимущества перехода на `chat()` для всех агентов:

1. **Единообразие** — все агенты используют один API
2. **System prompt** — чётко отделён от user message
3. **Future-proof** — новые модели могут требовать chat формат

### Пример миграции CoderAgent:

```python
# Было:
def generate_code(self, plan: str, tests: str, ...) -> str:
    prompt = self._build_code_generation_prompt(...)
    response = self.llm.generate(prompt, num_predict=...)
    return self._clean_code(response)

# Станет:
def generate_code(self, plan: str, tests: str, ...) -> str:
    messages = [
        {"role": "system", "content": self.SYSTEM_PROMPT},
        {"role": "user", "content": self._build_user_message(plan, tests, ...)}
    ]
    response = self.llm.chat(messages=messages)
    return self._clean_code(response)
```

### Оценка трудозатрат:

| Задача | Сложность |
|--------|-----------|
| Разделить промпты на system/user | Низкая |
| Заменить generate() на chat() | Низкая |
| Обновить тесты | Низкая |
| Всего на агент | ~30 мин |

## Файлы

```
agents/
├── chat.py           # ✅ Мигрирован на chat()
├── coder.py          # ⏳ Использует generate()
├── planner.py        # ⏳ Использует generate()
├── intent.py         # ⏳ Использует generate()
├── test_generator.py # ⏳ Использует generate()
├── debugger.py       # ⏳ Использует generate()
├── critic.py         # ⏳ Использует generate()
├── reflection.py     # ⏳ Использует generate()
└── conversation.py   # ⏳ Использует generate()
```

## Решение

Миграция остальных агентов — **опциональна**. Текущая реализация работает стабильно.
Можно выполнить при рефакторинге или при добавлении новых моделей, требующих chat формат.
