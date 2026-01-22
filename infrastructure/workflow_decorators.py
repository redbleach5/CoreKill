"""Декораторы для workflow nodes.

Убирают дублирование обработки ошибок, метрик и checkpoints.
"""
import asyncio
import time
from functools import wraps
from typing import Callable, Any, TypeVar, Awaitable

from infrastructure.workflow_state import AgentState
from infrastructure.local_llm import LLMTimeoutError
from utils.logger import get_logger

logger = get_logger()

# Type alias для node функции
NodeFunc = Callable[[AgentState], Awaitable[AgentState]]
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
            
            try:
                # Выполняем основную логику узла
                result = await func(state)
                
                # Записываем метрику времени
                _record_stage_duration(stage, time.time() - start_time)
                
                # Сохраняем checkpoint
                _save_checkpoint(result, stage)
                
                return result
                
            except LLMTimeoutError as e:
                logger.warning(f"⏱️ Таймаут на этапе {stage}: {e}")
                await _send_stage_error(
                    state, stage, "timeout",
                    f"Превышено время ожидания на этапе {stage}"
                )
                
                # Устанавливаем fallback значение если указано
                if fallback_key is not None:
                    value = fallback_value() if callable(fallback_value) else fallback_value
                    state[fallback_key] = value  # type: ignore[literal-required]
                
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
                    state[fallback_key] = value  # type: ignore[literal-required]
                
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
