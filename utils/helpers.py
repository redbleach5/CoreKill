"""Вспомогательные функции для устранения дублирования кода.

Содержит общие функции, которые используются в разных модулях проекта.
"""
from typing import List


def detect_language(text: str) -> str:
    """Определяет язык текста.
    
    Простая эвристика на основе наличия кириллических символов.
    
    Args:
        text: Текст для анализа
        
    Returns:
        'ru' если обнаружена кириллица, 'en' иначе
    """
    if not text:
        return "en"
    
    # Проверяем наличие кириллических символов
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    
    # Если есть кириллица - русский, иначе английский
    return "ru" if has_cyrillic else "en"


def is_greeting(text: str) -> bool:
    """Проверяет, является ли текст приветствием.
    
    Args:
        text: Текст для проверки
        
    Returns:
        True если это приветствие, False иначе
    """
    if not text:
        return False
    
    text_lower = text.strip().lower()
    
    # Список приветствий на русском и английском
    greetings = [
        "привет", "здравствуй", "здравствуйте", "добрый день",
        "добрый вечер", "доброе утро", "доброй ночи", "хай", "хей", "салют",
        "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
        "good evening", "good night", "howdy", "sup"
    ]
    
    # Проверяем точное совпадение или начало фразы
    is_greeting_text = any(
        text_lower == greeting or text_lower.startswith(greeting + " ")
        for greeting in greetings
    )
    
    # Если короткий текст и похож на приветствие
    if len(text_lower.split()) <= 3 and is_greeting_text:
        return True
    
    # Для более длинных текстов проверяем, нет ли ключевых слов кода
    if len(text_lower.split()) > 3:
        code_keywords = ["def ", "class ", "import ", "function", "code", "напиши", "создай"]
        has_code_keywords = any(keyword in text_lower for keyword in code_keywords)
        if has_code_keywords:
            return False
    
    return is_greeting_text
