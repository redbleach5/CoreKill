"""Утилита для приблизительного подсчёта токенов."""
from typing import List, Dict, Any


def estimate_tokens(text: str) -> int:
    """Приблизительно оценивает количество токенов в тексте.
    
    Используется простое правило: 1 токен ≈ 4 символа для английского/кода,
    или 1.5 токена на слово.
    
    Args:
        text: Текст для оценки
        
    Returns:
        Приблизительное количество токенов
    """
    if not text:
        return 0
    
    # Простая оценка: считаем слова и умножаем на 1.5
    # Альтернатива: делим длину на 4
    word_count = len(text.split())
    char_estimate = len(text) / 4
    word_estimate = word_count * 1.5
    
    # Берём среднее значение для более точной оценки
    estimated = int((char_estimate + word_estimate) / 2)
    return estimated


def estimate_workflow_tokens(
    task: str,
    plan: str,
    context: str,
    tests: str,
    code: str,
    prompts_used: List[str]
) -> int:
    """Оценивает общее количество токенов использованных в workflow.
    
    Args:
        task: Текст задачи
        plan: План выполнения
        context: Собранный контекст
        tests: Сгенерированные тесты
        code: Сгенерированный код
        prompts_used: Список промптов которые были использованы
        
    Returns:
        Общая оценка токенов
    """
    total = 0
    
    total += estimate_tokens(task)
    total += estimate_tokens(plan)
    total += estimate_tokens(context)
    total += estimate_tokens(tests)
    total += estimate_tokens(code)
    
    for prompt in prompts_used:
        total += estimate_tokens(prompt)
    
    # Добавляем накладные расходы на генерацию (output обычно в 1-2 раза больше промпта)
    # Для кода и тестов добавляем множитель
    total += estimate_tokens(code) * 0.5  # Генерация кода
    total += estimate_tokens(tests) * 0.5  # Генерация тестов
    
    return int(total)


def check_token_limit(
    current_tokens: int,
    warning_threshold: int = 30000,
    max_tokens: int = 50000
) -> Dict[str, Any]:
    """Проверяет превышение лимитов токенов.
    
    Args:
        current_tokens: Текущее количество токенов
        warning_threshold: Порог для предупреждения
        max_tokens: Максимальное количество токенов
        
    Returns:
        Словарь с информацией о статусе:
        {
            "within_limit": bool,
            "warning": bool,
            "message": str,
            "tokens": int
        }
    """
    result: Dict[str, Any] = {
        "tokens": current_tokens,
        "within_limit": True,
        "warning": False,
        "message": ""
    }
    
    if current_tokens >= max_tokens:
        result["within_limit"] = False
        result["warning"] = True
        result["message"] = f"⚠️ Превышен максимальный лимит токенов: {current_tokens} >= {max_tokens}"
    elif current_tokens >= warning_threshold:
        result["warning"] = True
        result["message"] = f"⚠️ Приближение к лимиту токенов: {current_tokens} / {max_tokens}"
    
    return result
