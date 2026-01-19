"""Управление пулингом соединений с Ollama.

СТАТУС: Реализовано, но НЕ ИНТЕГРИРОВАНО в workflow.

Текущая система использует синхронный LocalLLM (ollama.generate).
Этот модуль подготовлен для будущей миграции на async архитектуру.

Для интеграции необходимо:
1. Переписать LocalLLM на async с использованием этого пула
2. Сделать агенты async (async def execute)
3. Использовать await в workflow_nodes.py
4. Обновить LangGraph на async execution

Преимущества async пула:
- Не блокирует event loop при LLM запросах (30-120 сек)
- Несколько пользователей могут работать параллельно
- Лучшее масштабирование для production
"""
import asyncio
from typing import Optional, Any
from functools import lru_cache
import httpx
from utils.logger import get_logger
from utils.env_config import get_env_config

logger = get_logger()


class OllamaConnectionPool:
    """Асинхронный пул соединений для Ollama.
    
    Использует httpx.AsyncClient с connection pooling и HTTP/2.
    Semaphore ограничивает количество одновременных запросов.
    """
    
    def __init__(self, base_url: str, pool_size: int = 10, timeout: int = 300):
        """Инициализация пула соединений.
        
        Args:
            base_url: URL базы Ollama (например, http://localhost:11434)
            pool_size: Размер пула (максимум одновременных соединений)
            timeout: Timeout для соединений в секундах
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
            endpoint: Endpoint API (например, /api/generate)
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
    
    async def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[dict] = None,
        **kwargs: Any
    ) -> str:
        """Генерирует текст через Ollama API.
        
        Это async-аналог ollama.generate() для использования с пулом.
        
        Args:
            model: Название модели Ollama
            prompt: Текст промпта
            options: Опции генерации (temperature, top_p, num_predict)
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный текст
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **(options or {}),
            **kwargs
        }
        
        response = await self.post("/api/generate", json=payload)
        data = response.json()
        return data.get("response", "")
    
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
            Части ответа (bytes)
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
    
    Создаёт и инициализирует пул при первом вызове.
    
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
