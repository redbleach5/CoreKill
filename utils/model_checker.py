"""Утилита для проверки доступности моделей Ollama."""
import ollama
from typing import List, Optional
from utils.logger import get_logger

logger = get_logger()


def check_ollama_api_available() -> bool:
    """Проверяет доступность Ollama API.
    
    Returns:
        True если Ollama API доступен, False иначе
    """
    try:
        # Простой ping к Ollama API
        ollama.list()
        return True
    except Exception as e:
        logger.debug(f"Ollama API недоступен: {e}")
        return False


def check_model_available(model_name: str) -> bool:
    """Проверяет доступность модели Ollama.
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель доступна, False иначе
    """
    # Сначала проверяем доступность Ollama API
    if not check_ollama_api_available():
        return False
    
    try:
        models = ollama.list()
        model_names = [
            model.model if hasattr(model, 'model') else getattr(model, 'name', '')
            for model in models.models if hasattr(models, 'models')
        ] if hasattr(models, 'models') else []
        return model_name in model_names
    except Exception as e:
        logger.debug(f"Ошибка проверки модели {model_name}: {e}")
        return False


def get_available_model(preferred: str, fallbacks: List[str]) -> Optional[str]:
    """Возвращает первую доступную модель из списка.
    
    Args:
        preferred: Предпочтительная модель
        fallbacks: Список альтернативных моделей
        
    Returns:
        Название доступной модели или None если ничего не найдено
    """
    if check_model_available(preferred):
        return preferred
    
    for fallback in fallbacks:
        if check_model_available(fallback):
            return fallback
    
    return None


def get_any_available_model() -> Optional[str]:
    """Возвращает любую доступную модель Ollama.
    
    Returns:
        Название доступной модели или None если ничего не найдено
    """
    all_models = get_all_available_models()
    if all_models:
        return all_models[0]
    return None


def get_light_model() -> Optional[str]:
    """Возвращает легкую модель для быстрых операций (intent, planning).
    
    Приоритет:
    1. qwen2.5-coder:1.5b (лучший баланс скорость/качество для кода)
    2. Модели с 1b, 1.5b, 3b в названии
    3. Модели с phi, tiny, mini, gemma в названии
    
    Returns:
        Название легкой модели или None если ничего не найдено
    """
    all_models = get_all_available_models()
    if not all_models:
        return None
    
    # Приоритетные быстрые модели для кода
    priority_models = [
        'qwen2.5-coder:1.5b',
        'gemma3:1b', 
        'phi3:mini',
        'llama3.2:3b',
        'gemma3:4b',
        'stable-code:latest',
    ]
    
    for priority in priority_models:
        if priority in all_models:
            return priority
    
    # Ищем по ключевым словам размера
    size_keywords = ['1.5b', ':1b', ':3b', ':4b']
    for model in all_models:
        model_lower = model.lower()
        if any(keyword in model_lower for keyword in size_keywords):
            # Избегаем embed моделей
            if 'embed' not in model_lower:
                return model
    
    # Ищем легкие модели по названию
    light_keywords = ['phi', 'tiny', 'mini', 'gemma']
    for model in all_models:
        model_lower = model.lower()
        if any(keyword in model_lower for keyword in light_keywords):
            if 'embed' not in model_lower:
                return model
    
    # Если легких нет, возвращаем первую НЕ-embed модель
    for model in all_models:
        if 'embed' not in model.lower():
            return model
    
    return all_models[0] if all_models else None


def get_coder_model() -> Optional[str]:
    """Возвращает модель оптимизированную для генерации кода.
    
    Приоритет:
    1. qwen2.5-coder (лучшая для кода)
    2. deepseek-coder
    3. codellama
    4. stable-code
    5. Любая другая
    
    Returns:
        Название модели для кода или None
    """
    all_models = get_all_available_models()
    if not all_models:
        return None
    
    # Приоритетные модели для кода (от лёгких к тяжёлым)
    priority_models = [
        'qwen2.5-coder:1.5b',  # Быстрая и качественная
        'qwen2.5-coder:7b',    # Качественная но медленнее
        'deepseek-coder:6.7b',
        'stable-code:latest',
        'codellama:7b',
    ]
    
    for priority in priority_models:
        if priority in all_models:
            return priority
    
    # Ищем любую coder модель
    for model in all_models:
        if 'coder' in model.lower() or 'code' in model.lower():
            if 'embed' not in model.lower():
                return model
    
    # Возвращаем лёгкую модель как fallback
    return get_light_model()


def get_all_available_models() -> List[str]:
    """Возвращает список всех доступных моделей Ollama.
    
    Returns:
        Список названий доступных моделей
    """
    # Сначала проверяем доступность Ollama API
    if not check_ollama_api_available():
        logger.warning("⚠️ Ollama API недоступен, не могу получить список моделей")
        return []
    
    try:
        models = ollama.list()
        model_names = []
        if hasattr(models, 'models'):
            for model in models.models:
                # Ollama возвращает объекты Model с атрибутом 'model'
                model_name = model.model if hasattr(model, 'model') else getattr(model, 'name', '')
                if model_name:
                    model_names.append(model_name)
        return sorted(model_names)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения списка моделей: {e}")
        return []
