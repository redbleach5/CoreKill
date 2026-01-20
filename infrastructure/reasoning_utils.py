"""Утилиты для работы с reasoning моделями (DeepSeek-R1, QwQ, o1).

Reasoning модели имеют встроенный chain-of-thought (CoT) и возвращают
рассуждения в <think> блоках. Этот модуль обеспечивает:
- Парсинг <think> блоков
- Извлечение финального ответа
- Логирование рассуждений для отладки
"""
import re
from dataclasses import dataclass
from typing import Optional

from utils.logger import get_logger

logger = get_logger()


@dataclass
class ReasoningResponse:
    """Ответ reasoning модели с разделением на части.
    
    Attributes:
        thinking: Содержимое <think> блока (рассуждения модели)
        answer: Финальный ответ (после </think>)
        raw: Полный исходный ответ
        has_thinking: Был ли <think> блок в ответе
    """
    thinking: str
    answer: str
    raw: str
    has_thinking: bool = False
    
    @property
    def thinking_lines(self) -> int:
        """Количество строк в рассуждениях."""
        if not self.thinking:
            return 0
        return len(self.thinking.split('\n'))
    
    @property
    def answer_lines(self) -> int:
        """Количество строк в ответе."""
        if not self.answer:
            return 0
        return len(self.answer.split('\n'))


# Паттерн для <think> блока (поддерживает разные варианты)
_THINK_PATTERNS = [
    # Стандартный формат DeepSeek-R1
    r'<think>(.*?)</think>',
    # Альтернативные теги
    r'<thinking>(.*?)</thinking>',
    r'<thought>(.*?)</thought>',
    # С атрибутами (на всякий случай)
    r'<think[^>]*>(.*?)</think>',
]


def parse_reasoning_response(response: str) -> ReasoningResponse:
    """Парсит ответ reasoning модели, разделяя <think> и финальный ответ.
    
    Reasoning модели (DeepSeek-R1, QwQ) возвращают ответ в формате:
    
    ```
    <think>
    Анализирую задачу...
    Шаг 1: ...
    Шаг 2: ...
    </think>
    
    Финальный ответ здесь.
    ```
    
    Args:
        response: Полный ответ модели
        
    Returns:
        ReasoningResponse с разделёнными thinking и answer
        
    Example:
        >>> resp = parse_reasoning_response('''<think>
        ... Думаю над задачей...
        ... </think>
        ... 
        ... def hello(): pass''')
        >>> resp.thinking
        'Думаю над задачей...'
        >>> resp.answer
        'def hello(): pass'
    """
    if not response:
        return ReasoningResponse(
            thinking="",
            answer="",
            raw="",
            has_thinking=False
        )
    
    response = response.strip()
    
    # Пробуем разные паттерны
    for pattern in _THINK_PATTERNS:
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            thinking = match.group(1).strip()
            
            # Убираем <think> блок из ответа
            answer = re.sub(pattern, '', response, flags=re.DOTALL | re.IGNORECASE).strip()
            
            # Логируем для отладки (только первые 200 символов)
            if thinking:
                preview = thinking[:200] + ('...' if len(thinking) > 200 else '')
                logger.debug(f"🧠 Reasoning ({len(thinking)} символов): {preview}")
            
            return ReasoningResponse(
                thinking=thinking,
                answer=answer,
                raw=response,
                has_thinking=True
            )
    
    # <think> блок не найден — возвращаем всё как answer
    return ReasoningResponse(
        thinking="",
        answer=response,
        raw=response,
        has_thinking=False
    )


def extract_answer_only(response: str) -> str:
    """Извлекает только финальный ответ, убирая <think> блоки.
    
    Удобная функция для случаев, когда рассуждения не нужны.
    
    Args:
        response: Полный ответ модели
        
    Returns:
        Ответ без <think> блоков
    """
    return parse_reasoning_response(response).answer


def extract_code_from_reasoning(response: str) -> str:
    """Извлекает код из ответа reasoning модели.
    
    1. Убирает <think> блоки
    2. Извлекает код из markdown блоков (```python ... ```)
    3. Если нет markdown — возвращает весь ответ
    
    Args:
        response: Полный ответ модели
        
    Returns:
        Извлечённый код
    """
    # Сначала убираем <think>
    answer = extract_answer_only(response)
    
    if not answer:
        return ""
    
    # Пробуем извлечь код из markdown блоков
    code_patterns = [
        r'```python\n(.*?)```',
        r'```py\n(.*?)```',
        r'```\n(.*?)```',
    ]
    
    for pattern in code_patterns:
        match = re.search(pattern, answer, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Если нет markdown блоков — возвращаем весь ответ
    return answer.strip()


def format_thinking_for_log(thinking: str, max_lines: int = 10) -> str:
    """Форматирует рассуждения для логирования.
    
    Args:
        thinking: Текст рассуждений
        max_lines: Максимум строк для вывода
        
    Returns:
        Отформатированный текст с ограничением строк
    """
    if not thinking:
        return "(пусто)"
    
    lines = thinking.split('\n')
    if len(lines) <= max_lines:
        return thinking
    
    # Показываем первые и последние строки
    half = max_lines // 2
    first_lines = lines[:half]
    last_lines = lines[-half:]
    
    return '\n'.join(first_lines) + f'\n... ({len(lines) - max_lines} строк скрыто) ...\n' + '\n'.join(last_lines)


def is_reasoning_response(response: str) -> bool:
    """Проверяет, содержит ли ответ <think> блок.
    
    Args:
        response: Ответ модели
        
    Returns:
        True если есть <think> блок
    """
    if not response:
        return False
    
    response_lower = response.lower()
    return '<think>' in response_lower or '<thinking>' in response_lower


def get_thinking_summary(thinking: str, max_length: int = 100) -> str:
    """Возвращает краткую сводку рассуждений.
    
    Args:
        thinking: Полный текст рассуждений
        max_length: Максимальная длина сводки
        
    Returns:
        Краткая сводка
    """
    if not thinking:
        return ""
    
    # Берём первое предложение или первые N символов
    first_sentence = thinking.split('.')[0]
    if len(first_sentence) <= max_length:
        return first_sentence + '.'
    
    return thinking[:max_length].rsplit(' ', 1)[0] + '...'
