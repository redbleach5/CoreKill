"""Утилита для генерации SSE событий из workflow агентов."""
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime
import json


class SSEManager:
    """Менеджер для генерации Server-Sent Events из workflow агентов."""

    @staticmethod
    async def send_event(
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> str:
        """Генерирует SSE событие в формате text/event-stream.
        
        Args:
            event_type: Тип события (stage_start, stage_end, progress, result, error)
            data: Данные события
            event_id: Опциональный ID события
            
        Returns:
            Строка в формате SSE
        """
        if event_id is None:
            event_id = str(datetime.now().timestamp())
        
        lines: list[str] = []
        lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        
        # Добавляем timestamp
        data_with_timestamp = {
            **data,
            "timestamp": datetime.now().isoformat()
        }
        
        json_data = json.dumps(data_with_timestamp, ensure_ascii=False)
        lines.append(f"data: {json_data}")
        lines.append("")  # Пустая строка для завершения события
        
        # SSE требует двойной перевод строки (\n\n) для завершения события
        return "\n".join(lines) + "\n"

    @staticmethod
    async def stream_stage_start(
        stage: str,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерирует событие начала этапа.
        
        Args:
            stage: Название этапа (intent, planning, research, testing, coding, validation, reflection)
            message: Сообщение для пользователя на русском
            metadata: Дополнительные метаданные
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "stage": stage,
            "status": "start",
            "message": message
        }
        
        if metadata:
            data["metadata"] = metadata
        
        return await SSEManager.send_event("stage_start", data)

    @staticmethod
    async def stream_stage_progress(
        stage: str,
        progress: float,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерирует событие прогресса этапа.
        
        Args:
            stage: Название этапа
            progress: Прогресс от 0.0 до 1.0
            message: Сообщение на русском
            metadata: Дополнительные метаданные
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "stage": stage,
            "status": "progress",
            "progress": min(1.0, max(0.0, progress)),
            "message": message
        }
        
        if metadata:
            data["metadata"] = metadata
        
        return await SSEManager.send_event("stage_progress", data)

    @staticmethod
    async def stream_stage_end(
        stage: str,
        message: str = "",
        result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерирует событие завершения этапа.
        
        Args:
            stage: Название этапа
            message: Сообщение на русском
            result: Результат этапа
            metadata: Дополнительные метаданные
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "stage": stage,
            "status": "end",
            "message": message
        }
        
        if result:
            data["result"] = result
        
        if metadata:
            data["metadata"] = metadata
        
        return await SSEManager.send_event("stage_end", data)

    @staticmethod
    async def stream_error(
        stage: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерирует событие ошибки.
        
        Args:
            stage: Этап где произошла ошибка
            error_message: Сообщение об ошибке на русском
            error_details: Детали ошибки
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "stage": stage,
            "status": "error",
            "error": error_message
        }
        
        if error_details:
            data["error_details"] = error_details
        
        return await SSEManager.send_event("error", data)

    @staticmethod
    async def stream_final_result(
        task_id: str,
        results: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> str:
        """Генерирует финальное событие с результатами.
        
        Args:
            task_id: ID задачи
            results: Результаты выполнения (task, intent, plan, context, tests, code, validation)
            metrics: Метрики из рефлексии (planning, research, testing, coding, overall)
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "task_id": task_id,
            "status": "complete",
            "results": results,
            "metrics": metrics
        }
        
        return await SSEManager.send_event("complete", data)
