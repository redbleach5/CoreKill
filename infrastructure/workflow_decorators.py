"""Декораторы для workflow nodes.

Убирают дублирование обработки ошибок, метрик и checkpoints.
"""
import asyncio
import functools
import time
from functools import wraps
from typing import Callable, Any, TypeVar, Awaitable, AsyncGenerator

from infrastructure.workflow_state import AgentState
from infrastructure.local_llm import LLMTimeoutError, LLMModelUnavailableError
from infrastructure.node_validator import NodeInputValidator
from infrastructure.circuit_breaker import CircuitBreakerOpenError
from utils.logger import get_logger

logger = get_logger()

# Type alias для node функции
NodeFunc = Callable[[AgentState], Awaitable[AgentState]]
StreamingNodeFunc = Callable[[AgentState], AsyncGenerator[tuple[str, Any], None]]
T = TypeVar('T')


def workflow_node(
    stage: str,
    fallback_key: str | None = None,
    fallback_value: Any = None
) -> Callable[[NodeFunc], NodeFunc]:
    """Декоратор для workflow nodes с единой обработкой ошибок.
    
    Автоматически:
    - Записывает метрики времени выполнения
    - Сохраняет checkpoint после выполнения
    - Обрабатывает LLMTimeoutError с отправкой SSE
    - Обрабатывает общие Exception с fallback значением
    
    Args:
        stage: Название этапа (intent, planning, coding, etc.)
        fallback_key: Ключ в state для записи fallback значения при ошибке
        fallback_value: Значение по умолчанию при ошибке (или callable для создания)
    
    Usage:
        @workflow_node(stage="intent", fallback_key="intent_result", fallback_value=default_intent)
        async def intent_node(state: AgentState) -> AgentState:
            # только бизнес-логика, без try-except
            ...
    """
    def decorator(func: NodeFunc) -> NodeFunc:
        @wraps(func)
        async def wrapper(state: AgentState) -> AgentState:
            start_time = time.time()
            
            # Получаем доступ к ресурсу агента (контроль одновременных вызовов)
            task_id = state.get("task_id")
            # Валидируем входные данные перед выполнением
            valid, error_msg = NodeInputValidator.validate(stage, state)
            if not valid:
                logger.error(f"❌ Валидация входных данных не пройдена для узла '{stage}': {error_msg}")
                # Устанавливаем fallback значение если указано
                if fallback_key is not None:
                    value = fallback_value() if callable(fallback_value) else fallback_value
                    state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                _record_stage_duration(stage, time.time() - start_time)
                _save_checkpoint(state, stage)
                return state
            
            resource_context = await _acquire_agent_resource(stage, task_id)
            
            async with resource_context:
                # Используем circuit breaker для защиты от каскадных сбоев
                from infrastructure.circuit_breaker import get_circuit_breaker
                circuit_breaker = await get_circuit_breaker(f"agent_{stage}")
                
                try:
                    # Выполняем основную логику узла через circuit breaker
                    result = await circuit_breaker.call(func, state)
                    
                    # Записываем метрику времени
                    _record_stage_duration(stage, time.time() - start_time)
                    
                    # Сохраняем checkpoint
                    _save_checkpoint(result, stage)
                    
                    return result
                    
                except CircuitBreakerOpenError as e:
                    logger.warning(f"🔌 Circuit breaker открыт на этапе {stage}: {e}")
                    await _send_stage_error(
                        state, stage, "circuit_breaker_open",
                        f"Circuit breaker открыт: {str(e)}"
                    )
                    
                    # Устанавливаем fallback значение если указано
                    if fallback_key is not None:
                        value = fallback_value() if callable(fallback_value) else fallback_value
                        state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                    
                    _record_stage_duration(stage, time.time() - start_time)
                    _save_checkpoint(state, stage)
                    return state
                    
                except LLMTimeoutError as e:
                    logger.warning(f"⏱️ Таймаут на этапе {stage}: {e}")
                    await _send_stage_error(
                        state, stage, "timeout",
                        f"Превышено время ожидания на этапе {stage}"
                    )
                    
                    # Устанавливаем fallback значение если указано
                    if fallback_key is not None:
                        value = fallback_value() if callable(fallback_value) else fallback_value
                        state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                    
                    _record_stage_duration(stage, time.time() - start_time)
                    _save_checkpoint(state, stage)
                    return state
                    
                except LLMModelUnavailableError as e:
                    logger.error(
                        f"❌ Модель {e.model} недоступна на этапе {stage}: {e}. "
                        f"Рекомендуется переключиться на другую модель."
                    )
                    await _send_stage_error(
                        state, stage, "model_unavailable",
                        f"Модель {e.model} недоступна. Рекомендуется переключиться на другую модель."
                    )
                    
                    # Устанавливаем fallback значение если указано
                    if fallback_key is not None:
                        value = fallback_value() if callable(fallback_value) else fallback_value
                        state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                    
                    _record_stage_duration(stage, time.time() - start_time)
                    _save_checkpoint(state, stage)
                    return state
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка на этапе {stage}: {e}", error=e)
                    await _send_stage_error(
                        state, stage, "error",
                        f"Ошибка: {str(e)[:100]}"
                    )
                    
                    # Устанавливаем fallback значение если указано
                    if fallback_key is not None:
                        value = fallback_value() if callable(fallback_value) else fallback_value
                        state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                    
                    _record_stage_duration(stage, time.time() - start_time)
                    _save_checkpoint(state, stage)
                    return state
        
        return wrapper
    return decorator


