"""Обёртка для работы с локальными LLM через Ollama."""
import ollama
from typing import Optional, Dict, Any
import time
import signal
from contextlib import contextmanager

from utils.logger import get_logger


logger = get_logger()


class TimeoutError(Exception):
    """Исключение для таймаута LLM запроса."""
    pass


@contextmanager
def timeout_handler(seconds: int, operation: str = "LLM request"):
    """Контекстный менеджер для timeout операций.
    
    Args:
        seconds: Таймаут в секундах
        operation: Описание операции для логирования
        
    Raises:
        TimeoutError: Если операция превысила таймаут
    """
    def handler(signum: int, frame: Any) -> None:
        raise TimeoutError(f"{operation} превысил таймаут {seconds} секунд")
    
    # Устанавливаем обработчик сигнала
    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Восстанавливаем предыдущий обработчик
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


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
                
                # Вызов с timeout (через signal на Unix)
                try:
                    with timeout_handler(self.timeout, f"Ollama generate ({self.model})"):
                        response = ollama.generate(
                            model=self.model,
                            prompt=prompt,
                            options=options,
                            **{k: v for k, v in kwargs.items() if k != "options"}
                        )
                except TimeoutError as te:
                    elapsed = time.time() - start_time
                    logger.warning(f"⏱️ Таймаут LLM запроса после {elapsed:.1f}с: {te}")
                    raise
                
                elapsed = time.time() - start_time
                result = response.get("response", "").strip()
                
                if result:
                    logger.debug(f"✅ LLM ответ получен за {elapsed:.1f}с ({len(result)} символов)")
                    return result
                else:
                    logger.warning(f"⚠️ Пустой ответ от LLM после {elapsed:.1f}с")
                    
            except TimeoutError:
                last_error = TimeoutError(f"Таймаут {self.timeout}с")
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
                
                try:
                    with timeout_handler(self.timeout, f"Ollama chat ({self.model})"):
                        response = ollama.chat(
                            model=self.model,
                            messages=messages,
                            options=options,
                            **{k: v for k, v in kwargs.items() if k != "options"}
                        )
                except TimeoutError as te:
                    elapsed = time.time() - start_time
                    logger.warning(f"⏱️ Таймаут chat запроса после {elapsed:.1f}с: {te}")
                    raise
                
                result = response.get("message", {}).get("content", "").strip()
                if result:
                    return result
                    
            except TimeoutError:
                last_error = TimeoutError(f"Таймаут {self.timeout}с")
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
