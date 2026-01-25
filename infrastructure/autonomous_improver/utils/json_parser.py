"""Утилиты для парсинга JSON из ответов LLM."""
import json
import re
from typing import Optional, Dict, Any, List


def extract_json_from_markdown(text: str) -> Optional[str]:
    """Извлекает JSON из markdown блоков кода.
    
    Args:
        text: Текст с возможным JSON в markdown
        
    Returns:
        JSON строка или None
    """
    # Ищем JSON в markdown блоках ```json или ```
    patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'```\s*(.*?)\s*```',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            match = match.strip()
            if match.startswith('{') or match.startswith('['):
                return match
    
    # Если не нашли в markdown, ищем просто JSON объект/массив
    json_pattern = r'(\{.*\}|\[.*\])'
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        match = match.strip()
        if match.startswith('{') or match.startswith('['):
            return match
    
    return None


def fix_common_json_errors(json_str: str) -> str:
    """Исправляет частые ошибки в JSON.
    
    Args:
        json_str: JSON строка с возможными ошибками
        
    Returns:
        Исправленная JSON строка
    """
    # Убираем trailing commas
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Исправляем одинарные кавычки на двойные (в значениях строк)
    # Но осторожно - не трогаем уже правильные двойные кавычки
    json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    
    # Убираем комментарии (не поддерживаются в JSON)
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    return json_str


def parse_llm_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Парсит JSON из ответа LLM с обработкой ошибок.
    
    Пытается:
    1. Извлечь JSON из markdown
    2. Исправить частые ошибки
    3. Распарсить JSON
    
    Args:
        text: Ответ от LLM
        
    Returns:
        Распарсенный JSON или None
    """
    # Шаг 1: Извлекаем JSON из markdown
    json_str = extract_json_from_markdown(text)
    if not json_str:
        # Пробуем весь текст как JSON
        json_str = text.strip()
    
    # Шаг 2: Исправляем частые ошибки
    json_str = fix_common_json_errors(json_str)
    
    # Шаг 3: Парсим JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Логируем ошибку для отладки
        import logging
        logger = logging.getLogger("autonomous_improver")
        logger.debug(f"JSON parse error: {e}, text: {json_str[:200]}")
        return None


def extract_suggestions_with_fallback(text: str) -> List[Dict[str, Any]]:
    """Извлекает предложения из ответа LLM с fallback на regex.
    
    Args:
        text: Ответ от LLM
        
    Returns:
        Список предложений
    """
    # Пробуем нормальный парсинг
    parsed = parse_llm_json_response(text)
    if parsed and 'suggestions' in parsed:
        return parsed['suggestions']
    
    # Fallback: regex парсинг для критичных полей
    suggestions = []
    
    # Ищем паттерны типа "type": "code_quality"
    type_pattern = r'"type"\s*:\s*"([^"]+)"'
    description_pattern = r'"description"\s*:\s*"([^"]+)"'
    confidence_pattern = r'"confidence"\s*:\s*([0-9.]+)'
    
    types = re.findall(type_pattern, text)
    descriptions = re.findall(description_pattern, text)
    confidences = re.findall(confidence_pattern, text)
    
    # Создаём предложения из найденных полей
    max_len = max(len(types), len(descriptions), len(confidences))
    for i in range(max_len):
        suggestion = {}
        if i < len(types):
            suggestion['type'] = types[i]
        if i < len(descriptions):
            suggestion['description'] = descriptions[i]
        if i < len(confidences):
            suggestion['confidence'] = float(confidences[i])
        
        if suggestion:
            suggestions.append(suggestion)
    
    return suggestions
