"""Управление пулингом соединений с Ollama.

Асинхронный пул соединений для работы с Ollama API через httpx.
Используется в AsyncLocalLLM для production и многопользовательского режима.

Преимущества async пула:
- Не блокирует event loop при LLM запросах (30-120 сек)
- Несколько пользователей могут работать параллельно
- HTTP/2 и connection pooling для лучшей производительности
- Лучшее масштабирование для production

Использование:
    from infrastructure.connection_pool import get_ollama_pool
    
    pool = await get_ollama_pool()
    result = await pool.generate(model="qwen2.5-coder:7b", prompt="...")
"""
import asyncio
import json
import threading
from typing import Optional, Any, AsyncGenerator
import httpx
from utils.logger import get_logger
from utils.config import get_config

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
        """Инициализирует пул соединений.
        
        Пытается использовать HTTP/2, но fallback на HTTP/1.1 если h2 не установлен.
        """
        if self.client is None:
            limits = httpx.Limits(
                max_connections=self.pool_size,
                max_keepalive_connections=self.pool_size // 2
            )
            timeout = httpx.Timeout(self.timeout)
            
            # Пытаемся использовать HTTP/2, но fallback на HTTP/1.1
            http2_enabled = False
            try:
                import h2  # noqa: F401
                http2_enabled = True
                logger.debug("✅ HTTP/2 поддержка доступна (h2 установлен)")
            except ImportError:
                logger.warning(
                    "⚠️ HTTP/2 недоступен (h2 не установлен). "
                    "Используется HTTP/1.1. Для HTTP/2 установите: pip install httpx[http2]"
                )
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                limits=limits,
                timeout=timeout,
                http2=http2_enabled
            )
            logger.info(
                f"✅ Пул соединений инициализирован: {self.pool_size} соединений "
                f"(HTTP/{'2' if http2_enabled else '1.1'})"
            )
    
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
            httpx.ConnectError: Если не удалось подключиться к Ollama
            httpx.TimeoutException: Если запрос превысил таймаут
        """
        if self.client is None:
            raise RuntimeError("Пул соединений не инициализирован. Вызовите initialize() сначала.")
        
        async with self.semaphore:
            try:
                response = await self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.ConnectError as e:
                error_msg = f"Не удалось подключиться к Ollama по адресу {self.base_url}"
                logger.error(f"❌ {error_msg}: {e}")
                raise RuntimeError(f"{error_msg}. Проверьте что Ollama запущен и доступен.") from e
            except httpx.TimeoutException as e:
                error_msg = f"Таймаут запроса к {endpoint} (таймаут: {self.timeout}с)"
                logger.warning(f"⏱️ {error_msg}")
                raise
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"❌ HTTP {e.response.status_code} ошибка при запросе к {endpoint}: {e.response.text[:200]}"
                )
                raise
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
            Сгенерированный текст. Пустая строка в случае ошибки.
            
        Raises:
            RuntimeError: Если не удалось подключиться к Ollama
            httpx.HTTPError: Если запрос не удался
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **(options or {}),
            **kwargs
        }
        
        try:
            response = await self.post("/api/generate", json=payload)
            data = response.json()
            result = data.get("response", "").strip()
            
            if not result:
                logger.warning(f"⚠️ Пустой ответ от Ollama для модели {model}")
            
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка генерации через connection pool: {e}", error=e)
            # Пробрасываем ошибку выше для обработки retry логикой
            raise
    
    async def stream(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> AsyncGenerator[bytes, None]:
        """Выполняет streaming запрос.
        
        Args:
            method: HTTP метод
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры
            
        Yields:
            Части ответа (bytes)
            
        Raises:
            RuntimeError: Если пул не инициализирован
            httpx.HTTPError: Если запрос не удался
        """
        if self.client is None:
            raise RuntimeError("Пул соединений не инициализирован. Вызовите initialize() сначала.")
        
        async with self.semaphore:
            try:
                async with self.client.stream(method, endpoint, **kwargs) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPError as e:
                logger.error(f"❌ HTTP ошибка при streaming запросе к {endpoint}: {e}")
                raise
    
    async def generate_stream(
        self,
        model: str,
        prompt: str,
        options: Optional[dict] = None,
        **kwargs: Any
    ) -> AsyncGenerator[dict, None]:
        """Генерирует текст через Ollama API со стримингом.
        
        Это async-аналог ollama.generate(stream=True) для использования с пулом.
        
        Args:
            model: Название модели Ollama
            prompt: Текст промпта
            options: Опции генерации (temperature, top_p, num_predict)
            **kwargs: Дополнительные параметры
            
        Yields:
            Словари с чанками ответа от Ollama API
            
        Example:
            async for chunk in pool.generate_stream(model="qwen2.5-coder:7b", prompt="..."):
                if chunk.get("done"):
                    break
                content = chunk.get("response", "")
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            **(options or {}),
            **kwargs
        }
        
        async for chunk_bytes in self.stream("POST", "/api/generate", json=payload):
            # Парсим JSON чанки от Ollama
            try:
                # Ollama отправляет JSON строки разделённые \n
                for line in chunk_bytes.decode('utf-8').strip().split('\n'):
                    if line:
                        yield json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"⚠️ Ошибка парсинга чанка: {e}")
                continue


# Глобальный пул соединений
_pool: Optional[OllamaConnectionPool] = None
_pool_lock = threading.Lock()
_pool_initialized = False


async def get_ollama_pool() -> OllamaConnectionPool:
    """Возвращает глобальный пул соединений Ollama.
    
    Создаёт и инициализирует пул при первом вызове (ленивая инициализация).
    Потокобезопасен для использования в многопоточных окружениях.
    Использует единый источник конфигурации (config.toml с поддержкой env vars).
    
    Returns:
        Экземпляр OllamaConnectionPool
        
    Raises:
        RuntimeError: Если не удалось инициализировать пул
    """
    global _pool, _pool_initialized
    
    if _pool is None:
        with _pool_lock:
            # Двойная проверка для потокобезопасности
            if _pool is None:
                try:
                    config = get_config()
                    _pool = OllamaConnectionPool(
                        base_url=config.ollama_host,
                        pool_size=config.connection_pool_size,
                        timeout=config.ollama_timeout
                    )
                    await _pool.initialize()
                    _pool_initialized = True
                    logger.info("✅ Ollama connection pool инициализирован")
                except Exception as e:
                    logger.error(f"❌ Ошибка инициализации connection pool: {e}", error=e)
                    _pool = None
                    raise RuntimeError(f"Не удалось инициализировать connection pool: {e}")
    
    return _pool


async def initialize_ollama_pool() -> None:
    """Явно инициализирует пул соединений.
    
    Вызывается при старте приложения для предварительной инициализации.
    Если пул уже инициализирован, ничего не делает.
    """
    try:
        await get_ollama_pool()
    except Exception as e:
        logger.warning(f"⚠️ Предварительная инициализация connection pool не удалась: {e}")


async def close_ollama_pool() -> None:
    """Закрывает глобальный пул соединений.
    
    Вызывается при graceful shutdown приложения.
    """
    global _pool, _pool_initialized
    
    with _pool_lock:
        if _pool:
            try:
                await _pool.close()
                logger.info("✅ Ollama connection pool закрыт")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при закрытии connection pool: {e}")
            finally:
                _pool = None
                _pool_initialized = False
