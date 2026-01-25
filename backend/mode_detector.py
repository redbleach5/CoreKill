"""Определение режима взаимодействия на основе задачи пользователя.

Вынесено из stream_task_results для улучшения читаемости и поддерживаемости.
"""
from typing import Optional
from agents.intent import IntentAgent, IntentResult
from utils.model_checker import TaskComplexity
from utils.logger import get_logger

logger = get_logger()


class ModeDetector:
    """Определяет режим взаимодействия на основе задачи и пользовательского выбора."""
    
    def __init__(self):
        """Инициализирует ModeDetector."""
        self.intent_agent = IntentAgent(lazy_llm=True)
        
        # Ключевые слова для генерации кода
        self.code_keywords = [
            'напиши', 'создай', 'сделай', 'реализуй', 'сгенерируй',
            'write', 'create', 'make', 'implement', 'generate',
            'функци', 'класс', 'модуль', 'скрипт',
            'function', 'class', 'module', 'script',
            'исправ', 'отлад', 'debug', 'fix', 'оптимизир'
        ]
        
        # Ключевые слова для диалога (НЕ генерация кода)
        self.chat_keywords = [
            'объясни', 'расскажи', 'что такое', 'как работает',
            'explain', 'tell me', 'what is', 'how does',
            'почему', 'зачем', 'когда', 'можно ли',
            'why', 'when', 'can you', 'should i',
            'посоветуй', 'подскажи', 'помоги понять',
            # Обучающие запросы — это тоже chat (не генерация кода)
            'научи', 'научись', 'обучи', 'покажи как', 'покажи пример',
            'teach', 'learn', 'show me', 'show example', 'tutorial',
            'хочу научиться', 'хочу изучить', 'как начать', 'с чего начать',
            'i want to learn', 'how to start', 'where to start',
            # Запросы актуальной информации (realtime) — это тоже chat
            'новост', 'событи', 'погод', 'курс', 'сегодня', 'вчера', 'завтра',
            'news', 'weather', 'today', 'yesterday', 'tomorrow',
            'что происходит', 'что случилось', 'что нового', 'какие',
            "what's happening", 'latest', 'current'
        ]
        
        # Ключевые слова анализа проекта
        self.analyze_keywords = [
            'проанализируй', 'анализ', 'обзор', 'структур', 'архитектур',
            'analyze', 'review', 'overview', 'structure', 'architecture',
            'покажи проект', 'изучи проект', 'посмотри проект'
        ]
        
        # Обучающие паттерны
        self.learning_patterns = [
            'научи', 'научись', 'обучи', 'хочу научиться', 'хочу изучить',
            'teach', 'learn', 'i want to learn', 'how to start'
        ]
    
    def detect(
        self,
        task: str,
        user_mode: str,
        detected_intent_type: Optional[str] = None,
        detected_complexity: Optional[TaskComplexity] = None
    ) -> tuple[str, Optional[str], Optional[TaskComplexity]]:
        """Определяет режим взаимодействия на основе задачи.
        
        Args:
            task: Текст задачи пользователя
            user_mode: Режим, выбранный пользователем (auto, chat, code)
            detected_intent_type: Тип намерения (если уже определён)
            detected_complexity: Сложность задачи (если уже определена)
            
        Returns:
            Tuple (selected_mode, detected_intent_type, detected_complexity)
        """
        # Если пользователь явно выбрал режим, уважаем его выбор
        if user_mode == "chat":
            return self._handle_chat_mode(task, detected_complexity)
        elif user_mode == "code":
            return self._handle_code_mode(task, detected_complexity)
        elif user_mode == "auto":
            return self._handle_auto_mode(task, detected_intent_type, detected_complexity)
        else:
            # Неизвестный режим, используем auto
            logger.warning(f"⚠️ Неизвестный режим: {user_mode}, используем auto")
            return self._handle_auto_mode(task, detected_intent_type, detected_complexity)
    
    def _handle_chat_mode(
        self,
        task: str,
        detected_complexity: Optional[TaskComplexity]
    ) -> tuple[str, Optional[str], Optional[TaskComplexity]]:
        """Обрабатывает явный режим диалога."""
        if detected_complexity is None:
            detected_complexity = self.intent_agent._estimate_complexity_heuristic(task)
        
        # Для диалога определяем intent только для выбора модели
        detected_intent_type = None
        if IntentAgent.is_greeting_fast(task):
            detected_intent_type = "greeting"
            detected_complexity = TaskComplexity.SIMPLE
        
        logger.info(f"💬 Явный режим диалога, сложность: {detected_complexity.value}")
        return "chat", detected_intent_type, detected_complexity
    
    def _handle_code_mode(
        self,
        task: str,
        detected_complexity: Optional[TaskComplexity]
    ) -> tuple[str, Optional[str], Optional[TaskComplexity]]:
        """Обрабатывает явный режим генерации кода."""
        if detected_complexity is None:
            detected_complexity = self.intent_agent._estimate_complexity_heuristic(task)
        
        logger.info(f"🔧 Явный режим генерации кода, сложность: {detected_complexity.value}")
        return "code", None, detected_complexity
    
    def _handle_auto_mode(
        self,
        task: str,
        detected_intent_type: Optional[str],
        detected_complexity: Optional[TaskComplexity]
    ) -> tuple[str, Optional[str], Optional[TaskComplexity]]:
        """Обрабатывает автоматический режим определения."""
        task_lower = task.lower()
        
        # ИСПРАВЛЕНИЕ: Быстрая проверка на greeting только для простых приветствий
        # Если приветствие содержит вопросы - не используем быструю проверку
        if IntentAgent.is_greeting_fast(task):
            # Проверяем, есть ли вопросы или команды рассказать
            has_question = any(indicator in task.lower() for indicator in 
                              ["?", "знаешь", "расскажи", "do you know", "tell me", "what", "who", "when", "where"])
            has_tell_command = any(cmd in task.lower() for cmd in 
                                  ["расскажи", "опиши", "tell", "describe", "explain"])
            
            # Только для простых приветствий без вопросов используем быструю проверку
            if not (has_question or has_tell_command) or len(task.split()) <= 3:
                logger.info("🚀 Быстрое определение: простое greeting → chat + SIMPLE")
                return "chat", "greeting", TaskComplexity.SIMPLE
            else:
                logger.info("💬 Приветствие с вопросом - пропускаем быструю проверку, используем полную классификацию")
                # Продолжаем с полной классификацией
        
        # Проверяем ключевые слова
        has_code_keyword = any(kw in task_lower for kw in self.code_keywords)
        has_chat_keyword = any(kw in task_lower for kw in self.chat_keywords)
        has_analyze_keyword = any(kw in task_lower for kw in self.analyze_keywords)
        is_learning_request = any(pattern in task_lower for pattern in self.learning_patterns)
        
        # ПРИОРИТЕТ: Обучающие запросы ВСЕГДА chat
        if is_learning_request:
            detected_complexity = TaskComplexity.SIMPLE
            detected_intent_type = "explain"
            logger.info(f"📚 Обучающий запрос → chat + SIMPLE (быстрая модель)")
            return "chat", detected_intent_type, detected_complexity
        
        # Если есть chat-ключевые слова и НЕТ code-ключевых → диалог
        if has_chat_keyword and not has_code_keyword and not has_analyze_keyword:
            if detected_complexity is None:
                detected_complexity = self.intent_agent._estimate_complexity_heuristic(task)
            detected_intent_type = "explain"
            logger.info(f"💬 Обнаружены chat-ключевые слова → chat + {detected_complexity.value}")
            return "chat", detected_intent_type, detected_complexity
        
        # Анализ проекта
        if has_analyze_keyword and not has_code_keyword:
            detected_complexity = TaskComplexity.COMPLEX
            detected_intent_type = "analyze"
            logger.info(f"🔍 Обнаружены analyze-ключевые слова → analyze + {detected_complexity.value}")
            return "analyze", detected_intent_type, detected_complexity
        
        # Генерация кода
        if has_code_keyword:
            if detected_complexity is None:
                detected_complexity = self.intent_agent._estimate_complexity_heuristic(task)
            logger.info(f"🔧 Обнаружены code-ключевые слова → code + {detected_complexity.value}")
            return "code", None, detected_complexity
        
        # Fallback: используем LLM для точного определения intent
        intent_result: IntentResult = self.intent_agent.determine_intent(task)
        selected_mode = intent_result.recommended_mode
        
        if detected_complexity is None:
            detected_complexity = self.intent_agent._estimate_complexity_heuristic(task)
        
        detected_intent_type = intent_result.type
        
        # Для explain intent минимум MEDIUM сложность
        if intent_result.type == "explain" and detected_complexity == TaskComplexity.SIMPLE:
            detected_complexity = TaskComplexity.MEDIUM
            logger.info(f"📊 Explain intent повышен до MEDIUM")
        
        # Для analyze intent используем analyze режим
        if intent_result.type == "analyze":
            selected_mode = "analyze"
            detected_complexity = TaskComplexity.COMPLEX
            logger.info(f"🔍 Analyze intent → analyze + {detected_complexity.value}")
        
        logger.info(f"🧠 LLM определение: {intent_result.type} → {selected_mode} + {detected_complexity.value}")
        return selected_mode, detected_intent_type, detected_complexity
