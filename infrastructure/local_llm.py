"""Обёртка для работы с локальными LLM через Ollama.

Поддерживает два режима работы:
- Синхронный (generate) — для CLI и простых скриптов
- Асинхронный (generate_async) — для FastAPI и многопользовательского режима

Поддержка удалённого Ollama:
- Настраивается через config.toml [ollama] секцию
- Для связи между сетями рекомендуется Tailscale (работает в РФ)

Structured Output:
- generate_structured() возвращает Pydantic модели с гарантированным форматом
- Использует format="json" Ollama для принудительного JSON

Reasoning Models:
- Поддержка DeepSeek-R1, QwQ с <think> блоками
- Автоматический парсинг reasoning через reasoning_utils

Асинхронный режим использует asyncio.to_thread() для совместимости с существующим кодом,
а также может использовать httpx через OllamaConnectionPool для лучшей производительности.
"""
import asyncio
import json
import os
import ollama
from typing import Optional, Dict, Any, Type, TypeVar
import time
import concurrent.futures

from pydantic import BaseModel, ValidationError

from utils.logger import get_logger


logger = get_logger()


def _configure_ollama_host() -> None:
    """Настраивает хост Ollama из config.toml.
    
    Устанавливает переменную окружения OLLAMA_HOST которую
    использует ollama Python SDK.
    """
    # Не перезаписываем если уже установлено вручную
    if os.environ.get("OLLAMA_HOST"):
        return
    
    try:
        from utils.config import get_config
        config = get_config()
        host = config.ollama_host
        
        if host and host != "http://localhost:11434":
            os.environ["OLLAMA_HOST"] = host
            logger.info(f"🌐 Ollama хост: {host}")
    except Exception:
        pass  # Используем дефолт


# Настраиваем при импорте модуля
_configure_ollama_host()


class LLMTimeoutError(Exception):
    """Исключение для таймаута LLM запроса."""
    pass


class StructuredOutputError(Exception):
    """Исключение при ошибке structured output."""
    pass


# TypeVar для generic generate_structured
T = TypeVar('T', bound=BaseModel)


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
        format: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Генерирует текст на основе промпта.
        
        Args:
            prompt: Текст промпта
            temperature: Температура генерации (переопределяет значение по умолчанию)
            top_p: Параметр top_p (переопределяет значение по умолчанию)
            num_predict: Максимальное количество токенов для генерации
            format: Формат ответа ("json" для принудительного JSON)
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
                
                # Подготавливаем аргументы для ollama.generate
                generate_kwargs = {
                    "model": self.model,
                    "prompt": prompt,
                    "options": options,
                }
                
                # Добавляем format если указан (для JSON output)
                if format:
                    generate_kwargs["format"] = format
                
                # Добавляем остальные kwargs (кроме options и format)
                for k, v in kwargs.items():
                    if k not in ("options", "format"):
                        generate_kwargs[k] = v
                
                # Вызов с timeout через ThreadPoolExecutor (работает в любом потоке)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        ollama.generate,
                        **generate_kwargs
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
    
    # === STRUCTURED OUTPUT ===
    # Использует Pydantic для гарантированного формата ответов
    
    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        num_predict: int = 1024,
        retries: int = 2
    ) -> T:
        """Генерирует структурированный ответ с Pydantic валидацией.
        
        Использует format="json" Ollama для принудительного JSON формата,
        затем валидирует через Pydantic модель.
        
        Args:
            prompt: Текст промпта
            response_model: Pydantic модель для валидации ответа
            num_predict: Максимум токенов
            retries: Количество повторов при ошибке валидации
            
        Returns:
            Провалидированный Pydantic объект
            
        Raises:
            StructuredOutputError: Если не удалось получить валидный ответ
            
        Example:
            from models import IntentResponse
            
            response = llm.generate_structured(
                "Classify: напиши функцию",
                IntentResponse
            )
            print(response.intent)  # "create"
        """
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        # Добавляем инструкцию по формату в промпт
        enhanced_prompt = f"""{prompt}

IMPORTANT: Return response as valid JSON matching this schema:
{schema_str}

JSON:"""
        
        last_error: Optional[Exception] = None
        
        for attempt in range(retries + 1):
            try:
                # Генерируем с format="json"
                response = self.generate(
                    prompt=enhanced_prompt,
                    num_predict=num_predict,
                    format="json"  # Ollama принудительно возвращает JSON
                )
                
                if not response:
                    raise StructuredOutputError("Пустой ответ от LLM")
                
                # Пробуем распарсить как JSON
                # Иногда модель добавляет текст до/после JSON
                json_str = self._extract_json(response)
                
                # Pydantic валидация
                result = response_model.model_validate_json(json_str)
                
                logger.debug(
                    f"✅ Structured output успешно: {response_model.__name__} "
                    f"(попытка {attempt + 1})"
                )
                return result
                
            except ValidationError as e:
                last_error = e
                logger.warning(
                    f"⚠️ Validation failed (попытка {attempt + 1}/{retries + 1}): {e}"
                )
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    f"⚠️ JSON decode failed (попытка {attempt + 1}/{retries + 1}): {e}"
                )
                
            except Exception as e:
                last_error = e
                logger.error(f"❌ Structured output error: {e}")
                if attempt >= retries:
                    break
        
        raise StructuredOutputError(
            f"Не удалось получить валидный {response_model.__name__} "
            f"после {retries + 1} попыток: {last_error}"
        )
    
    def _extract_json(self, text: str) -> str:
        """Извлекает JSON из текста ответа.
        
        Обрабатывает случаи когда модель добавляет текст до/после JSON.
        
        Args:
            text: Текст с JSON
            
        Returns:
            Извлечённый JSON string
        """
        text = text.strip()
        
        # Убираем markdown блоки если есть
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Ищем JSON объект
        start = text.find('{')
        if start == -1:
            # Может быть массив
            start = text.find('[')
        
        if start == -1:
            return text  # Возвращаем как есть, пусть JSON парсер разберётся
        
        # Находим соответствующую закрывающую скобку
        end = text.rfind('}')
        if start >= 0 and text[start] == '[':
            end = text.rfind(']')
        
        if end == -1 or end < start:
            return text[start:]  # Возвращаем от начала JSON до конца
        
        return text[start:end + 1]
    
    async def generate_structured_async(
        self,
        prompt: str,
        response_model: Type[T],
        num_predict: int = 1024,
        retries: int = 2
    ) -> T:
        """Асинхронная версия generate_structured.
        
        Args:
            prompt: Текст промпта
            response_model: Pydantic модель
            num_predict: Максимум токенов
            retries: Количество повторов
            
        Returns:
            Провалидированный Pydantic объект
        """
        return await asyncio.to_thread(
            self.generate_structured,
            prompt,
            response_model,
            num_predict,
            retries
        )
    
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
