"""Роутер для работы с агентами через API.

Поддерживает режимы взаимодействия:
- auto: Автоматический выбор режима на основе анализа
- chat: Простой диалог с LLM без workflow
- plan: Только планирование без генерации кода
- analyze: Анализ кода/задачи
- code: Полный workflow генерации кода (TDD)
"""
import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.intent import IntentAgent, IntentResult
from agents.chat import ChatAgent, get_chat_agent
from agents.conversation import get_conversation_memory, ConversationMemory
from agents.reflection import ReflectionResult
from backend.types import InteractionMode, TaskRequest, SessionSettings
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
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.logger import get_logger
from backend.sse_manager import SSEManager
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState
from infrastructure.model_router import get_model_router, reset_model_router


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
    "💡 **Как использовать:**\n"
    "Просто опишите задачу на естественном языке, например:\n"
    "  • «напиши функцию сортировки»\n"
    "  • «создай калькулятор»\n"
    "  • «сделай парсер JSON»\n\n"
    "Я понимаю русский и английский. Даже если вы напечатали в неправильной раскладке — я пойму! 😊"
)

# ========== ИМПОРТ ЗАВИСИМОСТЕЙ ==========

# MemoryAgent через DependencyContainer (Singleton)
from backend.dependencies import get_memory_agent as _get_memory_agent


# TaskRequest импортирован из backend.types


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


async def run_workflow_stream(
    task: str,
    model: str,
    temperature: float,
    disable_web_search: bool,
    max_iterations: int
) -> AsyncGenerator[str, None]:
    """Запускает workflow агентов с SSE стримингом через LangGraph.
    
    Args:
        task: Текст задачи
        model: Модель Ollama (будет проверена на доступность)
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций (ограничено до 5)
        
    Yields:
        SSE события в формате text/event-stream
    """
    task_id = str(uuid.uuid4())
    
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
        "file_path": None,
        "file_context": None
    }
    
    # Создаём граф
    graph = create_workflow_graph()
    
    try:
        # Запускаем граф с стримингом
        async for event in graph.astream(initial_state):
            # Обрабатываем события графа
            # event - это словарь с ключами узлов и их обновлениями state
            for node_name, node_state in event.items():
                # Отправляем SSE события на основе узла
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
                        
                        # Если greeting или help, отправляем специальное сообщение и завершаем
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
                        yield await SSEManager.stream_stage_end(
                            stage="coding",
                            message="Код сгенерирован",
                            result={"code_length": len(code)}
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
                        yield await SSEManager.stream_stage_end(
                            stage="fixing",
                            message="Код исправлен",
                            result={"code_length": len(code)}
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


@router.get("/stream")
async def stream_task_results(
    task: str,
    mode: str = "auto",
    model: str = "",
    temperature: float = 0.25,
    disable_web_search: bool = False,
    max_iterations: int = 3,
    conversation_id: Optional[str] = None
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
        
    Returns:
        StreamingResponse с SSE событиями
    """
    from fastapi.responses import StreamingResponse
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            event_count = 0
            selected_mode = mode
            detected_intent_type: Optional[str] = None
            detected_complexity: Optional[TaskComplexity] = None
            
            # В режиме auto определяем нужен ли полный workflow
            if mode == "auto":
                intent_agent = IntentAgent(lazy_llm=True)
                
                # Быстрая проверка на greeting
                if IntentAgent.is_greeting_fast(task):
                    selected_mode = "chat"
                    detected_intent_type = "greeting"
                    detected_complexity = TaskComplexity.SIMPLE
                    logger.info("🚀 Быстрое определение: greeting → chat + SIMPLE")
                else:
                    # Эвристика: короткие запросы без ключевых слов кода → chat
                    task_lower = task.lower()
                    code_keywords = [
                        'напиши', 'создай', 'сделай', 'реализуй', 'сгенерируй',
                        'write', 'create', 'make', 'implement', 'generate',
                        'функци', 'класс', 'модуль', 'скрипт', 'код',
                        'function', 'class', 'module', 'script', 'code',
                        'исправ', 'отлад', 'debug', 'fix', 'оптимизир'
                    ]
                    
                    has_code_keyword = any(kw in task_lower for kw in code_keywords)
                    
                    if has_code_keyword:
                        selected_mode = "code"
                        # Определяем сложность эвристически для code режима
                        detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                        logger.info(f"🔧 Обнаружены code-ключевые слова → code + {detected_complexity.value}")
                    else:
                        # Используем LLM для точного определения intent
                        intent_result = intent_agent.determine_intent(task)
                        selected_mode = intent_result.recommended_mode
                        detected_intent_type = intent_result.type
                        
                        # Для chat режима пересчитываем сложность эвристикой
                        # (LLM определяет intent, но сложность лучше определять эвристикой)
                        detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                        
                        # Для explain intent минимум MEDIUM сложность
                        if intent_result.type == "explain" and detected_complexity == TaskComplexity.SIMPLE:
                            detected_complexity = TaskComplexity.MEDIUM
                            logger.info(f"📊 Explain intent повышен до MEDIUM")
                        
                        logger.info(f"🧠 LLM определение: {intent_result.type} → {selected_mode} + {detected_complexity.value}")
            
            # Для явно указанного chat режима тоже определяем сложность
            elif mode == "chat" and detected_complexity is None:
                intent_agent = IntentAgent(lazy_llm=True)
                detected_complexity = intent_agent._estimate_complexity_heuristic(task)
                logger.info(f"💬 Явный chat режим, сложность: {detected_complexity.value}")
            
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
            else:  # code или другой режим с workflow
                stream_func = run_workflow_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    disable_web_search=disable_web_search,
                    max_iterations=max_iterations
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
        feedback=request.feedback
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


@router.get("/conversations")
async def list_conversations() -> Dict[str, Any]:
    """Возвращает список диалогов.
    
    Returns:
        Список диалогов с метаданными
    """
    conv_memory = get_conversation_memory()
    
    conversations = []
    for conv_id, conv in conv_memory.conversations.items():
        conversations.append({
            "id": conv_id,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": len(conv.messages),
            "has_summary": conv.summary is not None,
            "preview": conv.messages[-1].content[:100] if conv.messages else ""
        })
    
    # Сортируем по дате обновления (новые первые)
    conversations.sort(key=lambda x: x["updated_at"], reverse=True)
    
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
