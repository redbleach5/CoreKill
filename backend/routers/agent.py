"""Роутер для работы с агентами через API.

Поддерживает режимы взаимодействия:
- auto: Автоматический выбор режима на основе анализа
- chat: Простой диалог с LLM без workflow
- plan: Только планирование без генерации кода
- analyze: Анализ кода/задачи
- code: Полный workflow генерации кода (TDD)
"""
import asyncio
import re
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from agents.intent import IntentAgent, IntentResult
from agents.chat import ChatAgent, get_chat_agent
from agents.conversation import get_conversation_memory, ConversationMemory
from agents.reflection import ReflectionResult
from backend.types import InteractionMode, TaskRequest, SessionSettings, StreamQueryParams, IndexProjectRequest
from utils.artifact_saver import ArtifactSaver
from utils.config import get_config
from utils.model_checker import (
    get_all_available_models,
    get_all_models_info,
    check_model_available,
    scan_available_models,
    TaskComplexity,
    ModelInfo
)
from infrastructure.model_router import ModelSelection
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.logger import get_logger
from backend.sse_manager import SSEManager
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState
from infrastructure.model_router import get_model_router, reset_model_router
from infrastructure.workflow_nodes import (
    _is_streaming_enabled,
    intent_node,
    researcher_node,
    validator_node,
    stream_planner_node,
    stream_generator_node,
    stream_coder_node,
    stream_debugger_node,
    stream_fixer_node,
    stream_reflection_node,
    stream_critic_node
)


logger = get_logger()


router = APIRouter(prefix="/api", tags=["agents"])

# ========== КОНСТАНТЫ ==========

# Сообщение приветствия (единый источник истины)
GREETING_MESSAGE = (
    "👋 Привет! Я локальная многоагентная система генерации кода.\n\n"
    "Я могу помочь вам:\n"
    "• Создать новый код (create)\n"
    "• Изменить существующий код (modify)\n"
    "• Найти и исправить ошибки (debug)\n"
    "• Оптимизировать код (optimize)\n"
    "• Объяснить как работает код (explain)\n"
    "• Написать тесты (test)\n"
    "• Рефакторить код (refactor)\n\n"
    "Просто опишите задачу, и я помогу вам!"
)

# Сообщение помощи
HELP_MESSAGE = (
    "🚀 Да, я могу помочь! Я — локальная многоагентная система генерации кода.\n\n"
    "**Мои возможности:**\n\n"
    "📝 **Создание кода:**\n"
    "  • Функции, классы, модули\n"
    "  • API endpoints, CLI утилиты\n"
    "  • Полные скрипты и программы\n\n"
    "🔧 **Работа с существующим кодом:**\n"
    "  • Исправление ошибок (debug)\n"
    "  • Оптимизация производительности\n"
    "  • Рефакторинг структуры\n"
    "  • Добавление новых функций\n\n"
    "🧪 **Качество кода:**\n"
    "  • Генерация pytest тестов (TDD)\n"
    "  • Валидация через mypy, bandit\n"
    "  • Автоматическое исправление ошибок\n\n"
    "🔍 **Анализ проекта:**\n"
    "  • Обзор структуры и архитектуры\n"
    "  • Анализ кодовой базы\n"
    "  • Выявление проблемных мест\n\n"
    "💡 **Как использовать:**\n"
    "Просто опишите задачу на естественном языке, например:\n"
    "  • «напиши функцию сортировки»\n"
    "  • «создай калькулятор»\n"
    "  • «сделай парсер JSON»\n"
    "  • «проанализируй проект»\n\n"
    "Я понимаю русский и английский. Даже если вы напечатали в неправильной раскладке — я пойму! 😊"
)

# ========== ИМПОРТ ЗАВИСИМОСТЕЙ ==========

# MemoryAgent через DependencyContainer (Singleton)
from backend.dependencies import get_memory_agent as _get_memory_agent


# TaskRequest импортирован из backend.types


