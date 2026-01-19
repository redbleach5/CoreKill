"""Агент для планирования выполнения задачи."""
from typing import Optional, List
from infrastructure.local_llm import create_llm_for_stage
from agents.memory import MemoryAgent
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


class PlannerAgent:
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
        if model is None:
            # Используем ModelRouter для выбора модели (поддерживает будущее расширение роя моделей)
            router = get_model_router()
            model_selection = router.select_model(
                task_type="planning",
                preferred_model=None,
                context={"agent": "planner"}
            )
            model = model_selection.model
        
        self.llm = create_llm_for_stage(
            stage="planning",
            model=model,
            temperature=temperature,
            top_p=0.9
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
        
        # Для очень простых задач создаём простой план без LLM
        if len(task.strip()) < 20 and not any(keyword in task.lower() for keyword in ['файл', 'класс', 'функция', 'модуль', 'test', 'file', 'class', 'function']):
            simple_plan = f"""ОСНОВНОЙ ПЛАН:
1. Проанализировать простую задачу: {task}
2. Создать минимальную реализацию
3. Добавить базовые тесты
4. Проверить работоспособность
"""
            logger.info("✅ Использован упрощённый план для простой задачи")
            return simple_plan
        
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
        
        intent_descriptions = {
            "create": "создание нового кода/функции/класса/модуля",
            "modify": "изменение существующего кода",
            "debug": "поиск и исправление ошибок",
            "optimize": "оптимизация производительности или качества",
            "explain": "объяснение кода",
            "test": "написание тестов",
            "refactor": "рефакторинг кода без изменения функциональности"
        }
        
        intent_desc = intent_descriptions.get(intent_type, "выполнение задачи")
        
        context_section = ""
        if context.strip():
            context_section = f"""
Контекст:
{context}
"""
        
        memory_section = ""
        if memory_recommendations:
            memory_section = f"""
Рекомендации из памяти прошлых задач:
{memory_recommendations}
"""
        
        prompt = f"""Ты - эксперт по планированию разработки. Создай детальный план для следующей задачи.

Задача: {task}
Тип: {intent_desc}
{context_section}{memory_section}
Требования к плану:
1. Основной план должен быть детальным и пошаговым (минимум 4-5 шагов)
2. Предложи {alternatives_count} альтернативных подхода (если основной не сработает)
3. План должен быть конкретным и выполнимым
4. Учитывай лучшие практики Python и рекомендации из контекста/памяти

Формат ответа:

ОСНОВНОЙ ПЛАН:
1. [Шаг 1]
2. [Шаг 2]
...

АЛЬТЕРНАТИВНЫЙ ПОДХОД 1:
1. [Шаг 1]
...

АЛЬТЕРНАТИВНЫЙ ПОДХОД 2:
1. [Шаг 1]
...

План:
"""
        return prompt

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
