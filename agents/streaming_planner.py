"""Стриминговая версия агента планирования.

Обеспечивает real-time стриминг:
- <think> блоков reasoning моделей
- Плана по мере генерации
- Возможность прерывания
"""
from typing import Optional, AsyncGenerator, List
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.reasoning_utils import extract_code_from_reasoning, is_reasoning_response
from agents.memory import MemoryAgent
from agents.base import BaseAgent
from utils.logger import get_logger
from utils.config import get_config
from infrastructure.model_router import get_model_router

logger = get_logger()


class StreamingPlannerAgent(BaseAgent):
    """Агент для создания плана с real-time стримингом.
    
    Расширяет функциональность PlannerAgent:
    - Real-time стриминг <think> блоков
    - Real-time стриминг плана
    - Возможность прерывания генерации
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.25,
        memory_agent: Optional[MemoryAgent] = None
    ) -> None:
        """Инициализация агента.
        
        Args:
            model: Модель (если None, выбирается автоматически)
            temperature: Температура генерации
            memory_agent: Агент памяти для рекомендаций
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="planning"
        )
        self.memory = memory_agent
        self.reasoning_manager = get_reasoning_stream_manager()
        self._interrupted = False
    
    def interrupt(self) -> None:
        """Прерывает текущую генерацию."""
        self._interrupted = True
        self.reasoning_manager.interrupt()
        logger.info("⏹️ Генерация плана прервана")
    
    def reset(self) -> None:
        """Сбрасывает состояние агента."""
        self._interrupted = False
        self.reasoning_manager.reset()
    
    async def create_plan_stream(
        self,
        task: str,
        intent_type: str,
        context: str = "",
        alternatives_count: int = 2,
        stage: str = "planning"
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Создаёт план с real-time стримингом.
        
        Args:
            task: Текст задачи
            intent_type: Тип намерения
            context: Контекст из RAG
            alternatives_count: Количество альтернатив
            stage: Этап workflow (для SSE событий)
            
        Yields:
            tuple[event_type, data]:
                - ("thinking", sse_event) — SSE событие для <think> блока
                - ("plan_chunk", chunk) — чанк плана
                - ("done", final_plan) — финальный план
        """
        logger.info(f"📋 Стриминг плана для: {task[:60]}...")
        
        self.reset()
        
        # Не создаём план для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущено планирование для приветствия")
            yield ("done", "")
            return
        
        # Быстрый план ТОЛЬКО для очень простых задач (fix, rename, typo)
        # Игры, проекты, приложения — всегда полный план
        complex_keywords = [
            'файл', 'класс', 'функция', 'модуль', 'test', 'file', 'class', 'function',
            'игра', 'game', 'приложение', 'app', 'проект', 'project', 'создай', 'напиши',
            'write', 'create', 'build', 'implement', 'сервис', 'service', 'api', 'бот', 'bot'
        ]
        is_complex = any(keyword in task.lower() for keyword in complex_keywords)
        
        if len(task.strip()) < 15 and not is_complex:
            simple_plan = f"""ОСНОВНОЙ ПЛАН:
1. Проанализировать простую задачу: {task}
2. Создать минимальную реализацию
3. Добавить базовые тесты
4. Проверить работоспособность
"""
            logger.info("✅ Использован упрощённый план (простая задача < 15 символов)")
            yield ("done", simple_plan)
            return
        
        logger.info(f"📋 Создаю полный план (задача сложная: {len(task)} симв., complex={is_complex})")
        
        # Получаем рекомендации из памяти
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
        plan_buffer = ""
        full_response = ""
        
        try:
            async for event_type, data in self.reasoning_manager.stream_from_llm(
                llm=self.llm,
                prompt=prompt,
                stage=stage,
                num_predict=config.llm_tokens_planning
            ):
                if self._interrupted:
                    logger.info("⏹️ Генерация прервана")
                    break
                
                if event_type == "thinking":
                    yield ("thinking", data)
                elif event_type == "content":
                    plan_buffer += data
                    yield ("plan_chunk", data)
                elif event_type == "done":
                    full_response = data
            
            # Очищаем финальный план
            if full_response:
                if is_reasoning_response(full_response):
                    plan_only = extract_code_from_reasoning(full_response)
                    cleaned_plan = self._clean_plan(plan_only)
                else:
                    cleaned_plan = self._clean_plan(full_response)
            else:
                cleaned_plan = self._clean_plan(plan_buffer)
            
            if cleaned_plan:
                logger.info(f"✅ План создан ({len(cleaned_plan)} символов)")
            else:
                logger.warning("⚠️ Не удалось создать план")
            
            yield ("done", cleaned_plan)
            
        except Exception as e:
            logger.error(f"❌ Ошибка стриминга плана: {e}", error=e)
            yield ("done", "")
    
    # === Синхронный метод для обратной совместимости ===
    
    def create_plan(
        self,
        task: str,
        intent_type: str,
        context: str = "",
        alternatives_count: int = 2
    ) -> str:
        """Синхронное создание плана (для обратной совместимости)."""
        from agents.planner import PlannerAgent
        
        sync_agent = PlannerAgent(
            model=self.model,
            temperature=self.temperature,
            memory_agent=self.memory
        )
        return sync_agent.create_plan(task, intent_type, context, alternatives_count)
    
    # === Приватные методы ===
    
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
        """Очищает сгенерированный план."""
        if not raw_plan:
            return ""
        
        lines = raw_plan.split("\n")
        cleaned_lines: List[str] = []
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
            
            if not cleaned_lines and not stripped:
                continue
            
            cleaned_lines.append(line)
        
        cleaned = "\n".join(cleaned_lines).strip()
        
        if not any(word in cleaned.upper() for word in ["ПЛАН", "ОСНОВНОЙ", "ШАГ", "ПОДХОД"]):
            logger.warning("⚠️ В плане не найдено ключевых слов")
            cleaned = f"ОСНОВНОЙ ПЛАН:\n{cleaned}"
        
        return cleaned


# === Factory функция ===

def get_streaming_planner_agent(
    model: Optional[str] = None,
    temperature: float = 0.25,
    memory_agent: Optional[MemoryAgent] = None
) -> StreamingPlannerAgent:
    """Создаёт StreamingPlannerAgent."""
    return StreamingPlannerAgent(
        model=model,
        temperature=temperature,
        memory_agent=memory_agent
    )