async def run_analyze_stream(
    task: str,
    model: str,
    temperature: float,
    project_path: Optional[str] = None,
    file_extensions: Optional[List[str]] = None,
    conversation_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Обрабатывает запрос на анализ проекта.
    
    Workflow:
    1. Индексирует кодовую базу через ContextEngine
    2. Собирает контекст релевантных файлов
    3. Генерирует отчёт через ChatAgent
    
    Args:
        task: Запрос пользователя на анализ
        model: Модель Ollama
        temperature: Температура генерации
        project_path: Путь к проекту для анализа
        file_extensions: Расширения файлов для индексации
        conversation_id: ID диалога для сохранения контекста
        
    Yields:
        SSE события с результатами анализа
    """
    import uuid
    from agents.researcher import ResearcherAgent
    
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or task_id
    
    config = get_config()
    
    # Проверяем, указан ли путь к проекту
    if not project_path:
        logger.warning("⚠️ Не указан путь к проекту для анализа")
        yield await SSEManager.stream_error(
            stage="analyze",
            error_message="Для анализа необходимо выбрать папку проекта. Используйте кнопку 'Выбрать папку' в IDE панели."
        )
        return
    
    # Отправляем stage_start для intent
    yield await SSEManager.stream_stage_start(
        stage="intent",
        message="Определяю намерение..."
    )
    await asyncio.sleep(0.02)
    
    yield await SSEManager.stream_stage_end(
        stage="intent",
        message="Намерение определено: analyze",
        result={"type": "analyze", "confidence": 0.95}
    )
    await asyncio.sleep(0.02)
    
    # Stage: indexing - индексация проекта
    yield await SSEManager.stream_stage_start(
        stage="indexing",
        message=f"Индексирую проект: {project_path}..."
    )
    await asyncio.sleep(0.02)
    
    try:
        # Собираем контекст из проекта
        researcher = ResearcherAgent()
        
        codebase_context = await asyncio.to_thread(
            researcher.research,
            query=task,
            intent_type="analyze",
            disable_web_search=True,
            project_path=project_path,
            file_extensions=file_extensions or [".py"]
        )
        
        if not codebase_context:
            logger.warning("⚠️ Не удалось собрать контекст из проекта")
            yield await SSEManager.stream_stage_end(
                stage="indexing",
                message="Проект проиндексирован, но релевантный контекст не найден",
                result={"context_length": 0}
            )
        else:
            yield await SSEManager.stream_stage_end(
                stage="indexing",
                message=f"Проект проиндексирован ({len(codebase_context)} символов контекста)",
                result={"context_length": len(codebase_context)}
            )
        await asyncio.sleep(0.02)
        
        # Stage: analysis - генерация отчёта
        yield await SSEManager.stream_stage_start(
            stage="analysis",
            message="Анализирую кодовую базу..."
        )
        await asyncio.sleep(0.02)
        
        # Выбираем модель через SmartModelRouter
        router = get_model_router()
        try:
            model_selection = router.select_model_for_complexity(
                complexity=TaskComplexity.COMPLEX,
                task_type="chat"
            )
            analyze_model = model_selection.model
            logger.info(f"🤖 Модель для анализа: {analyze_model}")
        except RuntimeError:
            analyze_model = model or config.default_model
        
        # Генерируем отчёт через ChatAgent
        chat_agent = get_chat_agent(model=analyze_model, temperature=temperature)
        
        analysis_response = await asyncio.to_thread(
            chat_agent.analyze_project,
            task=task,
            codebase_context=codebase_context or "Контекст не найден",
            project_path=project_path
        )
        
        analysis_text = analysis_response.content
        
        yield await SSEManager.stream_stage_end(
            stage="analysis",
            message=analysis_text,
            result={
                "type": "analyze",
                "analysis": analysis_text,
                "model_used": analysis_response.model_used
            }
        )
        await asyncio.sleep(0.02)
        
        # Сохраняем в историю диалога
        conv_memory = get_conversation_memory()
        conv_memory.add_message(conv_id, "user", task)
        conv_memory.add_message(conv_id, "assistant", analysis_text)
        
        # Финальный результат
        yield await SSEManager.stream_final_result(
            task_id=task_id,
            results={
                "task": task,
                "intent": {
                    "type": "analyze",
                    "confidence": 0.95,
                    "description": "Анализ проекта"
                },
                "analysis": analysis_text,
                "context_length": len(codebase_context) if codebase_context else 0,
                "project_path": project_path,
                "conversation_id": conv_id
            },
            metrics={
                "planning": 0.0,
                "research": 1.0,
                "testing": 0.0,
                "coding": 0.0,
                "overall": 0.8
            }
        )
        await asyncio.sleep(0.1)
        
        logger.info(f"✅ Анализ проекта завершён ({len(analysis_text)} символов)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа проекта: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="analyze",
            error_message=f"Ошибка анализа проекта: {str(e)}"
        )


async def run_chat_stream(
    task: str,
    model: str,
    temperature: float,
    conversation_id: Optional[str] = None,
    task_complexity: Optional[TaskComplexity] = None,
    intent_type: Optional[str] = None
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
    await asyncio.sleep(0.02)
    
    try:
        # Получаем ChatAgent с ЛЁГКОЙ моделью для быстрых ответов
        chat_agent = get_chat_agent(model=chat_model, temperature=temperature)
        response = chat_agent.chat(
            message=task,
            conversation_history=conversation_history
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
        await asyncio.sleep(0.02)
        
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
        await asyncio.sleep(0.1)
        
        logger.info(f"✅ Chat ответ отправлен ({len(response.content)} символов)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в chat режиме: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="chat",
            error_message=f"Ошибка генерации ответа: {str(e)}"
        )


async def run_workflow_stream_with_thinking(
    task: str,
    model: str,
    temperature: float,
    disable_web_search: bool,
    max_iterations: int,
    project_path: Optional[str] = None,
    file_extensions: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """DEPRECATED: Запускает workflow с real-time стримингом <think> блоков.
    
    ⚠️ УСТАРЕЛО: Теперь используется унифицированный workflow через граф LangGraph.
    Функция оставлена для обратной совместимости, но теперь просто вызывает run_workflow_stream().
    
    Использует стриминговые узлы для real-time вывода рассуждений
    reasoning моделей (DeepSeek-R1, QwQ).
    
    Включается через config.toml: [streaming] use_streaming_agents = true
    
    Args:
        task: Текст задачи
        model: Модель Ollama
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций
        project_path: Путь к проекту
        file_extensions: Расширения файлов
        
    Yields:
        SSE события включая thinking_* для <think> блоков
    """
    # Теперь используем унифицированный workflow через граф
    # Граф сам выберет стриминговые узлы на основе флага use_streaming_agents
    logger.info("⚠️ run_workflow_stream_with_thinking() устарела, используем унифицированный workflow")
    async for event in run_workflow_stream(
        task=task,
        model=model,
        temperature=temperature,
        disable_web_search=disable_web_search,
        max_iterations=max_iterations,
        project_path=project_path,
        file_extensions=file_extensions
    ):
        yield event


async def run_workflow_stream(
    task: str,
    model: str,
    temperature: float,
    disable_web_search: bool,
    max_iterations: int,
    project_path: Optional[str] = None,
    file_extensions: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """Запускает workflow агентов с SSE стримингом через LangGraph.
    
    Args:
        task: Текст задачи
        model: Модель Ollama (будет проверена на доступность)
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций (ограничено до 5)
        project_path: Путь к проекту для индексации кодовой базы (опционально)
        file_extensions: Расширения файлов для индексации (опционально)
        
    Yields:
        SSE события в формате text/event-stream
    """
    # Импорты для EventStore (вынесены наверх для избежания проблем с областью видимости)
    # SSEManager уже импортирован глобально на строке 35
    from infrastructure.event_store import get_event_store, EventStore
    
    task_id = str(uuid.uuid4())
    
    # Создаём очередь событий для реального времени
    event_queue = EventStore.get_event_queue(task_id)
    
    # Очередь для SSE событий от фоновой задачи
    sse_queue: asyncio.Queue = asyncio.Queue()
    
    # Флаг для остановки фоновой задачи
    stop_realtime_streaming = asyncio.Event()
    
    # Фоновая задача для отправки событий в реальном времени
    async def stream_events_realtime():
        """Отправляет события из очереди в SSE поток в реальном времени."""
        try:
            while not stop_realtime_streaming.is_set():
                try:
                    # Ждём событие с таймаутом
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    
                    # Преобразуем событие в SSE формат
                    if event.event_type.startswith("thinking_"):
                        # thinking события уже в формате SSE строки от ReasoningStreamManager
                        sse_event = event.data if isinstance(event.data, str) else await SSEManager.send_event(event.event_type, {"content": event.data})
                    elif event.event_type in ("plan_chunk", "test_chunk", "code_chunk"):
                        sse_event = await SSEManager.send_event(event.event_type, {"chunk": event.data})
                    else:
                        sse_event = await SSEManager.send_event(event.event_type, {"data": event.data})
                    
                    # Сохраняем SSE событие в очередь для основного генератора
                    await sse_queue.put(sse_event)
                    logger.debug(f"📤 Событие готово к отправке: {event.event_type}")
                    
                except asyncio.TimeoutError:
                    # Таймаут - продолжаем проверку
                    continue
                except Exception as e:
                    logger.error(f"❌ Ошибка в stream_events_realtime: {e}", error=e)
                    break
        except asyncio.CancelledError:
            logger.debug("🛑 stream_events_realtime отменён")
        finally:
            # Гарантируем что очередь будет очищена даже при ошибке
            logger.debug("🧹 stream_events_realtime завершён, очищаем очередь")
            # Очищаем оставшиеся события из очереди
            while not sse_queue.empty():
                try:
                    sse_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
    
    # Запускаем фоновую задачу
    realtime_task: Optional[asyncio.Task] = None
    try:
        realtime_task = asyncio.create_task(stream_events_realtime())
    except Exception as e:
        logger.error(f"❌ Ошибка создания фоновой задачи: {e}", error=e)
        realtime_task = None
    
    # БЫСТРАЯ ПРОВЕРКА ПРИВЕТСТВИЯ БЕЗ ИНИЦИАЛИЗАЦИИ WORKFLOW
    from agents.intent import IntentAgent
    if IntentAgent.is_greeting_fast(task):
        logger.info("🚀 Обнаружено приветствие - быстрый ответ без workflow")
        
        # АДАПТИВНЫЕ ЗАДЕРЖКИ: отправляем события с задержками для гарантии доставки frontend
        # Задержки адаптированы под скорость обработки событий frontend
        logger.info("📤 Отправляю stage_start для intent (greeting)")
        event1 = await SSEManager.stream_stage_start(
            stage="intent",
            message="Определяю намерение..."
        )
        yield event1
        await asyncio.sleep(0.02)  # Адаптивная задержка для stage_start
        logger.info(f"✅ Отправлено stage_start, длина: {len(event1)}")
        
        logger.info("📤 Отправляю stage_end для intent (greeting)")
        event2 = await SSEManager.stream_stage_end(
            stage="intent",
            message="Намерение определено: greeting",
            result={"type": "greeting", "confidence": 0.95}
        )
        yield event2
        await asyncio.sleep(0.02)  # Адаптивная задержка для stage_end
        logger.info(f"✅ Отправлено stage_end для intent, длина: {len(event2)}")
        
        logger.info("📤 Отправляю greeting stage_end")
        event3 = await SSEManager.stream_stage_end(
            stage="greeting",
            message=GREETING_MESSAGE,
            result={"type": "greeting", "message": GREETING_MESSAGE}
        )
        yield event3
        await asyncio.sleep(0.02)  # Адаптивная задержка для greeting
        logger.info(f"✅ Отправлено greeting, длина: {len(event3)}")
        
        logger.info("📤 Отправляю final_result (complete) для greeting")
        event4 = await SSEManager.stream_final_result(
            task_id=task_id,
            results={
                "task": task,
                "intent": {
                    "type": "greeting",
                    "confidence": 0.95,
                    "description": "Приветствие пользователя"
                },
                "greeting_message": GREETING_MESSAGE  # Добавляем greeting message для frontend
            },
            metrics={
                "planning": 0.0,
                "research": 0.0,
                "testing": 0.0,
                "coding": 0.0,
                "overall": 0.0
            }
        )
        yield event4
        await asyncio.sleep(0.3)  # Увеличенная задержка перед завершением - даем время frontend обработать greeting stage_end
        logger.info(f"✅ Отправлено complete, длина: {len(event4)}")
        logger.info("✅ Все события для greeting отправлены")
        return  # Выходим БЕЗ инициализации workflow
    
    # Ограничиваем max_iterations
    config = get_config()
    max_iterations = min(max_iterations, config.max_iterations, 5)
    
    # ПРОВЕРКА ПАМЯТИ: ищем идентичную/очень похожую задачу
    from backend.dependencies import get_memory_agent
    memory_agent = get_memory_agent()
    
    # Ищем очень похожую задачу (схожесть >= 0.85, успех >= 0.8)
    # Не фильтруем по intent на этом этапе - проверяем по тексту задачи
    similar_task = await asyncio.to_thread(
        memory_agent.find_exact_or_very_similar_task,
        query=task,
        intent_type=None,  # Не фильтруем по intent - проверяем по схожести текста
        min_success=0.8,
        similarity_threshold=0.85
    )
    
    if similar_task:
        similarity = similar_task.get("similarity", 0.0)
        success = similar_task.get("success", 0.0)
        has_code = similar_task.get("has_code", False)
        
        logger.info(
            f"🎯 Найдена очень похожая задача в памяти "
            f"(схожесть: {similarity:.2f}, успех: {success:.2f}, код: {'есть' if has_code else 'нет'})"
        )
        
        # Если схожесть очень высокая (>= 0.9) и успех высокий, предлагаем использовать готовое решение
        if similarity >= 0.9 and success >= 0.85 and has_code:
            logger.info("✅ Задача уже решалась успешно - используем готовое решение из памяти")
            
            # Отправляем события о найденном решении
            yield await SSEManager.stream_stage_start(
                stage="memory_check",
                message="Проверяю память..."
            )
            await asyncio.sleep(0.02)
            
            yield await SSEManager.stream_stage_end(
                stage="memory_check",
                message=f"Найдено готовое решение (схожесть: {similarity:.1%})",
                result={"similarity": similarity, "success": success}
            )
            await asyncio.sleep(0.02)
            
            # Извлекаем код и план из памяти
            code_preview = similar_task.get("code_preview", similar_task.get("code", ""))
            plan_preview = similar_task.get("plan_preview", similar_task.get("plan", ""))
            
            # Формируем сообщение для пользователя
            memory_message = (
                f"🎯 Найдено готовое решение для похожей задачи!\n\n"
                f"**Исходная задача:** {similar_task.get('task', '')[:200]}...\n"
                f"**Успешность:** {success:.1%}\n"
                f"**Схожесть:** {similarity:.1%}\n\n"
            )
            
            if plan_preview:
                memory_message += f"**План из памяти:**\n{plan_preview[:500]}...\n\n"
            
            if code_preview:
                memory_message += f"**Код из памяти:**\n```\n{code_preview[:1000]}...\n```\n\n"
            
            memory_message += (
                "💡 Система может использовать это решение или создать новое. "
                "Продолжаю с полным циклом для адаптации под текущую задачу."
            )
            
            yield await SSEManager.stream_stage_end(
                stage="memory_reuse",
                message=memory_message,
                result={
                    "similarity": similarity,
                    "success": success,
                    "has_code": has_code,
                    "code_preview": code_preview[:500] if code_preview else "",
                    "plan_preview": plan_preview[:300] if plan_preview else ""
                }
            )
            await asyncio.sleep(0.02)
            
            # ПРОДОЛЖАЕМ с workflow, но добавим информацию из памяти в контекст
            # Это позволит системе использовать готовое решение как основу
            logger.info("🔄 Продолжаю workflow с контекстом из памяти")
        else:
            logger.info(f"ℹ️ Найдена похожая задача, но схожесть недостаточна для пропуска workflow (схожесть: {similarity:.2f})")
    
    # УМНЫЙ ВЫБОР МОДЕЛИ:
    # 1. Сначала определяем сложность задачи через Intent (быстрая эвристика)
    # 2. Выбираем модель через SmartModelRouter на основе сложности
    
    model_to_use = (model.strip() if model and isinstance(model, str) and model.strip() else None)
    task_complexity = TaskComplexity.MEDIUM  # По умолчанию medium
    
    # Быстрая эвристика для определения сложности без полного LLM вызова
    intent_agent = IntentAgent(lazy_llm=True)
    task_complexity = intent_agent._estimate_complexity_heuristic(task)
    logger.info(f"📊 Определена сложность задачи: {task_complexity.value}")
    
    # Используем SmartModelRouter для выбора модели
    router = get_model_router()
    
    try:
        if model_to_use:
            # Проверяем, подходит ли указанная модель для сложности
            if check_model_available(model_to_use):
                model_selection = router.select_model_for_complexity(
                    complexity=task_complexity,
                    task_type="coding",
                    preferred_model=model_to_use
                )
                model_to_use = model_selection.model
                logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
            else:
                logger.warning(f"⚠️ Модель {model_to_use} недоступна, выбираю оптимальную")
                model_selection = router.select_model_for_complexity(
                    complexity=task_complexity,
                    task_type="coding"
                )
                model_to_use = model_selection.model
                logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
        else:
            # Автоматический выбор на основе сложности
            model_selection = router.select_model_for_complexity(
                complexity=task_complexity,
                task_type="coding"
            )
            model_to_use = model_selection.model
            logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
            
    except RuntimeError as e:
        logger.error(f"❌ {e}")
        yield await SSEManager.stream_error(
            stage="initialization",
            error_message=str(e)
        )
        return
    
    # Создаём начальный state
    initial_state: AgentState = {
        "task": task,
        "max_iterations": max_iterations,
        "disable_web_search": disable_web_search,
        "model": model_to_use,
        "temperature": temperature,
        # Режим и диалог
        "interaction_mode": "code",  # В этой функции всегда code режим
        "conversation_id": None,
        "conversation_history": None,
        "chat_response": None,
        # Codebase indexing
        "project_path": project_path,
        "file_extensions": file_extensions,
        # Результаты агентов
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
        "critic_report": None,
        "iteration": 0,
        "task_id": task_id,
        "enable_sse": True,  # Флаг для SSE стриминга
        "sse_events": None,  # DEPRECATED: Используйте event_references
        "event_references": None,  # Ссылки на события в EventStore
        "file_path": None,
        "file_context": None
    }
    
    # Создаём граф
    graph = create_workflow_graph()
    
    try:
        # Запускаем граф с стримингом
        async for event in graph.astream(initial_state):
            # Сначала проверяем очередь SSE событий из фоновой задачи (real-time стриминг)
            # Проверяем несколько раз для более быстрой отправки
            for _ in range(10):  # Проверяем до 10 событий за итерацию
                if sse_queue.empty():
                    break
                try:
                    sse_event = sse_queue.get_nowait()
                    yield sse_event
                    await asyncio.sleep(0.001)  # Небольшая задержка для плавности
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка отправки realtime SSE события: {e}")
            
            # Обрабатываем события графа
            # event - это словарь с ключами узлов и их обновлениями state
            for node_name, node_state in event.items():
                # Если узел использовал стриминговый адаптер, получаем события из EventStore
                event_references = node_state.get("event_references", [])
                if event_references:
                    # Получаем события из EventStore по ссылкам
                    # get_event_store уже импортирован в начале функции
                    session_id = initial_state.get("task_id") or initial_state.get("session_id") or "default"
                    event_store = await get_event_store(session_id)
                    
                    # Получаем только новые события (последние N ссылок)
                    existing_refs = initial_state.get("event_references", [])
                    new_refs = [ref for ref in event_references if ref not in existing_refs]
                    
                    if new_refs:
                        stored_events = await event_store.get_events(new_refs)
                        logger.info(f"📤 Отправляю {len(stored_events)} SSE событий из узла {node_name}")
                        
                        # Преобразуем события в SSE формат и отправляем
                        # SSEManager уже импортирован в начале файла
                        for stored_event in stored_events:
                            # thinking события уже в формате SSE строки от ReasoningStreamManager
                            if stored_event.event_type == "thinking":
                                # data уже содержит готовую SSE строку
                                sse_event = stored_event.data if isinstance(stored_event.data, str) else await SSEManager.send_event("thinking", {"content": stored_event.data})
                            elif stored_event.event_type in ("plan_chunk", "test_chunk", "code_chunk"):
                                sse_event = await SSEManager.send_event(stored_event.event_type, {"chunk": stored_event.data})
                            else:
                                sse_event = await SSEManager.send_event(stored_event.event_type, {"data": stored_event.data})
                            yield sse_event
                        
                        # Сохраняем ссылки в общем state для отслеживания
                        if "event_references" not in initial_state:
                            initial_state["event_references"] = []
                        initial_state["event_references"].extend(new_refs)
                
                # Отправляем SSE события на основе узла (для обычных узлов)
                if node_name == "intent":
                    intent_result = node_state.get("intent_result")
                    if intent_result:
                        logger.info(f"📤 Отправляю stage_start для intent")
                        event1 = await SSEManager.stream_stage_start(
                            stage="intent",
                            message="Определяю намерение..."
                        )
                        yield event1
                        logger.info(f"✅ Отправлено stage_start, длина: {len(event1)}")
                        
                        logger.info(f"📤 Отправляю stage_end для intent")
                        event2 = await SSEManager.stream_stage_end(
                            stage="intent",
                            message=f"Намерение определено: {intent_result.type}",
                            result={"type": intent_result.type, "confidence": intent_result.confidence}
                        )
                        yield event2
                        logger.info(f"✅ Отправлено stage_end, длина: {len(event2)}")
                        
                        # Если greeting или help (но НЕ analyze), отправляем специальное сообщение и завершаем
                        if intent_result.type in ("greeting", "help"):
                                message = GREETING_MESSAGE if intent_result.type == "greeting" else HELP_MESSAGE
                                stage_name = intent_result.type
                                
                                logger.info(f"📤 Отправляю {stage_name} stage_end")
                                event3 = await SSEManager.stream_stage_end(
                                    stage=stage_name,
                                    message=message,
                                    result={"type": stage_name, "message": message}
                                )
                                yield event3
                                logger.info(f"✅ Отправлено {stage_name}, длина: {len(event3)}")
                                
                                logger.info(f"📤 Отправляю final_result (complete)")
                                event4 = await SSEManager.stream_final_result(
                                    task_id=task_id,
                                    results={
                                        "task": task,
                                        "intent": {
                                            "type": intent_result.type,
                                            "confidence": intent_result.confidence,
                                            "description": intent_result.description
                                        },
                                        "greeting_message": message
                                    },
                                    metrics={
                                        "planning": 0.0,
                                        "research": 0.0,
                                        "testing": 0.0,
                                        "coding": 0.0,
                                        "overall": 0.0
                                    }
                                )
                                yield event4
                                logger.info(f"✅ Отправлено complete, длина: {len(event4)}")
                                # Даем время на отправку последнего события перед завершением
                                await asyncio.sleep(0.2)
                                break  # Выходим из цикла astream вместо return
                
                elif node_name == "planner":
                    plan = node_state.get("plan", "")
                    if plan:
                        yield await SSEManager.stream_stage_start(
                            stage="planning",
                            message="Создаю план выполнения..."
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="planning",
                            message="План создан",
                            result={"plan_length": len(plan)}
                        )
                
                elif node_name == "researcher":
                    context = node_state.get("context", "")
                    if context:
                        yield await SSEManager.stream_stage_start(
                            stage="research",
                            message="Ищу контекст в базе знаний (RAG)..."
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="research",
                            message="Контекст собран",
                            result={"context_length": len(context)}
                        )
                
                elif node_name == "test_generator":
                    tests = node_state.get("tests", "")
                    if tests:
                        yield await SSEManager.stream_stage_start(
                            stage="testing",
                            message="Генерирую тесты..."
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="testing",
                            message="Тесты сгенерированы",
                            result={"tests_length": len(tests)}
                        )
                
                elif node_name == "coder":
                    code = node_state.get("code", "")
                    if code:
                        yield await SSEManager.stream_stage_start(
                            stage="coding",
                            message="Генерирую код..."
                        )
                        # Отправляем код как чанк для отображения в IDE
                        yield await SSEManager.stream_code_chunk(
                            chunk=code,
                            is_final=True,
                            metadata={"stage": "coding"}
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="coding",
                            message="Код сгенерирован",
                            result={"code_length": len(code), "code": code}  # Добавляем код в result
                        )
                
                elif node_name == "validator":
                    validation_results = node_state.get("validation_results", {})
                    yield await SSEManager.stream_stage_start(
                        stage="validation",
                        message="Валидирую код (pytest, mypy, bandit)..."
                    )
                    yield await SSEManager.stream_stage_end(
                        stage="validation",
                        message="Валидация завершена",
                        result=validation_results
                    )
                
                elif node_name == "debugger":
                    debug_result = node_state.get("debug_result")
                    iteration = node_state.get("iteration", 0)
                    if debug_result:
                        yield await SSEManager.stream_stage_start(
                            stage="debug",
                            message=f"Анализирую ошибки (итерация {iteration})..."
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="debug",
                            message=f"Анализ завершён: {debug_result.error_summary}",
                            result={
                                "error_type": debug_result.error_type,
                                "confidence": debug_result.confidence,
                                "error_summary": debug_result.error_summary
                            }
                        )
                
                elif node_name == "fixer":
                    code = node_state.get("code", "")
                    iteration = node_state.get("iteration", 0)
                    if code:
                        yield await SSEManager.stream_stage_start(
                            stage="fixing",
                            message=f"Исправляю код по инструкциям (итерация {iteration})..."
                        )
                        # Отправляем исправленный код для обновления IDE
                        yield await SSEManager.stream_code_chunk(
                            chunk=code,
                            is_final=True,
                            metadata={"stage": "fixing", "iteration": iteration}
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="fixing",
                            message="Код исправлен",
                            result={"code_length": len(code), "code": code}
                        )
                
                elif node_name == "reflection":
                    reflection_result = node_state.get("reflection_result")
                    if reflection_result:
                        yield await SSEManager.stream_stage_start(
                            stage="reflection",
                            message="Анализирую результаты..."
                        )
                        
                        # Сохраняем артефакты
                        artifact_saver = ArtifactSaver()
                        artifacts_dir = None
                        try:
                            artifacts_dir = artifact_saver.save_all_artifacts(
                                task=task,
                                code=node_state.get("code", ""),
                                tests=node_state.get("tests", ""),
                                reflection_data={
                                    "planning_score": reflection_result.planning_score,
                                    "research_score": reflection_result.research_score,
                                    "testing_score": reflection_result.testing_score,
                                    "coding_score": reflection_result.coding_score,
                                    "overall_score": reflection_result.overall_score,
                                    "analysis": reflection_result.analysis,
                                    "improvements": reflection_result.improvements,
                                    "should_retry": reflection_result.should_retry
                                },
                                metrics={
                                    "planning": reflection_result.planning_score,
                                    "research": reflection_result.research_score,
                                    "testing": reflection_result.testing_score,
                                    "coding": reflection_result.coding_score,
                                    "overall": reflection_result.overall_score
                                }
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка сохранения артефактов: {e}", error=e)
                        
                        yield await SSEManager.stream_stage_end(
                            stage="reflection",
                            message="Рефлексия завершена",
                            result={
                                "planning_score": reflection_result.planning_score,
                                "research_score": reflection_result.research_score,
                                "testing_score": reflection_result.testing_score,
                                "coding_score": reflection_result.coding_score,
                                "overall_score": reflection_result.overall_score,
                                "artifacts_dir": str(artifacts_dir) if artifacts_dir else None
                            }
                        )
                
                elif node_name == "critic":
                    critic_report = node_state.get("critic_report")
                    reflection_result = node_state.get("reflection_result")
                    
                    # Critic stage
                    yield await SSEManager.stream_stage_start(
                        stage="critic",
                        message="Критический анализ кода..."
                    )
                    
                    if critic_report:
                        yield await SSEManager.stream_stage_end(
                            stage="critic",
                            message=critic_report.summary,
                            result={
                                "overall_score": critic_report.overall_score,
                                "issues_count": len(critic_report.issues),
                                "issues": [
                                    {
                                        "category": issue.category,
                                        "severity": issue.severity,
                                        "location": issue.location,
                                        "description": issue.description,
                                        "evidence": issue.evidence,
                                        "suggestion": issue.suggestion
                                    }
                                    for issue in critic_report.issues
                                ],
                                "strengths": critic_report.strengths
                            }
                        )
                    else:
                        yield await SSEManager.stream_stage_end(
                            stage="critic",
                            message="Критический анализ пропущен",
                            result={"overall_score": 0.0, "issues_count": 0, "issues": [], "strengths": []}
                        )
                    
                    # Подсчитываем токены
                    estimated_tokens = estimate_workflow_tokens(
                        task=task,
                        plan=node_state.get("plan", ""),
                        context=node_state.get("context", ""),
                        tests=node_state.get("tests", ""),
                        code=node_state.get("code", ""),
                        prompts_used=[]
                    )
                    
                    token_status = check_token_limit(
                        current_tokens=estimated_tokens,
                        warning_threshold=config.max_tokens_warning,
                        max_tokens=50000
                    )
                    
                    if token_status["warning"]:
                        yield await SSEManager.send_event(
                            "warning",
                            {
                                "message": token_status["message"],
                                "tokens": estimated_tokens
                            }
                        )
                    
                    # Финальный результат с critic данными
                    critic_score = critic_report.overall_score if critic_report else 0.0
                    reflection_score = reflection_result.overall_score if reflection_result else 0.0
                    
                    # Отправляем оставшиеся события из очереди перед финальным результатом
                    while not sse_queue.empty():
                        try:
                            sse_event = sse_queue.get_nowait()
                            yield sse_event
                        except asyncio.QueueEmpty:
                            break
                    
                    # Останавливаем фоновую задачу
                    stop_realtime_streaming.set()
                    realtime_task.cancel()
                    try:
                        await realtime_task
                    except asyncio.CancelledError:
                        pass
                    
                    # Очищаем очередь событий
                    EventStore.remove_event_queue(task_id)
                    
                    yield await SSEManager.stream_final_result(
                task_id=task_id,
                results={
                            "task": task,
                            "intent": {
                                "type": node_state.get("intent_result").type if node_state.get("intent_result") else "unknown",
                                "confidence": node_state.get("intent_result").confidence if node_state.get("intent_result") else 0.0,
                                "description": node_state.get("intent_result").description if node_state.get("intent_result") else ""
                            },
                            "plan": node_state.get("plan", ""),
                            "context": node_state.get("context", ""),
                            "tests": node_state.get("tests", ""),
                            "code": node_state.get("code", ""),
                            "validation": node_state.get("validation_results", {}),
                            "reflection": {
                                "planning_score": reflection_result.planning_score if reflection_result else 0.0,
                                "research_score": reflection_result.research_score if reflection_result else 0.0,
                                "testing_score": reflection_result.testing_score if reflection_result else 0.0,
                                "coding_score": reflection_result.coding_score if reflection_result else 0.0,
                                "overall_score": reflection_score,
                                "analysis": reflection_result.analysis if reflection_result else "",
                                "improvements": reflection_result.improvements if reflection_result else "",
                                "should_retry": reflection_result.should_retry if reflection_result else False
                            },
                            "critic": {
                                "score": critic_score,
                                "summary": critic_report.summary if critic_report else "",
                                "issues": [
                                    {
                                        "category": i.category,
                                        "severity": i.severity,
                                        "description": i.description,
                                        "suggestion": i.suggestion
                                    }
                                    for i in (critic_report.issues[:5] if critic_report else [])
                                ],
                                "strengths": critic_report.strengths if critic_report else []
                            },
                            "tokens_used": estimated_tokens,
                            "token_warning": token_status["warning"]
                        },
                        metrics={
                            "planning": reflection_result.planning_score if reflection_result else 0.0,
                            "research": reflection_result.research_score if reflection_result else 0.0,
                            "testing": reflection_result.testing_score if reflection_result else 0.0,
                            "coding": reflection_result.coding_score if reflection_result else 0.0,
                            "critic": critic_score,
                            "overall": (reflection_score + critic_score) / 2
                        }
                    )
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения workflow: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="workflow",
            error_message=f"Ошибка выполнения workflow: {str(e)}",
            error_details={"exception_type": type(e).__name__}
        )
    finally:
        # Останавливаем фоновую задачу и очищаем ресурсы
        stop_realtime_streaming.set()
        if realtime_task and not realtime_task.done():
            realtime_task.cancel()
            try:
                await asyncio.wait_for(realtime_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при отмене фоновой задачи: {e}")
        
        # Очищаем сессию из EventStore
        try:
            await EventStore.cleanup_session(task_id)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке сессии EventStore: {e}")
        
        # Удаляем очередь событий
        EventStore.remove_event_queue(task_id)


@router.post("/tasks")
async def create_task(request: TaskRequest) -> Dict[str, str]:
    """Создаёт задачу и возвращает task_id для SSE подключения.
    
    Args:
        request: Запрос с параметрами задачи
        
    Returns:
        Словарь с task_id
    """
    task_id = str(uuid.uuid4())
    
    # Запускаем workflow в фоне (через SSE endpoint)
    # В реальности task_id будет использоваться для получения результатов через SSE
    
    return {
        "task_id": task_id,
        "status": "created",
        "message": "Задача создана. Подключитесь к /api/stream/{task_id} для получения результатов."
    }


@router.get("/models")
async def get_models() -> Dict[str, Any]:
    """Возвращает список доступных моделей Ollama с детальной информацией.
    
    Модели отсортированы по качеству (лучшие для кода первые).
    Включает информацию о размере, специализации и рекомендациях.
    
    Returns:
        Словарь с списком моделей и их характеристиками
    """
    # Сканируем модели заново для актуальности
    models_info = get_all_models_info()
    
    # Формируем ответ с детальной информацией
    models_list = []
    for info in models_info:
        # Определяем рекомендацию по сложности
        if info.estimated_quality >= 0.7:
            recommended_for = ["complex", "medium", "simple"]
        elif info.estimated_quality >= 0.5:
            recommended_for = ["medium", "simple"]
        else:
            recommended_for = ["simple"]
        
        models_list.append({
            "name": info.name,
            "size_gb": round(info.size_gb, 2),
            "parameters": info.parameter_size,
            "family": info.family,
            "is_coder": info.is_coder,
            "is_reasoning": info.is_reasoning,  # Reasoning модель с встроенным CoT
            "quality_score": info.estimated_quality,
            "recommended_for": recommended_for
        })
    
    # Также возвращаем простой список имён для обратной совместимости
    model_names = [m["name"] for m in models_list]
    
    return {
        "models": model_names,  # Для обратной совместимости
        "models_detailed": models_list,  # Детальная информация
        "count": len(models_list),
        "recommendations": {
            "simple": _get_recommendation_for_complexity(models_info, TaskComplexity.SIMPLE),
            "medium": _get_recommendation_for_complexity(models_info, TaskComplexity.MEDIUM),
            "complex": _get_recommendation_for_complexity(models_info, TaskComplexity.COMPLEX)
        }
    }


def _get_recommendation_for_complexity(
    models: List[ModelInfo], 
    complexity: TaskComplexity
) -> Optional[str]:
    """Возвращает рекомендуемую модель для сложности."""
    min_quality = {
        TaskComplexity.SIMPLE: 0.3,
        TaskComplexity.MEDIUM: 0.55,
        TaskComplexity.COMPLEX: 0.7
    }
    
    threshold = min_quality[complexity]
    suitable = [m for m in models if m.estimated_quality >= threshold and 'embed' not in m.name.lower()]
    
    if suitable:
        # Для simple предпочитаем быстрые, для complex - качественные
        if complexity == TaskComplexity.SIMPLE:
            # Выбираем минимально подходящую (быстрее)
            return min(suitable, key=lambda m: m.estimated_quality).name
        else:
            # Выбираем лучшую по качеству
            return max(suitable, key=lambda m: m.estimated_quality).name
    
    # Если нет подходящих, возвращаем лучшую из доступных
    non_embed = [m for m in models if 'embed' not in m.name.lower()]
    if non_embed:
        return max(non_embed, key=lambda m: m.estimated_quality).name
    
    return models[0].name if models else None


@router.post("/models/refresh")
async def refresh_models() -> Dict[str, Any]:
    """Принудительно обновляет список моделей Ollama.
    
    Используйте после добавления/удаления моделей через ollama pull/rm.
    
    Returns:
        Обновлённый список моделей
    """
    reset_model_router()
    return await get_models()


@router.get("/browse-folder")
async def browse_folder(start_path: Optional[str] = None) -> Dict[str, Any]:
    """Открывает системный диалог выбора папки.
    
    Использует нативные средства ОС:
    - macOS: osascript (AppleScript)
    - Windows: PowerShell
    - Linux: zenity или kdialog
    
    Args:
        start_path: Начальная директория для диалога (опционально)
        
    Returns:
        Словарь с выбранным путём или cancelled если отменено
    """
    import asyncio
    import os
    import platform
    import subprocess
    
    def _open_folder_dialog_native(initial_dir: Optional[str] = None) -> Optional[str]:
        """Открывает нативный диалог выбора папки."""
        system = platform.system()
        initial = initial_dir if initial_dir and os.path.isdir(initial_dir) else os.path.expanduser("~")
        
        try:
            if system == "Darwin":  # macOS
                # AppleScript для нативного диалога
                script = f'''
                    set defaultFolder to POSIX file "{initial}"
                    try
                        set selectedFolder to choose folder with prompt "Выберите папку проекта" default location defaultFolder
                        return POSIX path of selectedFolder
                    on error
                        return ""
                    end try
                '''
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 минут на выбор
                )
                path = result.stdout.strip()
                # Убираем trailing slash если есть
                return path.rstrip("/") if path else None
                
            elif system == "Windows":
                # PowerShell для Windows
                script = f'''
                    Add-Type -AssemblyName System.Windows.Forms
                    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
                    $dialog.Description = "Выберите папку проекта"
                    $dialog.SelectedPath = "{initial}"
                    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                        Write-Output $dialog.SelectedPath
                    }}
                '''
                result = subprocess.run(
                    ["powershell", "-Command", script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                path = result.stdout.strip()
                return path if path else None
                
            else:  # Linux
                # Пробуем zenity (GNOME), потом kdialog (KDE)
                for cmd in [
                    ["zenity", "--file-selection", "--directory", f"--filename={initial}/", "--title=Выберите папку проекта"],
                    ["kdialog", "--getexistingdirectory", initial, "--title", "Выберите папку проекта"]
                ]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            return result.stdout.strip()
                    except FileNotFoundError:
                        continue
                        
                logger.warning("⚠️ Не найден zenity или kdialog для выбора папки")
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning("⏱️ Таймаут диалога выбора папки")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка диалога выбора папки: {e}")
            return None
    
    # Запускаем диалог в отдельном потоке
    selected_path = await asyncio.to_thread(_open_folder_dialog_native, start_path)
    
    if selected_path:
        logger.info(f"📂 Выбрана папка: {selected_path}")
        return {
            "path": selected_path,
            "name": os.path.basename(selected_path),
            "exists": os.path.isdir(selected_path)
        }
    else:
        return {
            "path": None,
            "cancelled": True
        }


@router.get("/project-files")
async def get_project_files(
    path: str,
    extensions: Optional[str] = None,
    max_depth: int = 5
) -> Dict[str, Any]:
    """Возвращает структуру файлов проекта.
    
    Args:
        path: Путь к корневой папке проекта
        extensions: Расширения файлов через запятую (опционально)
        max_depth: Максимальная глубина сканирования
        
    Returns:
        Древовидная структура файлов и папок
    """
    import os
    
    if not path or not os.path.isdir(path):
        return {"error": "Путь не существует", "path": path}
    
    IGNORED_DIRS = {
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', 
        '.venv', 'venv', 'env', '.idea', '.vscode', 'dist', 'build',
        '.next', '.nuxt', 'coverage', '.pytest_cache', '.mypy_cache',
        '__pypackages__', '.tox', '.eggs', '.cache'
    }
    
    IGNORED_FILES = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes'}
    
    allowed_ext: set[str] | None = None
    if extensions:
        allowed_ext = {(e.strip() if e.strip().startswith('.') else f'.{e.strip()}').lower() 
                       for e in extensions.split(',')}
    
    def scan_dir(dir_path: str, depth: int = 0) -> Dict[str, Any]:
        """Рекурсивно сканирует директорию и возвращает структуру дерева."""
        result: Dict[str, Any] = {
            "name": os.path.basename(dir_path) or dir_path,
            "path": dir_path,
            "type": "directory",
            "children": []
        }
        
        if depth >= max_depth:
            result["truncated"] = True
            return result
        
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            result["error"] = "Нет доступа"
            return result
        
        dirs, files = [], []
        
        for entry in entries:
            entry_path = os.path.join(dir_path, entry)
            
            if os.path.isdir(entry_path):
                if entry not in IGNORED_DIRS and not entry.startswith('.'):
                    child = scan_dir(entry_path, depth + 1)
                    if child.get("children") or child.get("truncated"):
                        dirs.append(child)
            else:
                if entry not in IGNORED_FILES and not entry.startswith('.'):
                    ext = os.path.splitext(entry)[1].lower()
                    if allowed_ext is None or ext in allowed_ext:
                        files.append({
                            "name": entry,
                            "path": entry_path,
                            "type": "file",
                            "extension": ext,
                            "size": os.path.getsize(entry_path)
                        })
        
        result["children"] = dirs + files
        return result
    
    tree = scan_dir(path)
    
    def count_items(node: Dict[str, Any]) -> tuple[int, int]:
        """Подсчитывает количество файлов и директорий в дереве."""
        if node["type"] == "file":
            return 1, 0
        files, dirs = 0, 1
        for child in node.get("children", []):
            f, d = count_items(child)
            files += f
            dirs += d
        return files, dirs
    
    total_files, total_dirs = count_items(tree)
    
    return {
        "tree": tree,
        "stats": {
            "total_files": total_files,
            "total_directories": total_dirs - 1,
            "root_path": path
        }
    }


@router.get("/file-content")
async def get_file_content(path: str) -> Dict[str, Any]:
    """Читает содержимое файла.
    
    Args:
        path: Полный путь к файлу
        
    Returns:
        Содержимое файла
    """
    import os
    
    if not path or not os.path.isfile(path):
        return {"error": "Файл не найден", "path": path}
    
    try:
        # Ограничиваем размер файла (макс 1MB)
        size = os.path.getsize(path)
        if size > 1024 * 1024:
            return {"error": "Файл слишком большой (>1MB)", "path": path, "size": size}
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return {
            "path": path,
            "name": os.path.basename(path),
            "content": content,
            "size": size
        }
    except Exception as e:
        return {"error": str(e), "path": path}


@router.post("/index")
async def index_project(request: IndexProjectRequest) -> Dict[str, Any]:
    """Индексирует кодовую базу проекта для последующего поиска.
    
    Используется для индексации проекта перед анализом или генерацией кода.
    
    Args:
        request: Запрос с путём к проекту и расширениями файлов
    
    Returns:
        Статус индексации с количеством проиндексированных файлов
    """
    from infrastructure.context_engine import ContextEngine
    from pathlib import Path
    import asyncio
    
    project_path = request.project_path.strip()
    file_extensions = request.file_extensions or [".py"]
    
    project_path_obj = Path(project_path)
    if not project_path_obj.exists() or not project_path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Проект не найден или не является директорией: {project_path}"
        )
    
    # Нормализуем расширения (добавляем точку если отсутствует)
    normalized_extensions = []
    for ext in file_extensions:
        ext = ext.strip()
        if not ext.startswith('.'):
            ext = f'.{ext}'
        normalized_extensions.append(ext)
    
    try:
        # Создаём ContextEngine и индексируем проект
        context_engine = ContextEngine()
        
        # Индексация выполняется синхронно, запускаем в отдельном потоке
        index_result = await asyncio.to_thread(
            context_engine.index_project,
            project_path=project_path,
            extensions=normalized_extensions if normalized_extensions else None
        )
        
        # Подсчитываем количество файлов и чанков
        total_files = len(index_result)
        total_chunks = sum(len(chunks) for chunks in index_result.values())
        
        logger.info(f"✅ Проиндексирован проект {project_path}: {total_files} файлов, {total_chunks} чанков")
        
        return {
            "status": "success",
            "project_path": project_path,
            "indexed_files": total_files,
            "total_chunks": total_chunks,
            "extensions": normalized_extensions
        }
    except ValueError as e:
        logger.error(f"❌ Ошибка валидации при индексации: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка индексации проекта: {e}", error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка индексации проекта: {str(e)}"
        )


@router.get("/metrics/stages")
async def get_stage_metrics() -> Dict[str, Any]:
    """Возвращает метрики производительности по этапам workflow.
    
    Включает:
    - Результаты бенчмарка (скорость генерации, множитель)
    - Статистику по каждому этапу (среднее время, медиана, кол-во замеров)
    - Адаптивные оценки времени для текущего железа
    
    Returns:
        Словарь с метриками
    """
    from infrastructure.performance_metrics import get_performance_metrics
    
    metrics = get_performance_metrics()
    return metrics.get_metrics_summary()


@router.post("/metrics/benchmark")
async def run_benchmark(model: Optional[str] = None) -> Dict[str, Any]:
    """Запускает бенчмарк производительности LLM.
    
    Тестирует скорость генерации и обновляет коэффициент производительности.
    Результаты сохраняются и используются для адаптивных оценок времени.
    
    Args:
        model: Модель для тестирования (опционально, по умолчанию текущая)
        
    Returns:
        Результаты бенчмарка
    """
    from infrastructure.performance_metrics import get_performance_metrics
    
    metrics = get_performance_metrics()
    benchmark = await metrics.run_benchmark(model)
    
    return {
        "benchmark": benchmark.to_dict(),
        "message": f"Бенчмарк завершён: {benchmark.tokens_per_second:.1f} токенов/сек"
    }


def get_stream_params(
    task: str = Query(..., min_length=1, description="Текст задачи"),
    mode: str = Query(default="auto", description="Режим взаимодействия (auto, chat, code)"),
    model: str = Query(default="", description="Модель Ollama (пусто = авто-выбор)"),
    temperature: float = Query(default=0.25, ge=0.1, le=0.7, description="Температура генерации"),
    disable_web_search: bool = Query(default=False, description="Отключить веб-поиск"),
    max_iterations: int = Query(default=3, ge=1, le=5, description="Максимальное количество итераций"),
    conversation_id: Optional[str] = Query(default=None, description="ID диалога для сохранения контекста"),
    project_path: Optional[str] = Query(default=None, description="Путь к проекту для индексации кодовой базы"),
    file_extensions: Optional[str] = Query(default=None, description="Расширения файлов через запятую (например: .py,.js)")
) -> StreamQueryParams:
    """Зависимость для валидации query параметров /api/stream.
    
    Преобразует query параметры в валидированную Pydantic модель.
    """
    # Валидация mode
    try:
        mode_enum = InteractionMode(mode.lower())
        mode_value = mode_enum.value
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый режим: {mode}. Допустимые значения: auto, chat, code, plan, analyze"
        )
    
    return StreamQueryParams(
        task=task,
        mode=mode_value,
        model=model,
        temperature=temperature,
        disable_web_search=disable_web_search,
        max_iterations=max_iterations,
        conversation_id=conversation_id,
        project_path=project_path,
        file_extensions=file_extensions
    )


@router.get("/stream")
async def stream_task_results(
    params: StreamQueryParams = Depends(get_stream_params)
):
    """SSE endpoint для стриминга результатов выполнения задачи.
    
    Поддерживает режимы взаимодействия:
    - auto: Автоматический выбор режима
    - chat: Простой диалог без workflow
    - code: Полный workflow генерации кода
    
    Args:
        task: Текст задачи
        mode: Режим взаимодействия (auto, chat, code)
        model: Модель Ollama
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций
        conversation_id: ID диалога для сохранения контекста
        project_path: Путь к проекту для индексации кодовой базы (опционально)
        file_extensions: Расширения файлов через запятую, например ".py,.js" (опционально)
        
    Returns:
        StreamingResponse с SSE событиями
    """
    from fastapi.responses import StreamingResponse
    
    # Извлекаем параметры из валидированной модели
    task = params.task
    mode = params.mode.value if isinstance(params.mode, InteractionMode) else params.mode
    model = params.model
    temperature = params.temperature
    disable_web_search = params.disable_web_search
    max_iterations = params.max_iterations
    conversation_id = params.conversation_id
    project_path = params.project_path
    file_extensions = params.file_extensions
    
    # Парсим file_extensions из строки в список
    parsed_extensions: Optional[List[str]] = None
    if file_extensions:
        parsed_extensions = [ext.strip() for ext in file_extensions.split(",") if ext.strip()]
    
    async def generate() -> AsyncGenerator[str, None]:
        """Генератор SSE событий для потоковой обработки задачи."""
        try:
            event_count = 0
            selected_mode = mode
            detected_intent_type: Optional[str] = None
            detected_complexity: Optional[TaskComplexity] = None
            
            # ВАЖНО: Уважаем явно выбранный пользователем режим
            # Режим "chat" = диалог без генерации кода
            # Режим "code" = полный workflow с TDD
            # Режим "auto" = система сама определяет
            
            if mode == "chat":
                # Пользователь ЯВНО выбрал режим диалога — не переключаем на code
                selected_mode = "chat"
                intent_agent = IntentAgent(lazy_llm=True)
                detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                # Для диалога определяем intent только для выбора модели
                if IntentAgent.is_greeting_fast(task):
                    detected_intent_type = "greeting"
                    detected_complexity = TaskComplexity.SIMPLE
                logger.info(f"💬 Явный режим диалога, сложность: {detected_complexity.value}")
                
            elif mode == "code":
                # Пользователь ЯВНО выбрал режим генерации кода
                selected_mode = "code"
                intent_agent = IntentAgent(lazy_llm=True)
                detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                logger.info(f"🔧 Явный режим генерации кода, сложность: {detected_complexity.value}")
                
            elif mode == "auto":
                # Только в auto режиме система сама определяет режим
                intent_agent = IntentAgent(lazy_llm=True)
                
                # Быстрая проверка на greeting
                if IntentAgent.is_greeting_fast(task):
                    selected_mode = "chat"
                    detected_intent_type = "greeting"
                    detected_complexity = TaskComplexity.SIMPLE
                    logger.info("🚀 Быстрое определение: greeting → chat + SIMPLE")
                else:
                    # Эвристика: ключевые слова для генерации кода
                    task_lower = task.lower()
                    code_keywords = [
                        'напиши', 'создай', 'сделай', 'реализуй', 'сгенерируй',
                        'write', 'create', 'make', 'implement', 'generate',
                        'функци', 'класс', 'модуль', 'скрипт',
                        'function', 'class', 'module', 'script',
                        'исправ', 'отлад', 'debug', 'fix', 'оптимизир'
                    ]
                    
                    # Ключевые слова для диалога (НЕ генерация кода)
                    chat_keywords = [
                        'объясни', 'расскажи', 'что такое', 'как работает',
                        'explain', 'tell me', 'what is', 'how does',
                        'почему', 'зачем', 'когда', 'можно ли',
                        'why', 'when', 'can you', 'should i',
                        'посоветуй', 'подскажи', 'помоги понять',
                        # Запросы актуальной информации (realtime) — это тоже chat
                        'новост', 'событи', 'погод', 'курс', 'сегодня', 'вчера', 'завтра',
                        'news', 'weather', 'today', 'yesterday', 'tomorrow',
                        'что происходит', 'что случилось', 'что нового', 'какие',
                        "what's happening", 'latest', 'current'
                    ]
                    
                    has_code_keyword = any(kw in task_lower for kw in code_keywords)
                    has_chat_keyword = any(kw in task_lower for kw in chat_keywords)
                    
                    # Ключевые слова анализа проекта
                    analyze_keywords = [
                        'проанализируй', 'анализ', 'обзор', 'структур', 'архитектур',
                        'analyze', 'review', 'overview', 'structure', 'architecture',
                        'покажи проект', 'изучи проект', 'посмотри проект'
                    ]
                    has_analyze_keyword = any(kw in task_lower for kw in analyze_keywords)
                    
                    # Если есть chat-ключевые слова и НЕТ code-ключевых → диалог
                    if has_chat_keyword and not has_code_keyword and not has_analyze_keyword:
                        selected_mode = "chat"
                        detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                        detected_intent_type = "explain"
                        logger.info(f"💬 Обнаружены chat-ключевые слова → chat + {detected_complexity.value}")
                    elif has_analyze_keyword and not has_code_keyword:
                        # Анализ проекта — специальный режим
                        selected_mode = "analyze"
                        detected_complexity = TaskComplexity.COMPLEX
                        detected_intent_type = "analyze"
                        logger.info(f"🔍 Обнаружены analyze-ключевые слова → analyze + {detected_complexity.value}")
                    elif has_code_keyword:
                        selected_mode = "code"
                        detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                        logger.info(f"🔧 Обнаружены code-ключевые слова → code + {detected_complexity.value}")
                    else:
                        # Используем LLM для точного определения intent
                        intent_result = intent_agent.determine_intent(task)
                        selected_mode = intent_result.recommended_mode
                        detected_intent_type = intent_result.type
                        detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                        
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
            
            logger.info(f"🎯 Выбран режим: {selected_mode} (запрошен: {mode})")
            
            # Выбираем обработчик в зависимости от режима
            if selected_mode == "chat":
                stream_func = run_chat_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    conversation_id=conversation_id,
                    task_complexity=detected_complexity,
                    intent_type=detected_intent_type
                )
            elif detected_intent_type == "analyze" or selected_mode == "analyze":
                # Режим анализа проекта — собираем контекст и генерируем отчёт
                stream_func = run_analyze_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    project_path=project_path,
                    file_extensions=parsed_extensions,
                    conversation_id=conversation_id
                )
            else:  # code или другой режим с workflow
                # Теперь workflow граф сам выбирает стриминговые узлы на основе флага
                # Поэтому всегда используем run_workflow_stream (граф сам решит)
                logger.info("🔄 Используем унифицированный workflow граф (стриминг определяется автоматически)")
                stream_func = run_workflow_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    disable_web_search=disable_web_search,
                    max_iterations=max_iterations,
                    project_path=project_path,
                    file_extensions=parsed_extensions
                )
            
            async for event in stream_func:
                event_count += 1
                logger.info(f"📤 [generate] Отправляю событие #{event_count}, длина: {len(event)}")
                yield event
                await asyncio.sleep(0.01)
            
            logger.info(f"✅ [generate] Всего отправлено событий: {event_count}")
            await asyncio.sleep(0.5)
            logger.info("✅ [generate] Генератор завершен после задержки")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в generate(): {e}", error=e)
            error_event = await SSEManager.stream_error(
                stage="workflow",
                error_message=f"Ошибка выполнения: {str(e)}"
            )
            yield error_event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "*"
        }
    )


class FeedbackRequest(BaseModel):
    """Запрос на сохранение feedback."""
    task: str = Field(..., description="Текст задачи")
    task_id: Optional[str] = Field(None, description="ID задачи (если есть)")
    feedback: str = Field(..., description="Тип feedback: positive или negative")


@router.post("/feedback")
async def save_feedback(request: FeedbackRequest) -> Dict[str, str]:
    """Сохраняет feedback пользователя для задачи.
    
    Args:
        request: Запрос с задачей и типом feedback
        
    Returns:
        Статус сохранения
    """
    memory_agent = _get_memory_agent()
    
    if request.feedback not in ["positive", "negative"]:
        raise HTTPException(status_code=400, detail="feedback должен быть 'positive' или 'negative'")
    
    # Создаём фиктивный ReflectionResult для сохранения feedback
    # В реальности лучше хранить task_id и обновлять существующую запись
    fake_reflection = ReflectionResult(
        planning_score=0.0,
        research_score=0.0,
        testing_score=0.0,
        coding_score=0.0,
        overall_score=1.0 if request.feedback == "positive" else 0.0,
        analysis=f"Feedback пользователя: {request.feedback}",
        improvements="",
        should_retry=False
    )
    
    memory_agent.save_task_experience(
        task=request.task,
        intent_type="unknown",  # Не знаем intent для feedback
        reflection_result=fake_reflection,
        feedback=request.feedback,
        code="",  # Нет кода для feedback
        plan=""  # Нет плана для feedback
    )
    
    return {
        "status": "success",
        "message": f"Feedback '{request.feedback}' сохранён"
    }


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Возвращает текущие настройки системы.
    
    Returns:
        Словарь с настройками
    """
    config = get_config()
    
    return {
        "interaction": {
            "default_mode": config.interaction_default_mode,
            "auto_confirm": config.interaction_auto_confirm,
            "show_thinking": config.interaction_show_thinking,
            "max_context_messages": config.interaction_max_context_messages,
            "persist_conversations": config.interaction_persist_conversations,
            "chat_model": config.chat_model,
            "chat_model_fallback": config.chat_model_fallback
        },
        "llm": {
            "default_model": config.default_model,
            "temperature": config.temperature,
            "tokens_chat": config.llm_tokens_chat,
            "tokens_code": config.llm_tokens_code
        },
        "quality": {
            "threshold": config.quality_threshold,
            "confidence_threshold": config.confidence_threshold
        },
        "web_search": {
            "enabled": config.enable_web,
            "timeout": config.web_search_timeout
        },
        "modes": [
            {"id": "auto", "name": "Авто", "description": "Автоматический выбор режима"},
            {"id": "chat", "name": "Диалог", "description": "Простое общение без генерации кода"},
            {"id": "code", "name": "Генерация", "description": "Полный workflow с тестами и кодом"}
        ]
    }


def _get_conversation_title(messages: list) -> str:
    """Генерирует заголовок диалога из первого сообщения пользователя.
    
    Args:
        messages: Список сообщений диалога
        
    Returns:
        Заголовок диалога (до 50 символов)
    """
    # Ищем первое сообщение пользователя
    for msg in messages:
        if msg.role == "user":
            text = msg.content.strip()
            # Убираем markdown разметку
            text = re.sub(r'[#*_`~\[\]()>]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            # Обрезаем до 50 символов
            if len(text) > 50:
                return text[:47] + '...'
            return text if text else 'Новый диалог'
    return 'Новый диалог'


@router.get("/conversations")
async def list_conversations() -> Dict[str, Any]:
    """Возвращает список диалогов.
    
    Returns:
        Список диалогов с метаданными
    """
    conv_memory = get_conversation_memory()
    
    conversations = []
    for conv_id, conv in conv_memory.conversations.items():
        # Заголовок — первое сообщение пользователя
        title = _get_conversation_title(conv.messages)
        
        # Preview — последнее сообщение (для поиска)
        preview = ""
        if conv.messages:
            last_msg = conv.messages[-1].content[:100]
            # Убираем markdown из preview тоже
            preview = re.sub(r'[#*_`~\[\]()>]', '', last_msg)
            preview = re.sub(r'\s+', ' ', preview).strip()
        
        conversations.append({
            "id": conv_id,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": len(conv.messages),
            "has_summary": conv.summary is not None,
            "preview": preview,
            "title": title  # Новое поле — заголовок диалога
        })
    
    # Сортируем по дате обновления (новые первые)
    conversations.sort(key=lambda x: str(x["updated_at"]), reverse=True)  # type: ignore[arg-type]
    
    return {
        "conversations": conversations,
        "total": len(conversations)
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Возвращает детали диалога.
    
    Args:
        conversation_id: ID диалога
        
    Returns:
        Данные диалога с сообщениями
    """
    conv_memory = get_conversation_memory()
    
    if conversation_id not in conv_memory.conversations:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    conv = conv_memory.conversations[conversation_id]
    
    return {
        "id": conv.id,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "summary": conv.summary,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata
            }
            for msg in conv.messages
        ]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict[str, str]:
    """Удаляет диалог.
    
    Args:
        conversation_id: ID диалога
        
    Returns:
        Статус удаления
    """
    conv_memory = get_conversation_memory()
    
    if not conv_memory.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    return {
        "status": "success",
        "message": f"Диалог {conversation_id} удалён"
    }


@router.post("/conversations/new")
async def create_conversation() -> Dict[str, str]:
    """Создаёт новый диалог.
    
    Returns:
        ID нового диалога
    """
    conv_memory = get_conversation_memory()
    conv = conv_memory.get_or_create_conversation()
    
    return {
        "conversation_id": conv.id,
        "status": "created"
    }


# ========== TASK PERSISTENCE ENDPOINTS ==========

from infrastructure.task_checkpointer import get_task_checkpointer, TaskMetadata


@router.get("/tasks/active")
async def get_active_tasks() -> Dict[str, Any]:
    """Возвращает список активных (незавершенных) задач.
    
    Используется frontend для восстановления после обновления страницы.
    
    Returns:
        Список активных задач с метаданными
    """
    config = get_config()
    
    if not config.persistence_enabled:
        return {
            "tasks": [],
            "total": 0,
            "persistence_enabled": False
        }
    
    checkpointer = get_task_checkpointer()
    active_tasks = checkpointer.list_active_tasks()
    
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_text": t.task_text,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "last_stage": t.last_stage,
                "status": t.status,
                "iteration": t.iteration,
                "model": t.model
            }
            for t in active_tasks
        ],
        "total": len(active_tasks),
        "persistence_enabled": True
    }


@router.get("/tasks/history")
async def get_task_history(limit: int = 20) -> Dict[str, Any]:
    """Возвращает историю всех задач.
    
    Args:
        limit: Максимальное количество задач
        
    Returns:
        Список всех задач с метаданными
    """
    config = get_config()
    
    if not config.persistence_enabled:
        return {
            "tasks": [],
            "total": 0,
            "persistence_enabled": False
        }
    
    checkpointer = get_task_checkpointer()
    all_tasks = checkpointer.list_all_tasks()[:limit]
    
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_text": t.task_text,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "last_stage": t.last_stage,
                "status": t.status,
                "iteration": t.iteration,
                "model": t.model
            }
            for t in all_tasks
        ],
        "total": len(all_tasks),
        "persistence_enabled": True
    }


@router.get("/tasks/{task_id}")
async def get_task_details(task_id: str) -> Dict[str, Any]:
    """Возвращает детали задачи включая сохраненное состояние.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Детали задачи с результатами
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    result = checkpointer.load_checkpoint(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    state, metadata = result
    
    return {
        "task_id": metadata.task_id,
        "task_text": metadata.task_text,
        "created_at": metadata.created_at,
        "updated_at": metadata.updated_at,
        "last_stage": metadata.last_stage,
        "status": metadata.status,
        "iteration": metadata.iteration,
        "model": metadata.model,
        "results": {
            "intent": state.get("intent_result"),
            "plan": state.get("plan", ""),
            "context": state.get("context", "")[:500] + "..." if len(state.get("context", "")) > 500 else state.get("context", ""),
            "tests": state.get("tests", ""),
            "code": state.get("code", ""),
            "validation": state.get("validation_results", {}),
        }
    }


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """Возобновляет выполнение приостановленной задачи.
    
    Args:
        task_id: ID задачи для возобновления
        
    Returns:
        StreamingResponse с SSE событиями продолжения workflow
    """
    from fastapi.responses import StreamingResponse
    
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    result = checkpointer.load_checkpoint(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    state, metadata = result
    
    # Проверяем что задачу можно возобновить
    if metadata.status == "completed":
        raise HTTPException(status_code=400, detail="Задача уже завершена")
    
    async def generate() -> AsyncGenerator[str, None]:
        """Генератор SSE событий для возобновления задачи."""
        try:
            # Определяем следующий этап на основе last_stage
            stage_order = [
                "intent", "planner", "researcher", "test_generator",
                "coder", "validator", "debugger", "fixer", "reflection", "critic"
            ]
            
            last_stage = metadata.last_stage
            
            # Находим индекс последнего завершенного этапа
            if last_stage in stage_order:
                last_index = stage_order.index(last_stage)
            else:
                last_index = -1
            
            # Отправляем событие о возобновлении
            yield await SSEManager.stream_stage_start(
                stage="resume",
                message=f"Возобновление с этапа: {last_stage}"
            )
            await asyncio.sleep(0.05)
            
            # Отправляем сохраненные результаты
            if state.get("intent_result"):
                intent_data = state["intent_result"]
                if isinstance(intent_data, dict):
                    yield await SSEManager.stream_stage_end(
                        stage="intent",
                        message=f"Намерение: {intent_data.get('type', 'unknown')}",
                        result=intent_data
                    )
                await asyncio.sleep(0.02)
            
            if state.get("plan"):
                yield await SSEManager.stream_stage_end(
                    stage="planning",
                    message="План восстановлен",
                    result={"plan_length": len(state["plan"])}
                )
                await asyncio.sleep(0.02)
            
            if state.get("context"):
                yield await SSEManager.stream_stage_end(
                    stage="research",
                    message="Контекст восстановлен",
                    result={"context_length": len(state["context"])}
                )
                await asyncio.sleep(0.02)
            
            if state.get("tests"):
                yield await SSEManager.stream_stage_end(
                    stage="testing",
                    message="Тесты восстановлены",
                    result={"tests_length": len(state["tests"])}
                )
                await asyncio.sleep(0.02)
            
            if state.get("code"):
                yield await SSEManager.stream_stage_end(
                    stage="coding",
                    message="Код восстановлен",
                    result={"code_length": len(state["code"]), "code": state["code"]}
                )
                # Отправляем код как chunk для IDE
                yield await SSEManager.stream_code_chunk(
                    chunk=state["code"],
                    is_final=True,
                    metadata={"stage": "resume"}
                )
                await asyncio.sleep(0.02)
            
            if state.get("validation_results"):
                yield await SSEManager.stream_stage_end(
                    stage="validation",
                    message="Валидация восстановлена",
                    result=state["validation_results"]
                )
                await asyncio.sleep(0.02)
            
            # Определяем нужно ли продолжать workflow
            validation = state.get("validation_results", {})
            all_passed = validation.get("all_passed", False)
            iteration = state.get("iteration", 0)
            max_iterations = state.get("max_iterations", 3)
            
            # Если задача не завершена, продолжаем workflow
            if last_index < len(stage_order) - 1:
                # Нужно продолжить с последнего этапа
                # Для простоты пока просто отправляем финальный результат с тем что есть
                
                # Формируем итоговые метрики
                reflection = state.get("reflection_result")
                if isinstance(reflection, dict):
                    metrics = {
                        "planning": reflection.get("planning_score", 0.0),
                        "research": reflection.get("research_score", 0.0),
                        "testing": reflection.get("testing_score", 0.0),
                        "coding": reflection.get("coding_score", 0.0),
                        "overall": reflection.get("overall_score", 0.0)
                    }
                else:
                    metrics = {
                        "planning": 0.0,
                        "research": 0.0,
                        "testing": 0.0,
                        "coding": 0.0,
                        "overall": 0.0
                    }
                
                # Формируем intent для результата
                intent_data = state.get("intent_result", {})
                if isinstance(intent_data, dict):
                    intent_for_result = {
                        "type": intent_data.get("type", "unknown"),
                        "confidence": intent_data.get("confidence", 0.0),
                        "description": intent_data.get("description", "")
                    }
                else:
                    intent_for_result = {"type": "unknown", "confidence": 0.0, "description": ""}
                
                yield await SSEManager.stream_final_result(
                    task_id=task_id,
                    results={
                        "task": state.get("task", ""),
                        "intent": intent_for_result,
                        "plan": state.get("plan", ""),
                        "context": state.get("context", ""),
                        "tests": state.get("tests", ""),
                        "code": state.get("code", ""),
                        "validation": validation,
                        "resumed": True,
                        "last_stage": last_stage
                    },
                    metrics=metrics
                )
            
            await asyncio.sleep(0.2)
            logger.info(f"✅ Задача {task_id[:8]}... возобновлена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка возобновления задачи: {e}", error=e)
            yield await SSEManager.stream_error(
                stage="resume",
                error_message=f"Ошибка возобновления: {str(e)}"
            )
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Credentials": "true"
        }
    )


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> Dict[str, str]:
    """Удаляет checkpoint задачи.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Статус удаления
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    
    if not checkpointer.delete_checkpoint(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    return {
        "status": "success",
        "message": f"Задача {task_id} удалена"
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """Отменяет/приостанавливает задачу.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Статус отмены
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    checkpointer.mark_paused(task_id)
    
    return {
        "status": "success",
        "message": f"Задача {task_id} приостановлена"
    }
