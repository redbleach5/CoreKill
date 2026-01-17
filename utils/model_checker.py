"""Утилита для проверки доступности моделей Ollama."""
import ollama
from typing import List, Optional


def check_model_available(model_name: str) -> bool:
    """Проверяет доступность модели Ollama.
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель доступна, False иначе
    """
    try:
        models = ollama.list()
        model_names = [model.get("name", "") for model in models.get("models", [])]
        return model_name in model_names
    except Exception:
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
    
    Ищет модели с ключевыми словами: phi, tiny, mini
    
    Returns:
        Название легкой модели или None если ничего не найдено
    """
    all_models = get_all_available_models()
    if not all_models:
        return None
    
    # Ищем легкие модели
    light_keywords = ['phi', 'tiny', 'mini']
    for model in all_models:
        model_lower = model.lower()
        if any(keyword in model_lower for keyword in light_keywords):
            return model
    
    # Если легких нет, возвращаем первую доступную
    return all_models[0]


def get_all_available_models() -> List[str]:
    """Возвращает список всех доступных моделей Ollama.
    
    Returns:
        Список названий доступных моделей
    """
    try:
        models = ollama.list()
        model_names = [
            model.get("name", "") 
            for model in models.get("models", []) 
            if model.get("name")
        ]
        return sorted(model_names)
    except Exception:
        return []
