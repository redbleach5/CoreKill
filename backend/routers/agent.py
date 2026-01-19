"""Роутер для работы с агентами через API."""
import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.intent import IntentAgent, IntentResult
from agents.reflection import ReflectionResult
from agents.memory import MemoryAgent
from utils.artifact_saver import ArtifactSaver
from utils.config import get_config
from utils.model_checker import get_all_available_models
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.logger import get_logger
from backend.sse_manager import SSEManager
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState


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

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========

# Глобальный MemoryAgent для feedback endpoint
_memory_agent: Optional[MemoryAgent] = None


def _get_memory_agent() -> MemoryAgent:
    """Возвращает глобальный MemoryAgent, создавая его при необходимости."""
    global _memory_agent
    if _memory_agent is None:
        _memory_agent = MemoryAgent()
    return _memory_agent


class TaskRequest(BaseModel):
    """Запрос на выполнение задачи."""
    task: str = Field(..., description="Текст задачи на русском или английском")
    model: str = Field(default="", description="Модель Ollama (если пусто, будет выбрана автоматически)")
    temperature: float = Field(default=0.25, ge=0.1, le=0.7, description="Температура генерации")
    disable_web_search: bool = Field(default=False, description="Отключить веб-поиск")
    max_iterations: int = Field(default=1, ge=1, le=3, description="Максимальное количество итераций")


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
    
    # Определяем модель для использования
    from utils.model_checker import check_model_available, get_any_available_model
    
    # Если модель не указана или пустая, выбираем автоматически
    model_to_use = (model.strip() if model and isinstance(model, str) and model.strip() else None)
    if not model_to_use:
        # Автоматически выбираем доступную модель
        model_to_use = get_any_available_model()
        if model_to_use:
            logger.info(f"🤖 Автоматически выбрана модель: {model_to_use}")
        else:
            logger.error("❌ Нет доступных моделей Ollama!")
            yield await SSEManager.stream_error(
                stage="initialization",
                error_message="Нет доступных моделей Ollama. Установите хотя бы одну модель."
            )
            return
    elif not check_model_available(model_to_use):
        logger.warning(f"⚠️ Модель {model_to_use} недоступна, выбираю альтернативу")
        model_to_use = get_any_available_model()
        if not model_to_use:
            logger.error("❌ Нет доступных моделей Ollama!")
            yield await SSEManager.stream_error(
                stage="initialization",
                error_message="Нет доступных моделей Ollama. Установите хотя бы одну модель."
            )
            return
    
    # Создаём начальный state
    initial_state: AgentState = {
        "task": task,
        "max_iterations": max_iterations,
        "disable_web_search": disable_web_search,
        "model": model_to_use,
        "temperature": temperature,
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
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
                        
                        # Если greeting, отправляем специальное сообщение
                        if intent_result.type == "greeting":
                                logger.info(f"📤 Отправляю greeting stage_end")
                                event3 = await SSEManager.stream_stage_end(
                                    stage="greeting",
                                    message=GREETING_MESSAGE,
                                    result={"type": "greeting", "message": GREETING_MESSAGE}
                                )
                                yield event3
                                logger.info(f"✅ Отправлено greeting, длина: {len(event3)}")
                                
                                logger.info(f"📤 Отправляю final_result (complete)")
                                event4 = await SSEManager.stream_final_result(
                                    task_id=task_id,
                                    results={
                                        "task": task,
                                        "intent": {
                                            "type": "greeting",
                                            "confidence": intent_result.confidence,
                                            "description": intent_result.description
                                        }
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
    """Возвращает список доступных моделей Ollama.
    
    Модели отсортированы по приоритету: быстрые coder модели первые.
    
    Returns:
        Словарь с списком доступных моделей
    """
    all_models = get_all_available_models()
    
    # Приоритетные модели (быстрые и качественные для кода)
    priority_order = [
        'qwen2.5-coder:1.5b',  # Лучший баланс скорость/качество
        'gemma3:1b',
        'stable-code:latest',
        'phi3:mini',
        'llama3.2:3b',
        'gemma3:4b',
        'qwen2.5-coder:7b',
        'deepseek-coder:6.7b',
        'codellama:7b',
    ]
    
    # Сортируем: приоритетные первые, остальные в конце
    def sort_key(model: str) -> int:
        try:
            return priority_order.index(model)
        except ValueError:
            # Embed модели в конец
            if 'embed' in model.lower():
                return 1000
            return 100
    
    sorted_models = sorted(all_models, key=sort_key)
    
    return {
        "models": sorted_models,
        "count": len(sorted_models)
    }


@router.get("/stream")
async def stream_task_results(
    task: str,
    model: str = "",
    temperature: float = 0.25,
    disable_web_search: bool = False,
    max_iterations: int = 1
):
    """SSE endpoint для стриминга результатов выполнения задачи.
    
    Args:
        task: Текст задачи
        model: Модель Ollama
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций
        
    Returns:
        StreamingResponse с SSE событиями
    """
    from fastapi.responses import StreamingResponse
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            event_count = 0
            async for event in run_workflow_stream(
                task=task,
                model=model,
                temperature=temperature,
                disable_web_search=disable_web_search,
                max_iterations=max_iterations
            ):
                event_count += 1
                logger.info(f"📤 [generate] Отправляю событие #{event_count}, длина: {len(event)}")
                yield event
                # Небольшая задержка для гарантии отправки каждого события
                await asyncio.sleep(0.01)
            logger.info(f"✅ [generate] Всего отправлено событий: {event_count}")
            # ВАЖНО: Задержка перед закрытием генератора, чтобы frontend успел получить события
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
