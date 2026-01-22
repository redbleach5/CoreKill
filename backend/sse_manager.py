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
    async def stream_code_chunk(
        chunk: str,
        is_final: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерирует событие с чанком кода для стриминга.
        
        Используется для отображения кода в IDE по мере генерации.
        
        Args:
            chunk: Часть сгенерированного кода
            is_final: Флаг последнего чанка
            metadata: Дополнительные метаданные (номер строки и т.д.)
            
        Returns:
            SSE событие
        """
        data: Dict[str, Any] = {
            "chunk": chunk,
            "is_final": is_final
        }
        
        if metadata:
            data["metadata"] = metadata
        
        return await SSEManager.send_event("code_chunk", data)

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

    @staticmethod
    async def stream_incremental_progress(
        function_name: str,
        status: str,
        current: int,
        total: int,
        fix_attempts: int = 0,
        error: Optional[str] = None
    ) -> str:
        """Генерирует событие прогресса инкрементальной генерации.
        
        Используется для Compiler-in-the-Loop (Phase 3).
        
        Args:
            function_name: Имя генерируемой функции
            status: Статус (generating, validating, fixing, passed, failed)
            current: Номер текущей функции (1-based)
            total: Общее количество функций
            fix_attempts: Количество попыток исправления
            error: Текст ошибки (если status == "failed")
            
        Returns:
            SSE событие
            
        Example:
            event = await SSEManager.stream_incremental_progress(
                function_name="calculate_sum",
                status="passed",
                current=2,
                total=5,
                fix_attempts=0
            )
        """
        data: Dict[str, Any] = {
            "function": function_name,
            "status": status,
            "fix_attempts": fix_attempts,
            "progress": {
                "current": current,
                "total": total
            }
        }
        
        if error:
            data["error"] = error
        
        return await SSEManager.send_event("incremental_progress", data)

    async def send_stage_event(
        self,
        task_id: str,
        stage: str,
        status: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Отправляет событие этапа в активный стрим.
        
        Используется для отправки ошибок и других событий из workflow nodes.
        
        Args:
            task_id: ID задачи
            stage: Название этапа
            status: Статус (start, progress, end, error)
            data: Дополнительные данные
        """
        event_data: Dict[str, Any] = {
            "stage": stage,
            "status": status,
            "task_id": task_id
        }
        
        if data:
            event_data.update(data)
        
        # Логируем событие (реальная отправка через yield в stream generator)
        from utils.logger import get_logger
        logger = get_logger()
        
        if status == "error":
            error_type = data.get("error_type", "unknown") if data else "unknown"
            message = data.get("message", "") if data else ""
            logger.warning(f"⚠️ Stage error [{stage}]: {error_type} - {message}")


# Singleton instance
_sse_manager: Optional[SSEManager] = None


def get_sse_manager() -> SSEManager:
    """Возвращает singleton экземпляр SSEManager.
    
    Returns:
        SSEManager instance
    """
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEManager()
    return _sse_manager
