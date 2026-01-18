"""Обёртка для работы с локальными LLM через Ollama."""
import ollama
from typing import Optional, Dict, Any
import time

from utils.logger import get_logger


logger = get_logger()


class LocalLLM:
    """Класс для работы с локальными моделями через Ollama API.
    
    Поддерживает retry, настройку параметров генерации и обработку ошибок.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.25,
        top_p: float = 0.9,
        timeout: int = 300,
        max_retries: int = 2
    ) -> None:
        """Инициализация LocalLLM.
        
        Args:
            model: Название модели Ollama
            temperature: Температура генерации (0.15-0.35 по правилам)
            top_p: Параметр top_p для генерации
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторных попыток
        """
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout
        self.max_retries = max_retries

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
                
                # Прямой вызов без дополнительных потоков/таймаутов
                # Ollama сам обрабатывает таймауты на уровне HTTP
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                    options=options,
                    **{k: v for k, v in kwargs.items() if k != "options"}
                )
                
                result = response.get("response", "").strip()
                if result:
                    return result
                    
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1)
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
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options=options,
                    **{k: v for k, v in kwargs.items() if k != "options"}
                )
                
                result = response.get("message", {}).get("content", "").strip()
                if result:
                    return result
                    
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                else:
                    break
        
        error_msg = f"Ошибка Ollama chat после {self.max_retries + 1} попыток: {last_error}"
        logger.error(f"❌ {error_msg}", error=last_error)
        return ""
