# Arize Phoenix — Локальный мониторинг LLM

## 📋 Обзор

[Arize Phoenix](https://phoenix.arize.com/) — open-source инструмент для мониторинга и отладки LLM приложений. Работает полностью локально.

**Статус:** 🔮 Планируется  
**Приоритет:** Средний (после стабилизации core workflow)  
**Сложность:** Низкая (pip install + несколько строк кода)

---

## 🎯 Зачем нужен

| Задача | Без Phoenix | С Phoenix |
|--------|-------------|-----------|
| Отладка промптов | Читать логи вручную | Визуальный интерфейс |
| Трейсинг LangGraph | Сложно | Автоматическая визуализация графа |
| Анализ latency | Ручной замер | Автоматические метрики |
| Поиск проблем | Grep по логам | Интерактивный поиск |

---

## 📦 Установка

```bash
pip install arize-phoenix openinference-instrumentation-langchain
```

---

## 🔧 Интеграция

### 1. Базовая инициализация

**Файл:** `infrastructure/monitoring.py`

```python
"""Мониторинг LLM вызовов через Arize Phoenix."""
from typing import Optional
import os

# Ленивый импорт для опциональной зависимости
_phoenix_session = None


def init_phoenix(enabled: bool = True) -> Optional[object]:
    """Инициализирует Phoenix для локального мониторинга.
    
    Args:
        enabled: Включить ли Phoenix (можно отключить для production)
        
    Returns:
        Phoenix session или None если отключен/недоступен
    """
    global _phoenix_session
    
    if not enabled:
        return None
    
    if _phoenix_session is not None:
        return _phoenix_session
    
    try:
        import phoenix as px
        from openinference.instrumentation.langchain import LangChainInstrumentor
        
        # Запускаем локальный сервер Phoenix
        _phoenix_session = px.launch_app()
        
        # Инструментируем LangChain/LangGraph
        LangChainInstrumentor().instrument()
        
        print(f"🔍 Phoenix UI: {_phoenix_session.url}")
        return _phoenix_session
        
    except ImportError:
        print("⚠️ Phoenix не установлен: pip install arize-phoenix")
        return None
    except Exception as e:
        print(f"⚠️ Ошибка запуска Phoenix: {e}")
        return None


def get_phoenix_url() -> Optional[str]:
    """Возвращает URL Phoenix UI если запущен."""
    if _phoenix_session:
        return _phoenix_session.url
    return None
```

### 2. Интеграция в Backend

**Файл:** `backend/api.py`

```python
from infrastructure.monitoring import init_phoenix
from utils.config import get_config

@app.on_event("startup")
async def startup_event():
    config = get_config()
    
    # Инициализируем Phoenix если включён в конфиге
    if config.enable_phoenix:
        phoenix_session = init_phoenix()
        if phoenix_session:
            logger.info(f"🔍 Phoenix UI: {phoenix_session.url}")
```

### 3. Добавление в config.toml

```toml
[monitoring]
# Включить Arize Phoenix для отладки промптов и workflow
enable_phoenix = true
```

### 4. Добавление в config.py

```python
@property
def enable_phoenix(self) -> bool:
    """Включён ли мониторинг Phoenix."""
    return self._config_data.get("monitoring", {}).get("enable_phoenix", False)
```

---

## 📊 Что можно отслеживать

### 1. LangGraph Workflow
- Визуализация графа агентов
- Время выполнения каждого узла
- Входы/выходы узлов

### 2. LLM Вызовы
- Промпты и ответы
- Latency каждого вызова
- Token usage
- Температура и другие параметры

### 3. Embeddings (RAG)
- Качество поиска
- Распределение embeddings
- Similarity scores

### 4. Ошибки
- Трейсы исключений
- Таймауты
- Некорректные ответы LLM

---

## 🖼️ Примеры использования

### Просмотр трейса workflow

```python
# Код работает как обычно, Phoenix автоматически собирает данные
result = await run_workflow_stream(task="создай функцию add")

# Открываем Phoenix UI в браузере
# http://localhost:6006 (по умолчанию)
```

### Анализ промпта

В Phoenix UI:
1. Перейти в раздел "Traces"
2. Найти интересующий вызов LLM
3. Посмотреть полный промпт и ответ
4. Проанализировать latency и tokens

### Сравнение версий промптов

1. Запустить workflow с версией промпта A
2. Запустить workflow с версией промпта B
3. В Phoenix сравнить качество ответов и метрики

---

## 🚀 Когда внедрять

### Предусловия
- [ ] Core workflow стабильно работает
- [ ] Greeting/help/create intent'ы обрабатываются корректно
- [ ] CriticAgent интегрирован
- [ ] Нет критических багов

### Триггеры для внедрения
- Нужна оптимизация промптов
- Непонятно почему LLM возвращает некорректные ответы
- Хочется визуализировать workflow
- Нужны метрики latency

---

## 📝 Порядок внедрения

1. **Установка** — `pip install arize-phoenix openinference-instrumentation-langchain`
2. **Создание** `infrastructure/monitoring.py`
3. **Интеграция** в `backend/api.py`
4. **Конфигурация** в `config.toml`
5. **Тестирование** — запустить workflow и проверить Phoenix UI

---

## 🔗 Ссылки

- [Phoenix Documentation](https://docs.arize.com/phoenix/)
- [GitHub](https://github.com/Arize-ai/phoenix)
- [LangChain Integration](https://docs.arize.com/phoenix/integrations/langchain)
- [Quickstart](https://docs.arize.com/phoenix/quickstart)

---

## ⚠️ Ограничения

- Phoenix потребляет RAM для хранения трейсов
- Не рекомендуется для production без ограничений
- Требует браузер для просмотра UI
- Может замедлить выполнение (незначительно)

---

## 📊 Альтернативы (не рекомендуются)

| Сервис | Причина отказа |
|--------|----------------|
| Langfuse | Облачный, требует регистрацию |
| Weights & Biases | Избыточно для отладки |
| Custom logging | Уже есть, но без визуализации |
