"""Утилиты для работы с типами intent (намерений).

Устраняет дублирование словарей intent_descriptions в разных модулях.
Предоставляет единый источник истины для описаний типов намерений.

Примеры использования:
    ```python
    from utils.intent_helpers import get_intent_description, get_all_intent_types
    
    # Получить описание типа intent
    short_desc = get_intent_description("create", "short")
    # "создать новую функцию/класс/модуль"
    
    long_desc = get_intent_description("create", "long")
    # "создание нового кода/функции/класса/модуля"
    
    planning_desc = get_intent_description("create", "planning")
    # "создание нового кода/функции/класса/модуля"
    
    # Получить все доступные типы
    all_types = get_all_intent_types()
    # ["create", "modify", "debug", "optimize", ...]
    ```

Зависимости:
    - typing: для типизации

Связанные утилиты:
    - agents.intent: использует для описаний типов намерений

Примечания:
    - Поддерживает форматы: "short", "long", "planning"
    - Все описания на русском языке
    - Централизованное хранение предотвращает дублирование
"""
from typing import Dict, Literal

# Описания типов intent для разных контекстов
INTENT_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "create": {
        "short": "создать новую функцию/класс/модуль",
        "long": "создание нового кода/функции/класса/модуля",
        "planning": "создание нового кода/функции/класса/модуля"
    },
    "modify": {
        "short": "изменить существующий код",
        "long": "изменение существующего кода",
        "planning": "изменение существующего кода"
    },
    "debug": {
        "short": "исправить ошибки в коде",
        "long": "поиск и исправление ошибок",
        "planning": "поиск и исправление ошибок"
    },
    "optimize": {
        "short": "оптимизировать производительность кода",
        "long": "оптимизация производительности или качества",
        "planning": "оптимизация производительности или качества"
    },
    "explain": {
        "short": "объяснить код (генерация документации)",
        "long": "объяснение кода",
        "planning": "объяснение кода"
    },
    "test": {
        "short": "написать тесты (но тесты уже есть, нужно реализовать тестируемый код)",
        "long": "написание тестов",
        "planning": "написание тестов"
    },
    "refactor": {
        "short": "рефакторинг кода без изменения функциональности",
        "long": "рефакторинг кода без изменения функциональности",
        "planning": "рефакторинг кода без изменения функциональности"
    },
    "greeting": {
        "short": "приветствие",
        "long": "приветствие пользователя",
        "planning": "приветствие"
    },
    "help": {
        "short": "помощь",
        "long": "запрос помощи",
        "planning": "запрос помощи"
    },
    "chat": {
        "short": "диалог",
        "long": "диалог с пользователем",
        "planning": "диалог"
    },
    "analyze": {
        "short": "анализ проекта",
        "long": "анализ структуры проекта",
        "planning": "анализ структуры проекта"
    }
}


def get_intent_description(
    intent_type: str,
    format: Literal["short", "long", "planning"] = "short"
) -> str:
    """Возвращает описание типа intent.
    
    Args:
        intent_type: Тип намерения (create, modify, debug, etc.)
        format: Формат описания:
            - "short": краткое описание (для промптов генерации кода)
            - "long": полное описание (для промптов планирования)
            - "planning": описание для планирования (аналогично long)
            
    Returns:
        Описание intent типа или пустая строка если не найдено
        
    Example:
        >>> get_intent_description("create", "short")
        "создать новую функцию/класс/модуль"
        >>> get_intent_description("create", "planning")
        "создание нового кода/функции/класса/модуля"
    """
    intent_data = INTENT_DESCRIPTIONS.get(intent_type, {})
    return intent_data.get(format, intent_data.get("short", ""))


def get_all_intent_types() -> list[str]:
    """Возвращает список всех доступных типов intent.
    
    Returns:
        Список типов intent
    """
    return list(INTENT_DESCRIPTIONS.keys())
