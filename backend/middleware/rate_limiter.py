"""Rate limiting middleware для защиты от DoS атак."""
import time
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from utils.logger import get_logger

logger = get_logger()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware для ограничения количества запросов от одного IP адреса.
    
    Использует простой в памяти счётчик запросов с временным окном.
    """
    
    def __init__(self, app, requests_per_minute: int = 60, cleanup_interval: int = 60):
        """Инициализация middleware.
        
        Args:
            app: FastAPI приложение
            requests_per_minute: Максимальное количество запросов в минуту
            cleanup_interval: Интервал очистки старых записей (секунды)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.cleanup_interval = cleanup_interval
        self.request_counts: Dict[str, list[float]] = {}
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        """Обработка запроса с проверкой rate limit.
        
        Args:
            request: HTTP запрос
            call_next: Следующий middleware/handler
            
        Returns:
            HTTP ответ
            
        Raises:
            HTTPException: Если превышен rate limit
        """
        # Получаем IP адрес клиента
        client_ip = request.client.host if request.client else "unknown"
        
        # Очищаем старые записи если нужно
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_records(current_time)
            self.last_cleanup = current_time
        
        # Проверяем rate limit
        if not self._check_rate_limit(client_ip, current_time):
            logger.warning(f"⚠️ Rate limit превышен для IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Пожалуйста, подождите перед повторной попыткой."
            )
        
        # Продолжаем обработку запроса
        response = await call_next(request)
        return response
    
    def _check_rate_limit(self, client_ip: str, current_time: float) -> bool:
        """Проверяет, не превышен ли rate limit для IP адреса.
        
        Args:
            client_ip: IP адрес клиента
            current_time: Текущее время (unix timestamp)
            
        Returns:
            True если запрос разрешён, False если превышен лимит
        """
        # Получаем или создаём список времён запросов для этого IP
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        request_times = self.request_counts[client_ip]
        
        # Удаляем запросы старше минуты
        one_minute_ago = current_time - 60
        request_times[:] = [t for t in request_times if t > one_minute_ago]
        
        # Проверяем лимит
        if len(request_times) >= self.requests_per_minute:
            return False
        
        # Добавляем текущий запрос
        request_times.append(current_time)
        return True
    
    def _cleanup_old_records(self, current_time: float) -> None:
        """Удаляет записи для IP адресов, которые давно не делали запросы.
        
        Args:
            current_time: Текущее время (unix timestamp)
        """
        five_minutes_ago = current_time - 300
        ips_to_remove = []
        
        for client_ip, request_times in self.request_counts.items():
            # Если последний запрос был более 5 минут назад, удаляем запись
            if request_times and request_times[-1] < five_minutes_ago:
                ips_to_remove.append(client_ip)
        
        for client_ip in ips_to_remove:
            del self.request_counts[client_ip]
        
        if ips_to_remove:
            logger.debug(f"🧹 Очищены записи для {len(ips_to_remove)} IP адресов")
