"""Rate Limiter для веб-поиска."""
import time
from typing import Optional
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("autonomous_improver")


class RateLimiter:
    """Ограничитель частоты запросов.
    
    Используется для веб-поиска, чтобы не превышать лимиты API.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """Инициализирует rate limiter.
        
        Args:
            max_requests: Максимальное количество запросов
            window_seconds: Окно времени в секундах
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: deque = deque()  # Временные метки запросов
    
    def can_make_request(self) -> bool:
        """Проверяет, можно ли сделать запрос.
        
        Returns:
            True если можно, False если нужно подождать
        """
        now = time.time()
        
        # Удаляем старые запросы (старше окна)
        while self._requests and self._requests[0] < now - self.window_seconds:
            self._requests.popleft()
        
        # Проверяем лимит
        return len(self._requests) < self.max_requests
    
    def wait_time(self) -> float:
        """Возвращает время ожидания до следующего возможного запроса.
        
        Returns:
            Время в секундах (0 если можно делать запрос сейчас)
        """
        if self.can_make_request():
            return 0.0
        
        now = time.time()
        # Время до истечения самого старого запроса в окне
        if self._requests:
            oldest_request = self._requests[0]
            wait = self.window_seconds - (now - oldest_request)
            return max(0.0, wait)
        
        return 0.0
    
    def record_request(self) -> None:
        """Записывает выполненный запрос."""
        now = time.time()
        self._requests.append(now)
        
        # Очищаем старые запросы
        while self._requests and self._requests[0] < now - self.window_seconds:
            self._requests.popleft()
    
    async def wait_if_needed(self) -> None:
        """Ждёт, если нужно, перед запросом."""
        wait = self.wait_time()
        if wait > 0:
            logger.debug(f"⏳ Rate limiter: ожидание {wait:.1f}с")
            import asyncio
            await asyncio.sleep(wait)
    
    def get_stats(self) -> dict:
        """Возвращает статистику rate limiter."""
        now = time.time()
        recent_requests = [
            req for req in self._requests
            if req >= now - self.window_seconds
        ]
        
        return {
            "current_requests": len(recent_requests),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "can_make_request": self.can_make_request(),
            "wait_time": self.wait_time()
        }
