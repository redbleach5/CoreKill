"""Агент для планирования выполнения задачи."""
from typing import Optional, List
from infrastructure.local_llm import create_llm_for_stage
from agents.memory import MemoryAgent
from agents.base import BaseAgent
from utils.logger import get_logger
from utils.model_checker import (
    get_available_model,
    get_light_model,
    get_any_available_model,
    check_model_available
)
from utils.config import get_config
from infrastructure.model_router import get_model_router


logger = get_logger()


class PlannerAgent(BaseAgent):
    """Агент для создания плана выполнения задачи и альтернативных подходов.
    
    Использует память для извлечения уроков из прошлых похожих задач.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.25,
        memory_agent: Optional[MemoryAgent] = None
    ) -> None:
        """Инициализация агента планирования.
        
        Args:
            model: Модель для генерации планов (если None, выбирается из config)
            temperature: Температура генерации
            memory_agent: Опциональный экземпляр MemoryAgent для получения рекомендаций
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="planning"
        )
        self.memory = memory_agent

    def create_plan(
        self,
        task: str,
        intent_type: str,
        context: str = "",
        alternatives_count: int = 2
    ) -> str:
        """Создаёт план выполнения задачи с альтернативными подходами.
        
        Args:
            task: Текст задачи
            intent_type: Тип намерения
            context: Собранный контекст (включая рекомендации из памяти)
            alternatives_count: Количество альтернативных подходов (2-3 по правилам)
            
        Returns:
            План с основным подходом и альтернативами
        """
        logger.info(f"📋 Создаю план для задачи: {task[:60]}...")
        
        # Не создаём план для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущено планирование для приветствия")
            return ""
        
        # Быстрый план ТОЛЬКО для очень простых задач (fix, rename, typo)
        # Игры, проекты, приложения — всегда полный план
        # НО: простые запросы типа "напиши функцию X" тоже должны быть простыми
        complex_keywords = [
            'игра', 'game', 'приложение', 'app', 'проект', 'project', 
            'сервис', 'service', 'api', 'бот', 'bot', 'framework', 'библиотека', 'library'
        ]
        # Простые ключевые слова, которые не делают задачу сложной
        simple_patterns = [
            'напиши функцию', 'write a function', 'создай функцию', 'create a function',
            'напиши класс', 'write a class', 'создай класс', 'create a class'
        ]
        
        # Проверяем сначала простые паттерны
        is_simple_request = any(pattern in task.lower() for pattern in simple_patterns)
        is_complex = any(keyword in task.lower() for keyword in complex_keywords) and not is_simple_request
        
        # Для простых запросов используем упрощенный план
        if (len(task.strip()) < 50 or is_simple_request) and not is_complex:
            # Пытаемся извлечь предполагаемое имя функции из запроса
            suggested_name = self._extract_function_name_from_task(task)
            signature_hint = ""
            if suggested_name:
                signature_hint = f"\nПредполагаемое имя функции: {suggested_name}\nПредполагаемая сигнатура: def {suggested_name}(...)\n"
            
            simple_plan = f"""ОСНОВНОЙ ПЛАН:
1. Проанализировать простую задачу: {task}
{signature_hint}2. Создать минимальную реализацию
3. Добавить базовые тесты
4. Проверить работоспособность
"""
            logger.info("✅ Использован упрощённый план (простая задача)")
            return simple_plan
        
        logger.info(f"📋 Создаю полный план (задача сложная: {len(task)} симв., complex={is_complex})")
        
        # Получаем рекомендации из памяти если доступны
        memory_recommendations = ""
        if self.memory:
            memory_recommendations = self.memory.get_recommendations(task, intent_type)
        
        prompt = self._build_planning_prompt(
            task=task,
            intent_type=intent_type,
            context=context,
            memory_recommendations=memory_recommendations,
            alternatives_count=alternatives_count
        )
        
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_planning)
        
        plan = self._clean_plan(response)
        
        if plan:
            logger.info(f"✅ План создан (размер: {len(plan)} символов)")
        else:
            logger.warning("⚠️ Не удалось создать план")
        
        return plan

    def _build_planning_prompt(
        self,
        task: str,
        intent_type: str,
        context: str,
        memory_recommendations: str,
        alternatives_count: int
    ) -> str:
        """Строит промпт для генерации плана."""
        from infrastructure.prompt_templates import build_planning_prompt
        return build_planning_prompt(
            task=task,
            intent_type=intent_type,
            context=context,
            memory_recommendations=memory_recommendations,
            alternatives_count=alternatives_count
        )

    def _clean_plan(self, raw_plan: str) -> str:
        """Очищает сгенерированный план от лишних элементов.
        
        Args:
            raw_plan: Сырой план от модели
            
        Returns:
            Очищенный план
        """
        if not raw_plan:
            return ""
        
        lines = raw_plan.split("\n")
        cleaned_lines: List[str] = []
        
        # Убираем markdown блоки
        skip_until_plan = False
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    skip_until_plan = True
                else:
                    in_code_block = False
                continue
            
            if skip_until_plan:
                if "ОСНОВНОЙ ПЛАН" in stripped.upper() or "ПЛАН:" in stripped.upper():
                    skip_until_plan = False
                    cleaned_lines.append(line)
                continue
            
            # Пропускаем пустые строки в начале
            if not cleaned_lines and not stripped:
                continue
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        # Убеждаемся что есть хотя бы "ПЛАН" или "ОСНОВНОЙ"
        if not any(word in cleaned.upper() for word in ["ПЛАН", "ОСНОВНОЙ", "ШАГ", "ПОДХОД"]):
            logger.warning("⚠️ В плане не найдено ключевых слов")
            # Создаём базовый план если модель не вернула структуру
            cleaned = f"ОСНОВНОЙ ПЛАН:\n{cleaned}"
        
        return cleaned
    
    def _extract_function_name_from_task(self, task: str) -> Optional[str]:
        """Извлекает предполагаемое имя функции из запроса пользователя.
        
        Пытается найти имя функции в запросах вида:
        - "напиши функцию сортировки" -> "sort" или "sorting"
        - "создай функцию add" -> "add"
        - "write a function to calculate" -> "calculate"
        
        Args:
            task: Текст задачи
            
        Returns:
            Предполагаемое имя функции в snake_case или None
        """
        import re
        
        task_lower = task.lower()
        
        # Паттерны для поиска имени функции
        patterns = [
            r'(?:напиши|создай|write|create)\s+(?:функцию|function)\s+(?:для|to|that|which)?\s*([a-z_][a-z0-9_]*)',  # "напиши функцию add"
            r'(?:напиши|создай|write|create)\s+(?:функцию|function)\s+(?:для|to)?\s*([а-яё]+)',  # "напиши функцию сортировки"
            r'функция\s+([a-z_][a-z0-9_]*)',  # "функция add"
            r'function\s+([a-z_][a-z0-9_]*)',  # "function add"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task_lower)
            if match:
                name = match.group(1)
                # Преобразуем в snake_case если нужно
                name = name.replace(' ', '_').replace('-', '_')
                # Ограничиваем длину
                if len(name) > 50:
                    name = name[:50]
                return name
        
        # Если не нашли явное имя, пытаемся извлечь ключевое слово из задачи
        # Для "напиши функцию сортировки" -> "sort"
        keyword_map = {
            'сортировк': 'sort',
            'sorting': 'sort',
            'сложени': 'add',
            'addition': 'add',
            'вычитани': 'subtract',
            'subtraction': 'subtract',
            'умножени': 'multiply',
            'multiplication': 'multiply',
            'делени': 'divide',
            'division': 'divide',
            'поиск': 'search',
            'search': 'search',
            'фильтрац': 'filter',
            'filter': 'filter',
        }
        
        for keyword, func_name in keyword_map.items():
            if keyword in task_lower:
                return func_name
        
        return None
