"""Вспомогательные функции для обработки SSE событий."""
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from utils.logger import get_logger
from utils.ui_delays import ui_sleep
from backend.sse_manager import SSEManager

logger = get_logger()


async def send_stage_events(
    stage: str,
    message: str,
    result: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """Отправляет пару stage_start и stage_end событий.
    
    Args:
        stage: Название этапа
        message: Сообщение для пользователя
        result: Результаты этапа
        
    Yields:
        SSE события
    """
    # ОПТИМИЗАЦИЯ: Убрано избыточное логирование - события stage_start/stage_end важные, но не нужно логировать каждое
    # Логируем только на уровне DEBUG для отладки
    logger.debug(f"📤 Отправляю stage_start для {stage}")
    event_start = await SSEManager.stream_stage_start(
        stage=stage,
        message=f"Начинаю {message}..."
    )
    yield event_start
    # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
    # await ui_sleep()
    
    logger.debug(f"📤 Отправляю stage_end для {stage}")
    event_end = await SSEManager.stream_stage_end(
        stage=stage,
        message=message,
        result=result or {}
    )
    yield event_end
    # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
    # await ui_sleep()


async def send_greeting_response(
    task_id: str,
    greeting_message: str,
    task: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Отправляет приветственный ответ.
    
    Args:
        task_id: ID задачи
        greeting_message: Текст приветствия
        task: Исходная задача пользователя (опционально, для результатов)
        
    Yields:
        SSE события
    """
    logger.info("🚀 Обнаружено приветствие - быстрый ответ без workflow")
    
    # stage_start для intent
    event1 = await SSEManager.stream_stage_start(
        stage="intent",
        message="Определяю намерение..."
    )
    yield event1
    # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
    # await ui_sleep()
    
    # stage_end для intent
    event2 = await SSEManager.stream_stage_end(
        stage="intent",
        message="Намерение определено: greeting",
        result={"type": "greeting", "confidence": 0.95}
    )
    yield event2
    # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
    # await ui_sleep()
    
    # stage_end для greeting
    event3 = await SSEManager.stream_stage_end(
        stage="greeting",
        message=greeting_message,
        result={"type": "greeting", "message": greeting_message}
    )
    yield event3
    # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
    # await ui_sleep()
    
    # final_result
    results = {
        "intent": {
            "type": "greeting",
            "confidence": 0.95,
            "description": "Приветствие пользователя"
        },
        "greeting_message": greeting_message
    }
    if task:
        results["task"] = task
    
    event4 = await SSEManager.stream_final_result(
        task_id=task_id,
        results=results,
        metrics={
            "planning": 0.0,
            "research": 0.0,
            "testing": 0.0,
            "coding": 0.0,
            "overall": 0.0
        }
    )
    yield event4
    # ОПТИМИЗАЦИЯ: Убрана критическая задержка - final_result должен отправляться сразу
    # await ui_sleep("critical")
    logger.info("✅ Все события для greeting отправлены")


async def send_error_response(
    stage: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None
) -> str:
    """Отправляет ошибку.
    
    Args:
        stage: Этап, на котором произошла ошибка
        error_message: Сообщение об ошибке
        error_details: Дополнительные детали ошибки
        
    Returns:
        SSE событие ошибки
    """
    logger.error(f"❌ Ошибка на этапе {stage}: {error_message}")
    return await SSEManager.stream_error(
        stage=stage,
        error_message=error_message,
        error_details=error_details or {}
    )
