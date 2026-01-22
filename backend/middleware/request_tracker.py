"""Middleware для отслеживания активных запросов.

Используется для graceful shutdown - ожидания завершения активных запросов.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.shutdown_manager import get_shutdown_manager
from utils.logger import get_logger

logger = get_logger()


class RequestTrackerMiddleware(BaseHTTPMiddleware):
    """Middleware для отслеживания активных запросов.
    
    Увеличивает счётчик при начале запроса и уменьшает при завершении.
    Используется ShutdownManager для ожидания завершения активных запросов.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Обрабатывает запрос с отслеживанием."""
        shutdown_manager = get_shutdown_manager()
        
        # Пропускаем health check и docs endpoints
        if request.url.path in ["/health", "/docs", "/openapi.json", "/"]:
            return await call_next(request)
        
        # Увеличиваем счётчик активных запросов
        await shutdown_manager.increment_active_requests()
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            return response
        finally:
            # Уменьшаем счётчик при завершении
            await shutdown_manager.decrement_active_requests()