def _record_stage_duration(stage: str, duration: float) -> None:
    """Записывает время выполнения этапа в метрики."""
    try:
        from infrastructure.performance_metrics import get_performance_metrics
        metrics = get_performance_metrics()
        metrics.record_stage_duration(stage, duration)
    except Exception as e:
        logger.debug(f"⚠️ Не удалось записать метрику: {e}")


def _save_checkpoint(state: AgentState, stage: str, status: str = "running") -> None:
    """Сохраняет checkpoint после выполнения узла."""
    from utils.config import get_config
    config = get_config()
    
    if not config.persistence_enabled:
        return
    
    task_id = state.get("task_id")
    if not task_id:
        return
    
    try:
        from infrastructure.task_checkpointer import get_task_checkpointer
        checkpointer = get_task_checkpointer()
        checkpointer.save_checkpoint(task_id, state, stage, status)
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сохранить checkpoint: {e}")


async def _acquire_agent_resource(
    stage: str,
    task_id: str | None = None
):
    """Получает доступ к ресурсу агента для этапа.
    
    Args:
        stage: Название этапа (intent, planning, coding, etc.)
        task_id: ID задачи для отслеживания
        
    Returns:
        AgentResourceContext для использования в async with
    """
    try:
        from infrastructure.agent_resource_manager import acquire_agent_resource
        return await acquire_agent_resource(stage, task_id)
    except Exception as e:
        # Если resource manager недоступен, возвращаем пустой контекст
        # Проверяем, не является ли это ошибкой мока в тестах
        error_msg = str(e)
        if "Mock can't be used in 'await' expression" in error_msg:
            # Это ошибка мока в тестах - возвращаем правильный async context manager
            from contextlib import asynccontextmanager
            
            @asynccontextmanager
            async def empty_context():
                yield None
            
            return empty_context()
        
        logger.debug(f"⚠️ Resource manager недоступен: {e}")
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def empty_context():
            yield None
        
        return empty_context()


async def _send_stage_error(
    state: AgentState,
    stage: str,
    error_type: str,
    message: str
) -> None:
    """Отправляет событие ошибки этапа через SSE."""
    if not state.get("enable_sse"):
        return
    
    try:
        from backend.sse_manager import get_sse_manager
        sse = get_sse_manager()
        task_id = state.get("task_id", "unknown")
        
        await sse.send_stage_event(
            task_id=task_id,
            stage=stage,
            status="error",
            data={
                "error_type": error_type,
                "message": message
            }
        )
    except Exception as e:
        logger.debug(f"⚠️ Не удалось отправить stage_error: {e}")


