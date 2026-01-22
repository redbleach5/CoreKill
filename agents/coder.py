"""Агент для генерации кода по тестам и плану (TDD)."""
from typing import Optional, Dict, Any, TYPE_CHECKING
from infrastructure.local_llm import create_llm_for_stage
from infrastructure.prompt_enhancer import get_prompt_enhancer
from infrastructure.code_retrieval import get_code_retriever, CodeExample
from infrastructure.coder_prompt_builder import get_coder_prompt_builder
from infrastructure.code_security import get_code_security_checker
from utils.logger import get_logger
from utils.model_checker import (
    get_available_model,
    get_any_available_model,
    check_model_available
)
from utils.config import get_config
from utils.intent_helpers import get_intent_description
from agents.base import BaseAgent

if TYPE_CHECKING:
    from infrastructure.coder_interfaces import ILLM, IPromptEnhancer, ICodeRetriever, IPromptBuilder


logger = get_logger()


class CoderAgent(BaseAgent):
    """Агент для генерации рабочего кода, который должен пройти сгенерированные тесты.
    
    Следует TDD-подходу: код генерируется ПОСЛЕ тестов.
    Использует PromptEnhancer для динамического улучшения промптов.
    """

    def __init__(
        self, 
        model: Optional[str] = None, 
        temperature: float = 0.25,
        user_query: str = "",
        llm: Optional['ILLM'] = None,
        prompt_enhancer: Optional['IPromptEnhancer'] = None,
        retriever: Optional['ICodeRetriever'] = None,
        prompt_builder: Optional['IPromptBuilder'] = None
    ) -> None:
        """Инициализация агента генерации кода.
        
        Args:
            model: Модель для генерации кода (если None, выбирается из config)
            temperature: Температура генерации (0.15-0.35 по правилам)
            user_query: Оригинальный запрос пользователя для улучшения промптов
            llm: LLM для генерации (для тестирования, по умолчанию создаётся автоматически)
            prompt_enhancer: Улучшитель промптов (для тестирования)
            retriever: Поисковик примеров кода (для тестирования)
            prompt_builder: Билдер промптов (для тестирования)
        """
        # Инициализация базового класса (LLM создаётся автоматически)
        super().__init__(
            model=model,
            temperature=temperature,
            stage="coding",
            llm=llm
        )
        
        self.user_query = user_query
        self.prompt_enhancer = prompt_enhancer or get_prompt_enhancer()
        
        # Code Retrieval для few-shot примеров (Phase 4)
        self.retriever = retriever or get_code_retriever()
        
        # Единый билдер промптов (устраняет дубли)
        self.prompt_builder = prompt_builder or get_coder_prompt_builder()
        
        # Проверка безопасности кода
        self.security_checker = get_code_security_checker()

    def generate_code(
        self,
        plan: str,
        tests: str,
        context: str,
        intent_type: str,
        user_query: str = ""
    ) -> str:
        """Генерирует рабочий код на основе тестов, плана и контекста.
        
        Args:
            plan: План реализации задачи
            tests: Сгенерированные pytest тесты
            context: Собранный контекст из RAG/веб-поиска
            intent_type: Тип намерения (create/modify/debug/etc)
            user_query: Оригинальный запрос пользователя (для улучшения промпта)
            
        Returns:
            Строка с полным кодом. Пустая строка в случае ошибки.
        """
        logger.info(f"💻 Генерирую код для намерения: {intent_type}")
        
        # Не генерируем код для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущена генерация кода для приветствия")
            return ""
        
        # Используем оригинальный запрос пользователя если передан
        query = user_query or self.user_query
        
        # Ищем похожие примеры кода (Phase 4: Code Retrieval)
        examples: list[CodeExample] = []
        if self.retriever:
            try:
                examples = self.retriever.find_similar(
                    query=f"{plan}\n{query}" if query else plan,
                    n=3
                )
                if examples:
                    logger.info(f"📚 Найдено {len(examples)} примеров кода для few-shot")
            except Exception as e:
                logger.debug(f"Code retrieval пропущен: {e}")
        
        # Используем единый PromptBuilder (устраняет дубли)
        if query and not examples:
            # Если есть запрос и нет примеров, используем PromptEnhancer для улучшения
            prompt = self.prompt_enhancer.enhance_for_coding(
                user_query=query,
                intent_type=intent_type,
                plan=plan,
                tests=tests,
                context=context
            )
        else:
            # Используем единый билдер (с примерами или без)
            prompt = self.prompt_builder.build_generation_prompt(
                plan=plan,
                tests=tests,
                context=context,
                intent_type=intent_type,
                user_query=query,
                examples=examples
            )
        
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_code)
        
        # Очищаем и валидируем сгенерированный код (используем метод из BaseAgent)
        # Если ответ содержит reasoning, извлекаем код из него
        cleaned_code = self._clean_code_from_reasoning(response)
        
        if cleaned_code:
            logger.info(f"✅ Сгенерирован код (размер: {len(cleaned_code)} символов)")
            
            # Проверка безопасности перед сохранением в историю
            is_safe, security_warnings = self.security_checker.check_code(cleaned_code)
            if security_warnings:
                logger.warning(f"⚠️ Обнаружены предупреждения безопасности: {', '.join(security_warnings[:2])}")
            
            # Сохраняем успешную генерацию в историю (Phase 4) только если код безопасен
            if self.retriever and query and is_safe:
                try:
                    self.retriever.add_from_history(query, cleaned_code, success=True)
                except Exception as e:
                    logger.debug(f"Не удалось сохранить в историю: {e}")
            elif self.retriever and query and not is_safe:
                logger.warning("⚠️ Код не сохранён в историю из-за предупреждений безопасности")
        else:
            logger.warning("⚠️ Не удалось сгенерировать валидный код")
        
        return cleaned_code

    def fix_code(
        self,
        code: str,
        instructions: str,
        tests: str,
        validation_results: Dict[str, Any]
    ) -> str:
        """Исправляет код по инструкциям от Debugger Agent.
        
        Args:
            code: Исходный код с ошибками
            instructions: Конкретные инструкции от Debugger Agent (EN)
            tests: Тесты для кода
            validation_results: Результаты валидации с ошибками
            
        Returns:
            Исправленный код. Пустая строка в случае ошибки.
        """
        logger.info("🔧 Исправляю код по инструкциям от Debugger...")
        
        if not code.strip() or not instructions.strip():
            logger.warning("⚠️ Пустой код или инструкции")
            return code
        
        # Используем единый PromptBuilder
        prompt = self.prompt_builder.build_fix_prompt(
            code=code,
            instructions=instructions,
            tests=tests,
            validation_results=validation_results
        )
        
        config = get_config()
        response = self.llm.generate(prompt, num_predict=config.llm_tokens_code)
        
        # Очищаем исправленный код (используем метод из BaseAgent)
        fixed_code = self._clean_code_from_reasoning(response)
        
        if fixed_code:
            logger.info(f"✅ Код исправлен (размер: {len(fixed_code)} символов)")
        else:
            logger.warning("⚠️ Не удалось исправить код, возвращаю исходный")
            fixed_code = code
        
        return fixed_code
