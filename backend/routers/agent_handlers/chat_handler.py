"""Handler для режима простого диалога (chat)."""
import uuid
from typing import AsyncGenerator, Optional

from agents.chat import get_chat_agent
from agents.conversation import get_conversation_memory
from utils.config import get_config
from utils.model_checker import TaskComplexity, check_model_available
from utils.ui_delays import ui_sleep
from backend.sse_manager import SSEManager
from infrastructure.model_router import get_model_router
from utils.logger import get_logger

logger = get_logger()


async def run_chat_stream(
    task: str,
    model: str,
    temperature: float,
    conversation_id: Optional[str] = None,
    task_complexity: Optional[TaskComplexity] = None,
    intent_type: Optional[str] = None,
    disable_web_search: bool = False
) -> AsyncGenerator[str, None]:
    """Обрабатывает запрос в режиме chat (простой диалог без workflow).
    
    Использует умную систему выбора модели:
    - SIMPLE (greeting, help) → лёгкая модель (phi3:mini)
    - MEDIUM (explain) → средняя модель
    - COMPLEX (архитектурные вопросы) → мощная модель
    
    Args:
        task: Сообщение пользователя
        model: Модель Ollama (используется как fallback)
        temperature: Температура генерации
        conversation_id: ID диалога для сохранения контекста
        task_complexity: Предопределённая сложность (если уже вычислена)
        intent_type: Тип намерения (greeting, help, explain и т.д.)
        
    Yields:
        SSE события с ответом
    """
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or task_id
    
    # Получаем конфиг
    config = get_config()
    
    # УМНЫЙ ВЫБОР МОДЕЛИ для chat режима на основе сложности
    complexity = task_complexity or TaskComplexity.SIMPLE
    
    # Для приветствий ВСЕГДА используем лёгкую модель
    # Для help — зависит от сложности (простой help vs сложное объяснение)
    if intent_type == "greeting":
        complexity = TaskComplexity.SIMPLE
        logger.info(f"📊 Intent greeting → принудительно SIMPLE")
    elif intent_type == "help" and complexity == TaskComplexity.SIMPLE:
        # Простой help (что умеешь, помощь) — оставляем SIMPLE
        logger.info(f"📊 Intent help + SIMPLE → оставляем SIMPLE")
    # Для explain и сложных help используем переданную сложность
    elif intent_type in ("help", "explain"):
        logger.info(f"📊 Intent {intent_type} → используем сложность {complexity.value}")
    
    # Выбираем модель через SmartModelRouter
    router = get_model_router()
    
    try:
        # Используем task_type="chat" для выбора подходящей модели
        model_selection = router.select_model_for_complexity(
            complexity=complexity,
            task_type="chat"  # Указываем что это chat, а не coding
        )
        chat_model = model_selection.model
        logger.info(f"🤖 {model_selection.reason}: {chat_model}")
        
    except RuntimeError as e:
        # Fallback на конфигурационную модель
        logger.warning(f"⚠️ SmartModelRouter не смог выбрать модель: {e}")
        chat_model = config.chat_model
        
        if not check_model_available(chat_model):
            logger.warning(f"⚠️ Chat модель {chat_model} недоступна, пробую fallback")
            chat_model = config.chat_model_fallback
            if not check_model_available(chat_model):
                logger.warning(f"⚠️ Fallback модель {chat_model} тоже недоступна, использую основную")
                chat_model = model if model else config.default_model
    
    logger.info(f"💬 Режим chat: обработка сообщения (conversation: {conv_id}, модель: {chat_model}, сложность: {complexity.value})")
    
    # Получаем менеджер диалогов
    conv_memory = get_conversation_memory()
    
    # Добавляем сообщение пользователя в историю
    conv_memory.add_message(conv_id, "user", task)
    
    # Получаем контекст диалога
    conversation_history = conv_memory.get_context(
        conv_id, 
        max_messages=config.interaction_max_context_messages
    )
    
    # Отправляем stage_start
    yield await SSEManager.stream_stage_start(
        stage="chat",
        message="Обрабатываю сообщение..."
    )
    await ui_sleep()
    
    try:
        # Получаем ChatAgent с ЛЁГКОЙ моделью для быстрых ответов
        chat_agent = get_chat_agent(model=chat_model, temperature=temperature)
        # ИСПРАВЛЕНИЕ: Для chat режима веб-поиск должен работать для вопросов о фактах
        # disable_web_search применяется только если явно отключен пользователем
        response = chat_agent.chat(
            message=task,
            conversation_history=conversation_history,
            disable_web_search=disable_web_search
        )
        
        # Сохраняем ответ в историю
        conv_memory.add_message(conv_id, "assistant", response.content)
        
        # Отправляем stage_end с ответом
        yield await SSEManager.stream_stage_end(
            stage="chat",
            message=response.content,
            result={
                "type": "chat",
                "message": response.content,
                "model_used": response.model_used
            }
        )
        await ui_sleep()
        
        # Финальный результат
        yield await SSEManager.stream_final_result(
            task_id=task_id,
            results={
                "task": task,
                "intent": {
                    "type": "chat",
                    "confidence": 1.0,
                    "description": "Режим диалога"
                },
                "chat_response": response.content,
                "conversation_id": conv_id,
                "greeting_message": response.content  # Для совместимости с frontend
            },
            metrics={
                "planning": 0.0,
                "research": 0.0,
                "testing": 0.0,
                "coding": 0.0,
                "overall": 0.0
            }
        )
        await ui_sleep("critical")
        
        logger.info(f"✅ Chat ответ отправлен ({len(response.content)} символов)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в chat режиме: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="chat",
            error_message=f"Ошибка генерации ответа: {str(e)}"
        )