def streaming_node(
    stage: str,
    fallback_key: str | None = None,
    fallback_value: Any = None
) -> Callable[[StreamingNodeFunc], StreamingNodeFunc]:
    """Декоратор для стриминговых узлов с общей логикой обработки событий.
    
    Автоматически:
    - Сохраняет события в EventStore
    - Обрабатывает ошибки с fallback
    - Добавляет event_references в state
    
    Args:
        stage: Название этапа (planning, coding, etc.)
        fallback_key: Ключ в state для записи fallback значения при ошибке
        fallback_value: Значение по умолчанию при ошибке
        
    Usage:
        @streaming_node(stage="planning", fallback_key="plan", fallback_value="")
        async def stream_planner_node(state: AgentState) -> AsyncGenerator[tuple[str, Any], None]:
            async for event_type, data in agent.create_plan_stream(...):
                yield (event_type, data)
    """
    def decorator(stream_func: StreamingNodeFunc) -> StreamingNodeFunc:
        @functools.wraps(stream_func)
        async def wrapper(state: AgentState) -> AsyncGenerator[tuple[str, Any], None]:
            """Обёртка для стримингового узла с обработкой событий."""
            # Получаем session_id для изоляции событий
            session_id = state.get("task_id") or state.get("session_id") or "default"
            
            # Инициализируем EventStore для сессии
            from infrastructure.event_store import get_event_store
            event_store = await get_event_store(session_id)
            
            # Инициализируем список ссылок на события если его нет или он None
            if "event_references" not in state or state.get("event_references") is None:
                state["event_references"] = []
            
            final_state = None
            
            try:
                # Выполняем стриминговую функцию
                # ИСПРАВЛЕНИЕ: Проверяем что stream_func(state) возвращает async генератор, а не корутину
                stream_gen = stream_func(state)
                if not hasattr(stream_gen, '__aiter__'):
                    error_msg = (
                        f"stream_func для {stage} должен возвращать async генератор, "
                        f"получен {type(stream_gen)}. Возможно функция не декорирована @streaming_node "
                        f"или вызывается неправильно."
                    )
                    logger.error(f"❌ {error_msg}")
                    raise TypeError(error_msg)
                
                logger.debug(f"🔄 Начало стриминга для {stage}")
                async for event_type, data in stream_gen:
                    if event_type == "done":
                        # Финальное состояние
                        final_state = data
                        # ИСПРАВЛЕНИЕ: Выходим из цикла сразу после получения "done"
                        # Это предотвращает зависание workflow
                        break
                    else:
                        # Сохраняем событие в EventStore
                        event_id = await event_store.save_event(event_type, data)
                        # ИСПРАВЛЕНИЕ: Дополнительная проверка на None перед append
                        if state.get("event_references") is None:
                            state["event_references"] = []
                        state["event_references"].append(event_id)
                        # Логирование уже выполняется в event_store.save_event(), не дублируем
                        
                        # Пробрасываем событие дальше
                        yield (event_type, data)
                
                # Если есть финальное состояние, добавляем event_references
                if final_state:
                    # ИСПРАВЛЕНИЕ: Убеждаемся что event_references не None
                    event_refs = state.get("event_references")
                    if event_refs is None:
                        event_refs = []
                    final_state["event_references"] = event_refs
                    yield ("done", final_state)
                else:
                    # Если не было финального состояния, создаём его из текущего state
                    # ИСПРАВЛЕНИЕ: Это fallback на случай если "done" не был получен
                    if state.get("event_references") is None:
                        state["event_references"] = []
                    if fallback_key:
                        state[fallback_key] = fallback_value
                    yield ("done", state)
                    
            except LLMModelUnavailableError as e:
                logger.error(
                    f"❌ Модель {e.model} недоступна в стриминговом узле {stage}: {e}. "
                    f"Рекомендуется переключиться на другую модель."
                )
                await _send_stage_error(
                    state, stage, "model_unavailable",
                    f"Модель {e.model} недоступна. Рекомендуется переключиться на другую модель."
                )
                
                # Устанавливаем fallback значение если указано
                if fallback_key is not None:
                    value = fallback_value() if callable(fallback_value) else fallback_value
                    state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                
                # Возвращаем state с fallback
                if state.get("event_references") is None:
                    state["event_references"] = []
                yield ("done", state)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в стриминговом узле {stage}: {e}", error=e)
                
                # Отправляем событие ошибки
                await _send_stage_error(
                    state, stage, "error",
                    f"Ошибка в стриминговом узле: {str(e)[:100]}"
                )
                
                # Устанавливаем fallback значение если указано
                if fallback_key is not None:
                    value = fallback_value() if callable(fallback_value) else fallback_value
                    state[fallback_key] = value  # type: ignore[literal-required]  # LangGraph AgentState требует Dict[str, Any], но мы знаем что fallback_key валиден
                
                # Возвращаем state с fallback
                if state.get("event_references") is None:
                    state["event_references"] = []
                yield ("done", state)
        
        return wrapper
    return decorator
