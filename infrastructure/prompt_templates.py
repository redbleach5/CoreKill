"""Централизованные шаблоны промптов для агентов.

Устраняет дублирование общих паттернов в промптах разных агентов.
Содержит:
- Общие секции промптов
- Утилиты для форматирования
- Базовые шаблоны
"""
from typing import Optional, Dict, Any, List
from utils.intent_helpers import get_intent_description
from utils.logger import get_logger

logger = get_logger()


class PromptTemplates:
    """Централизованные шаблоны промптов."""
    
    @staticmethod
    def format_context_section(context: str, title: str = "Контекст") -> str:
        """Форматирует секцию контекста.
        
        Args:
            context: Текст контекста
            title: Заголовок секции
            
        Returns:
            Отформатированная секция или пустая строка
        """
        if not context or not context.strip():
            return ""
        return f"""
{title}:
{context}
"""
    
    @staticmethod
    def format_code_section(code: str, language: str = "python", max_length: int = 1500) -> str:
        """Форматирует секцию кода.
        
        Args:
            code: Код для отображения
            language: Язык кода (для markdown)
            max_length: Максимальная длина кода
            
        Returns:
            Отформатированная секция кода
        """
        if not code:
            return ""
        
        truncated = code[:max_length] if len(code) > max_length else code
        return f"```{language}\n{truncated}\n```"
    
    @staticmethod
    def format_errors_section(error_details: Dict[str, str]) -> str:
        """Форматирует секцию ошибок валидации.
        
        Args:
            error_details: Словарь с деталями ошибок (pytest, mypy, bandit)
            
        Returns:
            Отформатированная секция ошибок
        """
        error_sections: List[str] = []
        
        if error_details.get("pytest"):
            error_sections.append(f"pytest ошибки:\n{error_details['pytest']}")
        if error_details.get("mypy"):
            error_sections.append(f"mypy ошибки:\n{error_details['mypy']}")
        if error_details.get("bandit"):
            error_sections.append(f"bandit проблемы:\n{error_details['bandit']}")
        
        if not error_sections:
            return ""
        
        return "\n\n".join(error_sections)
    
    @staticmethod
    def format_validation_summary(validation_results: Dict[str, Any]) -> str:
        """Форматирует сводку результатов валидации.
        
        Args:
            validation_results: Результаты валидации
            
        Returns:
            Отформатированная сводка
        """
        pytest_status = "✅ ПРОЙДЕН" if validation_results.get('pytest', {}).get('success') else "❌ НЕ ПРОЙДЕН"
        mypy_status = "✅ ПРОЙДЕН" if validation_results.get('mypy', {}).get('success') else "❌ НЕ ПРОЙДЕН"
        bandit_status = "✅ ПРОЙДЕН" if validation_results.get('bandit', {}).get('success') else "❌ НЕ ПРОЙДЕН"
        
        return f"""
Результаты валидации:
- pytest: {pytest_status}
- mypy: {mypy_status}
- bandit: {bandit_status}
"""
    
    @staticmethod
    def build_planning_prompt(
        task: str,
        intent_type: str,
        context: str = "",
        memory_recommendations: str = "",
        alternatives_count: int = 2
    ) -> str:
        """Строит промпт для планирования.
        
        Args:
            task: Текст задачи
            intent_type: Тип намерения
            context: Контекст из RAG
            memory_recommendations: Рекомендации из памяти
            alternatives_count: Количество альтернативных подходов
            
        Returns:
            Промпт для планирования
        """
        intent_desc = get_intent_description(intent_type, format="planning") or "выполнение задачи"
        
        context_section = PromptTemplates.format_context_section(context, "Контекст")
        memory_section = PromptTemplates.format_context_section(
            memory_recommendations,
            "Рекомендации из памяти прошлых задач"
        ) if memory_recommendations else ""
        
        # Инструкции для reasoning моделей
        thinking_instructions = """
ВАЖНО для reasoning моделей (DeepSeek-R1, QwQ и т.д.):
Если твоя модель поддерживает <think> блоки, используй их для детального описания процесса планирования:

<think>
Детально опиши:
1. Как анализируешь задачу - что в ней важно, какие требования
2. Какие файлы/компоненты нужно будет изменить или создать
3. Какие решения принимаешь при планировании и почему
4. Какие альтернативные подходы рассматриваешь
5. Как план учитывает контекст и рекомендации из памяти

Пример детального thinking:
"Анализирую задачу: нужно добавить поддержку DELETE запросов в CORS.
Проверяю контекст - вижу что в проекте используется FastAPI.
План должен включать: 1) анализ текущей конфигурации CORS, 2) добавление DELETE в список методов, 3) тестирование.
Учитываю рекомендации из памяти о безопасности CORS."
</think>
"""
        
        return f"""Ты - эксперт по планированию разработки. Создай детальный план для следующей задачи.

Задача: {task}
Тип: {intent_desc}
{context_section}{memory_section}
Требования к плану:
1. Основной план должен быть детальным и пошаговым (минимум 4-5 шагов)
2. Каждый шаг должен быть конкретным и выполнимым
3. Предложи {alternatives_count} альтернативных подхода (если основной не сработает)
4. Учитывай лучшие практики Python и рекомендации из контекста/памяти
5. План должен учитывать TDD подход (тесты ДО кода)
6. Учитывай зависимости между шагами

{thinking_instructions}

Формат ответа (строго придерживайся):

ОСНОВНОЙ ПЛАН:
1. [Конкретный шаг 1 - что именно делать]
2. [Конкретный шаг 2 - что именно делать]
3. [Конкретный шаг 3 - что именно делать]
...

АЛЬТЕРНАТИВНЫЙ ПОДХОД 1:
1. [Шаг 1]
...

АЛЬТЕРНАТИВНЫЙ ПОДХОД 2:
1. [Шаг 1]
...

План:
"""
    
    @staticmethod
    def build_debug_analysis_prompt(
        task: str,
        code: str,
        tests: str,
        error_details: Dict[str, str],
        error_type: str
    ) -> str:
        """Строит промпт для анализа ошибок отладки.
        
        Args:
            task: Исходная задача
            code: Код с ошибками
            tests: Тесты
            error_details: Детали ошибок
            error_type: Тип ошибки
            
        Returns:
            Промпт для анализа ошибок
        """
        code_section = PromptTemplates.format_code_section(code, max_length=1500)
        tests_section = PromptTemplates.format_code_section(tests, max_length=1000)
        errors_text = PromptTemplates.format_errors_section(error_details)
        
        return f"""Ты - эксперт по отладке Python кода. Проанализируй ошибки и создай конкретные инструкции для исправления.

Исходная задача: {task}

Текущий код (с ошибками):
{code_section}

Тесты:
{tests_section}

Ошибки валидации:
{errors_text}

Проанализируй и ответь строго в следующем формате:

ОПИСАНИЕ_ОШИБОК:
[Краткое описание найденных ошибок на русском языке]

ПРИЧИНА:
[Основная причина ошибок на русском языке. Объясни почему код не работает.]

ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ:
[Конкретные, атомарные инструкции на английском языке для Coder Agent. 
Каждая инструкция должна быть чёткой и выполнимой. 
Формат: "Fix X by doing Y" или "Add Z to function A" или "Change type annotation from X to Y"]
[ВАЖНО: Инструкции должны быть конкретными и направленными на исправление конкретных ошибок из валидации]

УВЕРЕННОСТЬ: [0.0-1.0]
[Оценка уверенности в диагнозе]
"""
    
    @staticmethod
    def build_reflection_prompt(
        task: str,
        plan: str,
        context: str,
        tests: str,
        code: str,
        validation_results: Dict[str, Any],
        base_scores: Dict[str, float]
    ) -> str:
        """Строит промпт для рефлексии.
        
        Args:
            task: Исходная задача
            plan: План выполнения
            context: Собранный контекст
            tests: Сгенерированные тесты
            code: Сгенерированный код
            validation_results: Результаты валидации
            base_scores: Базовые оценки
            
        Returns:
            Промпт для рефлексии
        """
        validation_summary = PromptTemplates.format_validation_summary(validation_results)
        
        return f"""Ты - эксперт по анализу качества кода и процессов разработки. Проанализируй выполнение задачи.

Задача: {task}

План:
{plan}

Собранный контекст (длина: {len(context)} символов):
{context[:500] if context else 'Контекст не собран'}

Сгенерированные тесты (длина: {len(tests)} символов, количество: {tests.count('def test_')}):
{tests[:300] if tests else 'Тесты не сгенерированы'}

Сгенерированный код (длина: {len(code)} символов):
{code[:500] if code else 'Код не сгенерирован'}

{validation_summary}

Базовые оценки:
- Planning: {base_scores['planning']:.2f}
- Research: {base_scores['research']:.2f}
- Testing: {base_scores['testing']:.2f}
- Coding: {base_scores['coding']:.2f}

Проанализируй и ответь в следующем формате (строго придерживайся формата):

ОЦЕНКИ:
planning: [0.0-1.0]
research: [0.0-1.0]
testing: [0.0-1.0]
coding: [0.0-1.0]
overall: [0.0-1.0]

АНАЛИЗ:
[Что прошло хорошо, что плохо, какие проблемы]

УЛУЧШЕНИЯ:
[Конкретные предложения: новый план / другая стратегия / изменения в промптах]

НУЖНА_ПОВТОРНАЯ_ПОПЫТКА: [да/нет]
"""


