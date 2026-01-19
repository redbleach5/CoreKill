"""Управление пулингом соединений с Ollama."""
import asyncio
from typing import Optional, Dict, Any
from functools import lru_cache
import httpx
from utils.logger import get_logger
from utils.env_config import get_env_config

logger = get_logger()


class OllamaConnectionPool:
    """Пул соединений для Ollama."""
    
    def __init__(self, base_url: str, pool_size: int = 10, timeout: int = 300):
        """Инициализация пула соединений.
        
        Args:
            base_url: URL базы Ollama
            pool_size: Размер пула
            timeout: Timeout для соединений (секунды)
        """
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        self.semaphore = asyncio.Semaphore(pool_size)
    
    async def initialize(self) -> None:
        """Инициализирует пул соединений."""
        if self.client is None:
            limits = httpx.Limits(
                max_connections=self.pool_size,
                max_keepalive_connections=self.pool_size // 2
            )
            timeout = httpx.Timeout(self.timeout)
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                limits=limits,
                timeout=timeout,
                http2=True
            )
            logger.info(f"✅ Пул соединений инициализирован: {self.pool_size} соединений")
    
    async def close(self) -> None:
        """Закрывает пул соединений."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("✅ Пул соединений закрыт")
    
    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> httpx.Response:
        """Выполняет HTTP запрос через пул.
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры для запроса
            
        Returns:
            HTTP ответ
            
        Raises:
            RuntimeError: Если пул не инициализирован
            httpx.HTTPError: Если запрос не удался
        """
        if self.client is None:
            raise RuntimeError("Пул соединений не инициализирован. Вызовите initialize() сначала.")
        
        async with self.semaphore:
            try:
                response = await self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                logger.error(f"❌ HTTP ошибка при запросе к {endpoint}: {e}")
                raise
    
    async def get(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        """GET запрос.
        
        Args:
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры
            
        Returns:
            HTTP ответ
        """
        return await self.request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        """POST запрос.
        
        Args:
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры
            
        Returns:
            HTTP ответ
        """
        return await self.request("POST", endpoint, **kwargs)
    
    async def stream(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ):
        """Выполняет streaming запрос.
        
        Args:
            method: HTTP метод
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры
            
        Yields:
            Части ответа
        """
        if self.client is None:
            raise RuntimeError("Пул соединений не инициализирован. Вызовите initialize() сначала.")
        
        async with self.semaphore:
            async with self.client.stream(method, endpoint, **kwargs) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk


# Глобальный пул соединений
_pool: Optional[OllamaConnectionPool] = None


async def get_ollama_pool() -> OllamaConnectionPool:
    """Возвращает глобальный пул соединений Ollama.
    
    Returns:
        Экземпляр OllamaConnectionPool
    """
    global _pool
    
    if _pool is None:
        env_config = get_env_config()
        _pool = OllamaConnectionPool(
            base_url=env_config.ollama_base_url,
            pool_size=env_config.connection_pool_size,
            timeout=env_config.ollama_timeout
        )
        await _pool.initialize()
    
    return _pool


async def close_ollama_pool() -> None:
    """Закрывает глобальный пул соединений."""
    global _pool
    
    if _pool:
        await _pool.close()
        _pool = None
