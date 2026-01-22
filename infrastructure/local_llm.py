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
import threading
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


from dataclasses import dataclass


@dataclass
class StreamChunk:
    """Чанк стриминга от LLM.
    
    Используется для real-time стриминга генерации в UI.
    Позволяет отделять <think> блоки от основного контента.
    
    Attributes:
        content: Текст текущего чанка
        is_thinking: True если чанк находится внутри <think> блока
        is_done: True если это последний чанк
        full_response: Накопленный полный ответ
    """
    content: str
    is_thinking: bool
    is_done: bool
    full_response: str


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
    
    # Общий ThreadPoolExecutor для всех экземпляров класса
    # Используется для выполнения синхронных ollama вызовов с таймаутом
    _executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
    _executor_lock = threading.Lock()
    _executor_max_workers = 10  # Максимум одновременных запросов

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
    
    @classmethod
    def _get_executor(cls) -> concurrent.futures.ThreadPoolExecutor:
        """Возвращает общий ThreadPoolExecutor для класса.
        
        Создаёт executor при первом использовании (ленивая инициализация).
        Потокобезопасен.
        
        Returns:
            ThreadPoolExecutor для выполнения запросов
        """
        if cls._executor is None:
            with cls._executor_lock:
                # Двойная проверка для потокобезопасности
                if cls._executor is None:
                    cls._executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=cls._executor_max_workers,
                        thread_name_prefix="LocalLLM"
                    )
                    logger.debug(f"✅ ThreadPoolExecutor создан ({cls._executor_max_workers} workers)")
        return cls._executor
    
    @classmethod
    def shutdown_executor(cls) -> None:
        """Закрывает общий ThreadPoolExecutor.
        
        Вызывается при graceful shutdown приложения.
        """
        with cls._executor_lock:
            if cls._executor is not None:
                cls._executor.shutdown(wait=True)
                cls._executor = None
                logger.info("✅ ThreadPoolExecutor остановлен")
    
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
                
                # Вызов с timeout через общий ThreadPoolExecutor (работает в любом потоке)
                executor = self._get_executor()
                future = executor.submit(
                    ollama.generate,  # type: ignore[arg-type]
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
                
                # Вызов с timeout через общий ThreadPoolExecutor
                executor = self._get_executor()
                future = executor.submit(
                    ollama.chat,  # type: ignore[arg-type]
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
        Корректно обрабатывает вложенные структуры используя стек.
        
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
        
        # Ищем JSON объект или массив
        start = text.find('{')
        is_array = False
        if start == -1:
            start = text.find('[')
            is_array = True
        
        if start == -1:
            return text  # Возвращаем как есть, пусть JSON парсер разберётся
        
        # Находим соответствующую закрывающую скобку используя стек
        # для корректной обработки вложенных структур
        def find_matching_brace(text: str, start_pos: int, open_char: str, close_char: str) -> int:
            """Находит позицию соответствующей закрывающей скобки.
            
            Args:
                text: Текст для поиска
                start_pos: Позиция открывающей скобки
                open_char: Символ открывающей скобки ('{' или '[')
                close_char: Символ закрывающей скобки ('}' или ']')
                
            Returns:
                Позиция закрывающей скобки или -1 если не найдена
            """
            stack = []
            in_string = False
            escape_next = False
            
            for i in range(start_pos, len(text)):
                char = text[i]
                
                # Обработка escape-последовательностей в строках
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                # Отслеживаем строки (JSON может содержать скобки внутри строк)
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                # Игнорируем скобки внутри строк
                if in_string:
                    continue
                
                # Отслеживаем скобки
                if char == open_char:
                    stack.append(open_char)
                elif char == close_char:
                    if stack:
                        stack.pop()
                        if not stack:
                            return i
            
            return -1
        
        # Находим закрывающую скобку
        open_char = '[' if is_array else '{'
        close_char = ']' if is_array else '}'
        end = find_matching_brace(text, start, open_char, close_char)
        
        if end == -1 or end < start:
            # Если не нашли закрывающую скобку, возвращаем от начала до конца
            return text[start:]
        
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
    
    # === STREAMING МЕТОДЫ ===
    # Real-time стриминг для UI: thinking блоки, генерация кода и т.д.
    
    async def generate_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_predict: int = 4096,
        format: Optional[str] = None,
        **kwargs: Any
    ):
        """Асинхронный стриминг генерации текста.
        
        Использует Ollama streaming API для real-time отдачи чанков.
        Позволяет показывать <think> блоки и код по мере генерации.
        
        Args:
            prompt: Текст промпта
            temperature: Температура генерации
            top_p: Параметр top_p
            num_predict: Максимальное количество токенов
            format: Формат ответа ("json" для JSON)
            **kwargs: Дополнительные параметры
            
        Yields:
            StreamChunk с данными чанка
            
        Example:
            async for chunk in llm.generate_stream(prompt):
                if chunk.is_thinking:
                    yield thinking_event(chunk.content)
                else:
                    yield code_event(chunk.content)
        """
        temp = temperature if temperature is not None else self.temperature
        tp = top_p if top_p is not None else self.top_p
        
        options: Dict[str, Any] = {
            "temperature": temp,
            "top_p": tp,
            "num_predict": num_predict
        }
        options.update(kwargs.get("options", {}))
        
        generate_kwargs = {
            "model": self.model,
            "prompt": prompt,
            "options": options,
            "stream": True  # Включаем стриминг
        }
        
        if format:
            generate_kwargs["format"] = format
        
        for k, v in kwargs.items():
            if k not in ("options", "format"):
                generate_kwargs[k] = v
        
        full_response = ""
        in_thinking = False
        
        try:
            # Ollama streaming API
            # Запускаем в отдельном потоке чтобы не блокировать event loop
            import queue
            import threading
            
            chunk_queue: queue.Queue = queue.Queue()
            error_holder: list = []
            
            def stream_worker():
                try:
                    for chunk in ollama.generate(**generate_kwargs):
                        chunk_queue.put(chunk)
                    chunk_queue.put(None)  # Сигнал завершения
                except Exception as e:
                    error_holder.append(e)
                    chunk_queue.put(None)
            
            thread = threading.Thread(target=stream_worker, daemon=True)
            thread.start()
            
            wait_count = 0
            last_log_time = asyncio.get_event_loop().time()
            
            stream_start_time = time.time()
            max_stream_time = self.timeout * 2  # Максимум 2x timeout для стриминга
            
            while True:
                # Проверяем общий timeout стриминга
                elapsed_stream = time.time() - stream_start_time
                if elapsed_stream > max_stream_time:
                    logger.error(
                        f"❌ Превышен общий timeout стриминга: {elapsed_stream:.1f}с "
                        f"(максимум: {max_stream_time}с)"
                    )
                    # Добавляем ошибку в список (если список пуст, создаём его)
                    if not error_holder:
                        error_holder.append(LLMTimeoutError(
                            f"Превышен общий timeout стриминга: {elapsed_stream:.1f}с"
                        ))
                    else:
                        error_holder[0] = LLMTimeoutError(
                            f"Превышен общий timeout стриминга: {elapsed_stream:.1f}с"
                        )
                    chunk_queue.put(None)  # Сигнал завершения
                    break
                
                try:
                    # Неблокирующее ожидание с таймаутом
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: chunk_queue.get(timeout=0.5)
                    )
                    wait_count = 0  # Reset on successful get
                except queue.Empty:
                    wait_count += 1
                    # Логируем каждые 10 секунд ожидания
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_log_time > 10:
                        elapsed_total = time.time() - stream_start_time
                        logger.info(
                            f"⏳ Ожидаю ответ от LLM... "
                            f"(ожидание: {wait_count * 0.5:.0f}с, всего: {elapsed_total:.0f}с)"
                        )
                        last_log_time = current_time
                    continue
                
                if chunk is None:
                    # Стриминг завершён
                    if error_holder and error_holder[0]:
                        elapsed_total = time.time() - stream_start_time
                        logger.error(
                            f"❌ Ошибка стриминга после {elapsed_total:.1f}с: {error_holder[0]}"
                        )
                        raise error_holder[0]
                    break
                
                content = chunk.get("response", "")
                is_done = chunk.get("done", False)
                
                if content:
                    full_response += content
                    
                    # Определяем находимся ли внутри <think> блока
                    # Простая эвристика: считаем открывающие/закрывающие теги
                    think_opens = full_response.lower().count("<think>")
                    think_closes = full_response.lower().count("</think>")
                    in_thinking = think_opens > think_closes
                    
                    yield StreamChunk(
                        content=content,
                        is_thinking=in_thinking,
                        is_done=is_done,
                        full_response=full_response
                    )
                
                if is_done:
                    break
            
            # Финальный чанк
            if full_response:
                yield StreamChunk(
                    content="",
                    is_thinking=False,
                    is_done=True,
                    full_response=full_response
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга LLM: {e}", error=e)
            # Yield пустой финальный чанк при ошибке
            yield StreamChunk(
                content="",
                is_thinking=False,
                is_done=True,
                full_response=full_response
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
    model: str | None = None,
    temperature: float = 0.25,
    top_p: float = 0.9
) -> LocalLLM:
    """Создаёт LocalLLM с таймаутом, соответствующим этапу workflow.
    
    Args:
        stage: Название этапа (intent, planning, coding, etc.)
        model: Название модели Ollama (None = default)
        temperature: Температура генерации
        top_p: Параметр top_p
        
    Returns:
        LocalLLM с правильным таймаутом для этапа
    """
    from utils.config import get_config
    config = get_config()
    timeout = config.get_stage_timeout(stage)
    
    # Используем дефолтную модель если не указана
    resolved_model = model or "qwen2.5-coder:7b"
    
    return LocalLLM(
        model=resolved_model,
        temperature=temperature,
        top_p=top_p,
        timeout=timeout
    )
