"""Утилиты для работы со structured output.

Предоставляет:
- Единую точку входа для generate_structured с fallback
- Feature flag проверку из config.toml
- Логирование и метрики

Примеры использования:
    ```python
    from utils.structured_helpers import generate_with_fallback
    from models.agent_responses import IntentResponse
    
    # Синхронная версия
    response = generate_with_fallback(
        llm=self.llm,
        prompt=prompt,
        response_model=IntentResponse,
        fallback_fn=lambda: self._classify_legacy(query),
        agent_name="intent"
    )
    
    # Асинхронная версия
    from utils.structured_helpers import generate_with_fallback_async
    
    response = await generate_with_fallback_async(
        llm=self.llm,
        prompt=prompt,
        response_model=IntentResponse,
        fallback_fn=lambda: self._classify_legacy(query),
        agent_name="intent"
    )
    
    # Проверка включён ли structured output
    from utils.structured_helpers import is_structured_output_enabled
    
    if is_structured_output_enabled("intent"):
        print("Structured output включён для intent агента")
    ```

Зависимости:
    - pydantic: для валидации structured output
    - infrastructure.local_llm: для генерации
    - utils.logger: для логирования
    - utils.config: для feature flags

Связанные утилиты:
    - agents.intent: использует для structured output
    - agents.debugger: использует для structured output
    - agents.reflection: использует для structured output

Примечания:
    - Автоматически проверяет feature flag из config.toml
    - При ошибке structured output использует fallback функцию
    - Fallback можно отключить в config.toml (fallback_to_manual_parsing)
"""
from typing import TypeVar, Type, Callable, Optional, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from infrastructure.local_llm import LocalLLM

from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()

T = TypeVar('T', bound=BaseModel)


def is_structured_output_enabled(agent_name: str) -> bool:
    """Проверяет, включён ли structured output для агента.
    
    Args:
        agent_name: Название агента (intent, planner, debugger, etc.)
        
    Returns:
        True если structured output включён для этого агента
    """
    try:
        config = get_config()
        structured_config = config._config_data.get("structured_output", {})
        
        # Проверяем глобальный флаг
        if not structured_config.get("enabled", True):
            return False
        
        # Проверяем список включённых агентов
        enabled_agents = structured_config.get("enabled_agents", [])
        return agent_name in enabled_agents
    except Exception as e:
        logger.debug(f"⚠️ Ошибка проверки enabled_agents для {agent_name}: {e}")
        return False


def generate_with_fallback(
    llm: 'LocalLLM',
    prompt: str,
    response_model: Type[T],
    fallback_fn: Callable[[], T],
    agent_name: str,
    num_predict: int = 1024,
    retries: int = 2
) -> T:
    """Генерирует structured output с fallback на legacy парсинг.
    
    Логика:
    1. Проверяет включён ли structured output для агента
    2. Если да — использует generate_structured()
    3. При ошибке — вызывает fallback функцию
    
    Args:
        llm: LocalLLM инстанс
        prompt: Промпт для генерации
        response_model: Pydantic модель для ответа
        fallback_fn: Функция для fallback (возвращает тот же тип)
        agent_name: Название агента для feature flag
        num_predict: Максимум токенов
        retries: Количество повторов при ошибке
        
    Returns:
        Pydantic модель или результат fallback
        
    Example:
        response = generate_with_fallback(
            llm=self.llm,
            prompt=prompt,
            response_model=IntentResponse,
            fallback_fn=lambda: self._legacy_parse(query),
            agent_name="intent"
        )
    """
    from infrastructure.local_llm import StructuredOutputError
    
    # Проверяем feature flag
    if not is_structured_output_enabled(agent_name):
        logger.debug(f"📦 Structured output отключён для {agent_name}, используем fallback")
        return fallback_fn()
    
    try:
        logger.debug(f"📦 Используем structured output для {agent_name}")
        result = llm.generate_structured(
            prompt=prompt,
            response_model=response_model,
            num_predict=num_predict,
            retries=retries
        )
        logger.info(f"✅ Structured output успешен для {agent_name}")
        return result
        
    except StructuredOutputError as e:
        # Проверяем разрешён ли fallback
        config = get_config()
        structured_config = config._config_data.get("structured_output", {})
        allow_fallback = structured_config.get("fallback_to_manual_parsing", True)
        
        if allow_fallback:
            logger.warning(
                f"⚠️ Structured output failed для {agent_name}: {e}, используем fallback"
            )
            return fallback_fn()
        else:
            logger.error(f"❌ Structured output failed для {agent_name}: {e}")
            raise


async def generate_with_fallback_async(
    llm: 'LocalLLM',
    prompt: str,
    response_model: Type[T],
    fallback_fn: Callable[[], T],
    agent_name: str,
    num_predict: int = 1024,
    retries: int = 2
) -> T:
    """Асинхронная версия generate_with_fallback.
    
    Args:
        llm: LocalLLM инстанс
        prompt: Промпт для генерации
        response_model: Pydantic модель для ответа
        fallback_fn: Функция для fallback (может быть sync или async)
        agent_name: Название агента для feature flag
        num_predict: Максимум токенов
        retries: Количество повторов при ошибке
        
    Returns:
        Pydantic модель или результат fallback
    """
    import asyncio
    from infrastructure.local_llm import StructuredOutputError
    
    # Проверяем feature flag
    if not is_structured_output_enabled(agent_name):
        logger.debug(f"📦 Structured output отключён для {agent_name}, используем fallback")
        result = fallback_fn()
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    try:
        logger.debug(f"📦 Используем structured output для {agent_name}")
        result = await llm.generate_structured_async(
            prompt=prompt,
            response_model=response_model,
            num_predict=num_predict,
            retries=retries
        )
        logger.info(f"✅ Structured output успешен для {agent_name}")
        return result
        
    except StructuredOutputError as e:
        # Проверяем разрешён ли fallback
        config = get_config()
        structured_config = config._config_data.get("structured_output", {})
        allow_fallback = structured_config.get("fallback_to_manual_parsing", True)
        
        if allow_fallback:
            logger.warning(
                f"⚠️ Structured output failed для {agent_name}: {e}, используем fallback"
            )
            result = fallback_fn()
            if asyncio.iscoroutine(result):
                return await result
            return result
        else:
            logger.error(f"❌ Structured output failed для {agent_name}: {e}")
            raise
