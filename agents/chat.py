"""ChatAgent для простого диалогового взаимодействия с LLM.

Обеспечивает режим чата без запуска полного workflow.
Поддерживает контекст диалога и различные стили общения.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from infrastructure.local_llm import LocalLLM
from utils.logger import get_logger


logger = get_logger()


@dataclass
class ChatResponse:
    """Ответ ChatAgent."""
    content: str
    tokens_used: int = 0
    model_used: str = ""
    finish_reason: str = "stop"


class ChatAgent:
    """Агент для простого диалогового взаимодействия.
    
    Используется для режима chat, когда пользователь хочет просто
    поговорить с LLM без запуска полного workflow генерации кода.
    
    Поддерживает:
    - Диалог с контекстом истории
    - Ответы на вопросы о коде
    - Обсуждение архитектуры
    - Объяснения концепций
    """
    
    SYSTEM_PROMPT = """Ты — опытный senior разработчик и помощник по программированию.

Твои характеристики:
- Отвечаешь на русском языке
- Даёшь чёткие и структурированные ответы
- Если нужен код — показываешь примеры
- Если вопрос неясен — уточняешь
- Не делаешь предположений без необходимости
- Предлагаешь лучшие практики и паттерны

Ты можешь:
- Отвечать на вопросы о программировании
- Объяснять код и концепции
- Обсуждать архитектуру и подходы
- Помогать с отладкой (на уровне обсуждения)
- Предлагать улучшения кода

Если пользователь хочет сгенерировать полноценный код с тестами,
посоветуй использовать режим "Генерация кода" для лучшего результата."""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ):
        """Инициализирует ChatAgent.
        
        Args:
            model: Модель Ollama (None = автовыбор)
            temperature: Температура генерации (выше для креативности)
            max_tokens: Максимум токенов в ответе
        """
        self.llm = LocalLLM(model=model, temperature=temperature)
        self.max_tokens = max_tokens
        self.temperature = temperature
        logger.info(f"✅ ChatAgent инициализирован (модель: {model or 'auto'})")
    
    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> ChatResponse:
        """Отправляет сообщение и получает ответ.
        
        Args:
            message: Сообщение пользователя
            conversation_history: История диалога [{role, content}]
            system_prompt: Кастомный системный промпт (опционально)
            
        Returns:
            ChatResponse с ответом
        """
        # Формируем полный промпт с историей
        full_prompt = self._build_prompt(
            message=message,
            history=conversation_history,
            system_prompt=system_prompt or self.SYSTEM_PROMPT
        )
        
        logger.info(f"💬 ChatAgent: обработка сообщения ({len(message)} символов)")
        
        try:
            response = self.llm.generate(
                prompt=full_prompt,
                max_tokens=self.max_tokens
            )
            
            logger.info(f"✅ ChatAgent: получен ответ ({len(response)} символов)")
            
            return ChatResponse(
                content=response,
                model_used=self.llm.model_name or "",
                finish_reason="stop"
            )
            
        except Exception as e:
            logger.error(f"❌ ChatAgent ошибка: {e}", error=e)
            return ChatResponse(
                content=f"Произошла ошибка при генерации ответа: {str(e)}",
                finish_reason="error"
            )
    
    def _build_prompt(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
        system_prompt: str
    ) -> str:
        """Формирует полный промпт с историей диалога.
        
        Args:
            message: Текущее сообщение
            history: История диалога
            system_prompt: Системный промпт
            
        Returns:
            Полный промпт для LLM
        """
        parts = [f"<system>\n{system_prompt}\n</system>\n"]
        
        # Добавляем историю диалога
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    parts.append(f"<user>\n{content}\n</user>\n")
                elif role == "assistant":
                    parts.append(f"<assistant>\n{content}\n</assistant>\n")
                elif role == "system":
                    parts.append(f"<context>\n{content}\n</context>\n")
        
        # Добавляем текущее сообщение
        parts.append(f"<user>\n{message}\n</user>\n")
        parts.append("<assistant>\n")
        
        return "".join(parts)
    
    def explain_code(self, code: str, question: Optional[str] = None) -> ChatResponse:
        """Объясняет код.
        
        Args:
            code: Код для объяснения
            question: Конкретный вопрос о коде (опционально)
            
        Returns:
            ChatResponse с объяснением
        """
        prompt = f"Объясни следующий код:\n\n```\n{code}\n```"
        if question:
            prompt += f"\n\nКонкретный вопрос: {question}"
        
        return self.chat(
            message=prompt,
            system_prompt="""Ты — эксперт по коду. Объясняй код чётко и понятно:
1. Что делает код в целом
2. Ключевые части и их назначение
3. Используемые паттерны и подходы
4. Возможные улучшения (если есть)

Отвечай на русском языке."""
        )
    
    def discuss_architecture(
        self,
        description: str,
        context: Optional[str] = None
    ) -> ChatResponse:
        """Обсуждает архитектуру или подход.
        
        Args:
            description: Описание задачи или архитектуры
            context: Дополнительный контекст (опционально)
            
        Returns:
            ChatResponse с рекомендациями
        """
        prompt = f"Обсудим архитектуру/подход:\n\n{description}"
        if context:
            prompt += f"\n\nКонтекст:\n{context}"
        
        return self.chat(
            message=prompt,
            system_prompt="""Ты — архитектор ПО. При обсуждении архитектуры:
1. Анализируй требования
2. Предлагай несколько подходов с плюсами и минусами
3. Рекомендуй оптимальный вариант с обоснованием
4. Учитывай масштабируемость и поддерживаемость

Будь практичным, избегай over-engineering. Отвечай на русском."""
        )
    
    def quick_help(self, topic: str) -> ChatResponse:
        """Быстрая справка по теме.
        
        Args:
            topic: Тема для справки
            
        Returns:
            ChatResponse со справкой
        """
        return self.chat(
            message=f"Дай краткую справку по: {topic}",
            system_prompt="""Даёшь краткие, ёмкие справки по программированию.
Формат ответа:
- Краткое определение
- Пример использования (если уместно)
- Ссылки на документацию (если знаешь)

Отвечай на русском, кратко и по делу."""
        )


# Singleton для ChatAgent
_chat_agent: Optional[ChatAgent] = None


def get_chat_agent(
    model: Optional[str] = None,
    temperature: float = 0.3
) -> ChatAgent:
    """Возвращает singleton экземпляр ChatAgent.
    
    Args:
        model: Модель Ollama
        temperature: Температура генерации
        
    Returns:
        Экземпляр ChatAgent
    """
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatAgent(model=model, temperature=temperature)
    return _chat_agent


def reset_chat_agent() -> None:
    """Сбрасывает singleton ChatAgent."""
    global _chat_agent
    _chat_agent = None
    logger.info("🔄 ChatAgent сброшен")
