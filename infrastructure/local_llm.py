"""Обёртка для работы с локальными LLM через Ollama.

Поддерживает два режима работы:
- Синхронный (generate) — для CLI и простых скриптов
- Асинхронный (generate_async) — для FastAPI и многопользовательского режима

Асинхронный режим использует asyncio.to_thread() для совместимости с существующим кодом,
а также может использовать httpx через OllamaConnectionPool для лучшей производительности.
"""
import asyncio
import ollama
from typing import Optional, Dict, Any
import time
import concurrent.futures

from utils.logger import get_logger


logger = get_logger()


class LLMTimeoutError(Exception):
    """Исключение для таймаута LLM запроса."""
    pass


class LocalLLM:
    """Класс для работы с локальными моделями через Ollama API.
    
    Поддерживает retry с exponential backoff, настройку параметров генерации и обработку ошибок.
    """

    # Базовая задержка для exponential backoff (секунды)
    BASE_RETRY_DELAY = 1.0
    # Максимальная задержка между retry
    MAX_RETRY_DELAY = 30.0

    def __init__(
        self,
        model: str,
        temperature: float = 0.25,
        top_p: float = 0.9,
        timeout: int = 120,
        max_retries: int = 3
    ) -> None:
        """Инициализация LocalLLM.
        
        Args:
            model: Название модели Ollama
            temperature: Температура генерации (0.15-0.35 по правилам)
            top_p: Параметр top_p для генерации
            timeout: Таймаут запроса в секундах (по умолчанию 120с)
            max_retries: Максимальное количество повторных попыток
        """
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout
        self.max_retries = max_retries
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Вычисляет задержку для exponential backoff.
        
        Args:
            attempt: Номер попытки (начиная с 0)
            
        Returns:
            Задержка в секундах
        """
        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        return min(delay, self.MAX_RETRY_DELAY)

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_predict: int = 4096,
        **kwargs: Any
    ) -> str:
        """Генерирует текст на основе промпта.
        
        Args:
            prompt: Текст промпта
            temperature: Температура генерации (переопределяет значение по умолчанию)
            top_p: Параметр top_p (переопределяет значение по умолчанию)
            num_predict: Максимальное количество токенов для генерации
            **kwargs: Дополнительные параметры для ollama.generate
            
        Returns:
            Сгенерированный текст. Пустая строка в случае ошибки.
        """
        temp = temperature if temperature is not None else self.temperature
        tp = top_p if top_p is not None else self.top_p
        
        options: Dict[str, Any] = {
            "temperature": temp,
            "top_p": tp,
            "num_predict": num_predict
        }
        
        # Добавляем дополнительные параметры если есть
        options.update(kwargs.get("options", {}))
        
        last_error: Optional[Exception] = None
        
        # Для коротких задач (intent, planning) уменьшаем num_predict для скорости
        if num_predict > 1024 and len(prompt) < 500:
            options["num_predict"] = min(512, num_predict // 2)
        
        for attempt in range(self.max_retries + 1):
            try:
                # Проверяем что Ollama доступен (только на первой попытке)
                if attempt == 0:
                    try:
                        ollama.list()
                    except Exception as e:
                        logger.warning(f"⚠️ Ollama недоступен, проверьте что сервис запущен: {e}")
                        return ""
                
                start_time = time.time()
                
                # Вызов с timeout через ThreadPoolExecutor (работает в любом потоке)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        ollama.generate,
                        model=self.model,
                        prompt=prompt,
                        options=options,
                        **{k: v for k, v in kwargs.items() if k != "options"}
                    )
                    
                    try:
                        response = future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        elapsed = time.time() - start_time
                        logger.warning(f"⏱️ Таймаут LLM запроса после {elapsed:.1f}с")
                        raise LLMTimeoutError(f"Таймаут {self.timeout}с")
                
                elapsed = time.time() - start_time
                result = response.get("response", "").strip()
                
                if result:
                    logger.debug(f"✅ LLM ответ получен за {elapsed:.1f}с ({len(result)} символов)")
                    return result
                else:
                    logger.warning(f"⚠️ Пустой ответ от LLM после {elapsed:.1f}с")
                    
            except (LLMTimeoutError, concurrent.futures.TimeoutError):
                last_error = LLMTimeoutError(f"Таймаут {self.timeout}с")
                backoff = self._calculate_backoff(attempt)
                if attempt < self.max_retries:
                    logger.info(f"🔄 Retry {attempt + 1}/{self.max_retries} через {backoff:.1f}с...")
                    time.sleep(backoff)
                    continue
                    
            except Exception as e:
                last_error = e
                backoff = self._calculate_backoff(attempt)
                if attempt < self.max_retries:
                    logger.info(f"🔄 Retry {attempt + 1}/{self.max_retries} через {backoff:.1f}с после ошибки: {e}")
                    time.sleep(backoff)
                    continue
                else:
                    break
        
        # Если все попытки неудачны
        error_msg = f"Ошибка Ollama после {self.max_retries + 1} попыток: {last_error}"
        logger.error(f"❌ {error_msg}", error=last_error)
        return ""

    def chat(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """Генерирует ответ в формате чата.
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            temperature: Температура генерации
            top_p: Параметр top_p
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ модели. Пустая строка в случае ошибки.
        """
        temp = temperature if temperature is not None else self.temperature
        tp = top_p if top_p is not None else self.top_p
        
        options: Dict[str, Any] = {
            "temperature": temp,
            "top_p": tp
        }
        options.update(kwargs.get("options", {}))
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                # Вызов с timeout через ThreadPoolExecutor
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        ollama.chat,
                        model=self.model,
                        messages=messages,
                        options=options,
                        **{k: v for k, v in kwargs.items() if k != "options"}
                    )
                    
                    try:
                        response = future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        elapsed = time.time() - start_time
                        logger.warning(f"⏱️ Таймаут chat запроса после {elapsed:.1f}с")
                        raise LLMTimeoutError(f"Таймаут {self.timeout}с")
                
                result = response.get("message", {}).get("content", "").strip()
                if result:
                    return result
                    
            except (LLMTimeoutError, concurrent.futures.TimeoutError):
                last_error = LLMTimeoutError(f"Таймаут {self.timeout}с")
                backoff = self._calculate_backoff(attempt)
                if attempt < self.max_retries:
                    logger.info(f"🔄 Chat retry {attempt + 1}/{self.max_retries} через {backoff:.1f}с...")
                    time.sleep(backoff)
                    continue
                    
            except Exception as e:
                last_error = e
                backoff = self._calculate_backoff(attempt)
                if attempt < self.max_retries:
                    logger.info(f"🔄 Chat retry {attempt + 1}/{self.max_retries} через {backoff:.1f}с после ошибки: {e}")
                    time.sleep(backoff)
                    continue
                else:
                    break
        
        error_msg = f"Ошибка Ollama chat после {self.max_retries + 1} попыток: {last_error}"
        logger.error(f"❌ {error_msg}", error=last_error)
        return ""
    
    # === ASYNC МЕТОДЫ ===
    # Используют asyncio.to_thread() для совместимости с существующим синхронным кодом
    # Это позволяет не блокировать event loop FastAPI при LLM запросах
    
    async def generate_async(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_predict: int = 4096,
        **kwargs: Any
    ) -> str:
        """Асинхронная генерация текста на основе промпта.
        
        Использует asyncio.to_thread() для выполнения синхронного ollama.generate()
        в отдельном потоке, не блокируя event loop.
        
        Args:
            prompt: Текст промпта
            temperature: Температура генерации
            top_p: Параметр top_p
            num_predict: Максимальное количество токенов
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный текст. Пустая строка в случае ошибки.
        """
        return await asyncio.to_thread(
            self.generate,
            prompt,
            temperature,
            top_p,
            num_predict,
            **kwargs
        )
    
    async def chat_async(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """Асинхронная генерация ответа в формате чата.
        
        Использует asyncio.to_thread() для выполнения синхронного ollama.chat()
        в отдельном потоке, не блокируя event loop.
        
        Args:
            messages: Список сообщений
            temperature: Температура генерации
            top_p: Параметр top_p
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ модели. Пустая строка в случае ошибки.
        """
        return await asyncio.to_thread(
            self.chat,
            messages,
            temperature,
            top_p,
            **kwargs
        )


class AsyncLocalLLM:
    """Полностью асинхронный класс для работы с Ollama через httpx.
    
    Использует OllamaConnectionPool для HTTP/2 и connection pooling.
    Рекомендуется для production и многопользовательского режима.
    
    Примечание: Требует инициализации пула через get_ollama_pool().
    """
    
    def __init__(
        self,
        model: str,
        temperature: float = 0.25,
        top_p: float = 0.9,
        num_predict: int = 4096
    ) -> None:
        """Инициализация AsyncLocalLLM.
        
        Args:
            model: Название модели Ollama
            temperature: Температура генерации
            top_p: Параметр top_p
            num_predict: Максимальное количество токенов по умолчанию
        """
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.num_predict = num_predict
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_predict: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """Асинхронная генерация текста через httpx.
        
        Args:
            prompt: Текст промпта
            temperature: Температура генерации
            top_p: Параметр top_p
            num_predict: Максимальное количество токенов
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный текст
        """
        from infrastructure.connection_pool import get_ollama_pool
        
        pool = await get_ollama_pool()
        
        options = {
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": top_p if top_p is not None else self.top_p,
            "num_predict": num_predict if num_predict is not None else self.num_predict
        }
        
        try:
            result = await pool.generate(
                model=self.model,
                prompt=prompt,
                options=options
            )
            return result.strip() if result else ""
        except Exception as e:
            logger.error(f"❌ AsyncLocalLLM ошибка: {e}", error=e)
            return ""
    
    async def chat(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """Асинхронная генерация ответа в формате чата через httpx.
        
        Args:
            messages: Список сообщений
            temperature: Температура генерации
            top_p: Параметр top_p
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ модели
        """
        from infrastructure.connection_pool import get_ollama_pool
        
        pool = await get_ollama_pool()
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "top_p": top_p if top_p is not None else self.top_p
            }
        }
        
        try:
            response = await pool.post("/api/chat", json=payload)
            data = response.json()
            return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"❌ AsyncLocalLLM chat ошибка: {e}", error=e)
            return ""


def create_llm_for_stage(
    stage: str,
    model: str,
    temperature: float = 0.25,
    top_p: float = 0.9
) -> LocalLLM:
    """Создаёт LocalLLM с таймаутом, соответствующим этапу workflow.
    
    Args:
        stage: Название этапа (intent, planning, coding, etc.)
        model: Название модели Ollama
        temperature: Температура генерации
        top_p: Параметр top_p
        
    Returns:
        LocalLLM с правильным таймаутом для этапа
    """
    from utils.config import get_config
    config = get_config()
    timeout = config.get_stage_timeout(stage)
    
    return LocalLLM(
        model=model,
        temperature=temperature,
        top_p=top_p,
        timeout=timeout
    )