# === Удобные функции для импорта ===

def format_context_section(context: str, title: str = "Контекст") -> str:
    """Форматирует секцию контекста."""
    return PromptTemplates.format_context_section(context, title)


def format_code_section(code: str, language: str = "python", max_length: int = 1500) -> str:
    """Форматирует секцию кода."""
    return PromptTemplates.format_code_section(code, language, max_length)


def format_errors_section(error_details: Dict[str, str]) -> str:
    """Форматирует секцию ошибок валидации."""
    return PromptTemplates.format_errors_section(error_details)


def format_validation_summary(validation_results: Dict[str, Any]) -> str:
    """Форматирует сводку результатов валидации."""
    return PromptTemplates.format_validation_summary(validation_results)


def build_planning_prompt(
    task: str,
    intent_type: str,
    context: str = "",
    memory_recommendations: str = "",
    alternatives_count: int = 2
) -> str:
    """Строит промпт для планирования."""
    return PromptTemplates.build_planning_prompt(
        task, intent_type, context, memory_recommendations, alternatives_count
    )


def build_debug_analysis_prompt(
    task: str,
    code: str,
    tests: str,
    error_details: Dict[str, str],
    error_type: str
) -> str:
    """Строит промпт для анализа ошибок отладки."""
    return PromptTemplates.build_debug_analysis_prompt(
        task, code, tests, error_details, error_type
    )


def build_reflection_prompt(
    task: str,
    plan: str,
    context: str,
    tests: str,
    code: str,
    validation_results: Dict[str, Any],
    base_scores: Dict[str, float]
) -> str:
    """Строит промпт для рефлексии."""
    return PromptTemplates.build_reflection_prompt(
        task, plan, context, tests, code, validation_results, base_scores
    )
