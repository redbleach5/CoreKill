"""Роутер для работы с агентами через API."""
import asyncio
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.intent import IntentAgent, IntentResult
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.memory import MemoryAgent
from utils.validation import validate_code
from utils.artifact_saver import ArtifactSaver
from utils.config import get_config
from utils.file_context import extract_file_path_from_task, read_file_context, prepare_modify_context
from utils.model_checker import get_all_available_models, get_available_model
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.logger import get_logger
from backend.sse_manager import SSEManager
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState


logger = get_logger()


router = APIRouter(prefix="/api", tags=["agents"])

# Глобальные агенты (инициализируются один раз)
_agents_initialized = False
_memory_agent: Optional[MemoryAgent] = None
_intent_agent: Optional[IntentAgent] = None
_planner_agent: Optional[PlannerAgent] = None
_researcher_agent: Optional[ResearcherAgent] = None
_test_generator: Optional[TestGeneratorAgent] = None
_coder_agent: Optional[CoderAgent] = None
_debugger_agent: Optional[DebuggerAgent] = None
_reflection_agent: Optional[ReflectionAgent] = None


def _initialize_agents(
    model: Optional[str] = None,
    temperature: float = 0.25
) -> None:
    """Инициализирует агентов один раз при первом запросе.
    
    Args:
        model: Модель для использования (будет проверена на доступность)
        temperature: Температура генерации
    """
    global _agents_initialized, _memory_agent, _intent_agent, _planner_agent
    global _researcher_agent, _test_generator, _coder_agent, _debugger_agent, _reflection_agent
    
    if _agents_initialized:
        return
    
    _memory_agent = MemoryAgent()
    # Агенты сами выберут доступные модели через свои fallback механизмы
    # Передаем модель только если она указана, иначе агенты выберут сами
    _intent_agent = IntentAgent(model=None, temperature=0.2)
    _planner_agent = PlannerAgent(model=model, temperature=temperature, memory_agent=_memory_agent)
    _researcher_agent = ResearcherAgent(memory_agent=_memory_agent)
    _test_generator = TestGeneratorAgent(model=model, temperature=0.18)
    _coder_agent = CoderAgent(model=model, temperature=temperature)
    _debugger_agent = DebuggerAgent(model=model, temperature=0.2)
    _reflection_agent = ReflectionAgent(model=model, temperature=temperature)
    
    _agents_initialized = True


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
    
    # Ограничиваем max_iterations
    config = get_config()
    max_iterations = min(max_iterations, config.max_iterations, 5)
    
    # Определяем модель для использования
    from utils.model_checker import check_model_available, get_any_available_model
    
    model_to_use = model if model else None
    if model_to_use and not check_model_available(model_to_use):
        logger.warning(f"⚠️ Модель {model_to_use} недоступна, выбираю альтернативу")
        model_to_use = get_any_available_model()
    
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
        "enable_sse": True  # Флаг для SSE стриминга
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
                        yield await SSEManager.stream_stage_start(
                            stage="intent",
                            message="Определяю намерение..."
                        )
                        yield await SSEManager.stream_stage_end(
                            stage="intent",
                            message=f"Намерение определено: {intent_result.type}",
                            result={"type": intent_result.type, "confidence": intent_result.confidence}
                        )
                        
                        # Если greeting, отправляем специальное сообщение
                        if intent_result.type == "greeting":
                            greeting_message = (
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
                            yield await SSEManager.stream_stage_end(
                                stage="greeting",
                                message=greeting_message,
                                result={"type": "greeting", "message": greeting_message}
                            )
                            yield await SSEManager.stream_final_result(
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
                            return
                
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
                        
                        # Подсчитываем токены
                        estimated_tokens = estimate_workflow_tokens(
                            task=task,
                            plan=node_state.get("plan", ""),
                            context=node_state.get("context", ""),
                            tests=node_state.get("tests", ""),
                            code=node_state.get("code", ""),
                            prompts_used=[]  # TODO: отслеживать промпты в узлах
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
                        
                        # Финальный результат
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
                                    "planning_score": reflection_result.planning_score,
                                    "research_score": reflection_result.research_score,
                                    "testing_score": reflection_result.testing_score,
                                    "coding_score": reflection_result.coding_score,
                                    "overall_score": reflection_result.overall_score,
                                    "analysis": reflection_result.analysis,
                                    "improvements": reflection_result.improvements,
                                    "should_retry": reflection_result.should_retry
                                },
                                "tokens_used": estimated_tokens,
                                "token_warning": token_status["warning"]
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
        logger.error(f"❌ Ошибка выполнения workflow: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="workflow",
            error_message=f"Ошибка выполнения workflow: {str(e)}",
            error_details={"exception_type": type(e).__name__}
        )


async def run_workflow_stream_legacy(
    task: str,
    model: str,
    temperature: float,
    disable_web_search: bool,
    max_iterations: int
) -> AsyncGenerator[str, None]:
    """Запускает workflow агентов с SSE стримингом (legacy, без LangGraph).
    
    DEPRECATED: Используйте run_workflow_stream вместо этого.
    
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
    
    # Ограничиваем max_iterations
    config = get_config()
    max_iterations = min(max_iterations, config.max_iterations, 5)
    
    # Определяем модель для использования
    from utils.model_checker import check_model_available, get_any_available_model
    
    # БЫСТРАЯ ПРОВЕРКА: Используем статический метод IntentAgent для проверки приветствия
    # БЕЗ инициализации агента и LLM. Вся логика проверки находится в IntentAgent,
    # а не хардкодится в роутере (соблюдение архитектурных принципов).
    is_greeting = IntentAgent.is_greeting_fast(task)
    
    # Если это приветствие - обрабатываем БЕЗ инициализации тяжелых агентов
    if is_greeting:
        # Используем IntentResult напрямую, так как is_greeting_fast() уже определил результат
        # Вся логика проверки находится в IntentAgent.is_greeting_fast(), а не хардкодится в роутере
        # Это соблюдает архитектурные принципы - логика в агенте, роутер только использует её
        intent_result = IntentResult(
            type="greeting",
            confidence=0.95,
            description="Приветствие пользователя"
        )
        greeting_message = (
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
        yield await SSEManager.stream_stage_start(
            stage="intent",
            message="Определяю намерение..."
        )
        yield await SSEManager.stream_stage_end(
            stage="intent",
            message="Намерение определено: greeting",
            result={"type": "greeting", "confidence": intent_result.confidence}
        )
        yield await SSEManager.stream_stage_end(
            stage="greeting",
            message=greeting_message,
            result={"type": "greeting", "message": greeting_message}
        )
        yield await SSEManager.stream_final_result(
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
        return
    
    # Только для НЕ-приветствий инициализируем остальных агентов
    if not _agents_initialized:
        _initialize_agents(model=model, temperature=temperature)
    
    # Для не-greeting определяем намерение через LLM
    if not is_greeting:
        intent_result = _intent_agent.determine_intent(task)
    
    # Список промптов для подсчёта токенов
    prompts_used: List[str] = []
    
    # Переменные для хранения результатов
    plan = ""
    context = ""
    tests = ""
    code = ""
    validation_results: Dict[str, Any] = {}
    reflection_result = None
    
    try:
        # Шаг 1: Определение намерения
        # Для greeting уже определено и события отправлены выше через ранний return
        if not is_greeting:
            yield await SSEManager.stream_stage_start(
                stage="intent",
                message="Определяю намерение..."
            )
            
            yield await SSEManager.stream_stage_end(
                stage="intent",
                message=f"Намерение определено: {intent_result.type}",
                result={"type": intent_result.type, "confidence": intent_result.confidence}
            )
        
        # Запасная проверка (не должна срабатывать, так как greeting уже обработан выше)
        if intent_result.type == "greeting":
            greeting_message = (
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
            yield await SSEManager.stream_stage_end(
                stage="greeting",
                message=greeting_message,
                result={"type": "greeting", "message": greeting_message}
            )
            # Отправляем финальное событие для корректного завершения
            yield await SSEManager.stream_final_result(
                task_id=task_id,
                results={
                    "task": task,
                    "intent": {
                        "type": intent_result.type,
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
            return
        
        # Шаг 2: Планирование
        yield await SSEManager.stream_stage_start(
            stage="planning",
            message="Создаю план выполнения..."
        )
        
        plan = _planner_agent.create_plan(
            task=task,
            intent_type=intent_result.type
        )
        
        yield await SSEManager.stream_stage_end(
            stage="planning",
            message="План создан",
            result={"plan_length": len(plan)}
        )
        
        # Шаг 3: Исследование (RAG + файл если modify/debug)
        yield await SSEManager.stream_stage_start(
            stage="research",
            message="Ищу контекст в базе знаний (RAG)..."
        )
        
        # Проверяем есть ли файл для modify/debug режима
        file_path = extract_file_path_from_task(task)
        file_context = None
        if file_path and intent_result.type in ['modify', 'debug']:
            file_content = read_file_context(file_path)
            if file_content:
                file_context = prepare_modify_context(task, file_content)
                yield await SSEManager.stream_stage_progress(
                    stage="research",
                    progress=0.3,
                    message=f"Найден файл для модификации: {file_path}"
                )
        
        context = _researcher_agent.research(
            query=task,
            intent_type=intent_result.type,
            disable_web_search=disable_web_search
        )
        
        # Добавляем контекст файла в начало если есть
        if file_context:
            context = file_context + "\n\n---\n\n" + context if context else file_context
        
        # Информация о веб-поиске (если он был выполнен внутри research)
        if not disable_web_search and "[Веб-контекст]" in context:
            yield await SSEManager.stream_stage_progress(
                stage="research",
                progress=0.8,
                message="Веб-поиск выполнен, контекст собран"
            )
        
        yield await SSEManager.stream_stage_end(
            stage="research",
            message="Контекст собран",
            result={"context_length": len(context)}
        )
        
        # Шаг 4: Генерация тестов
        yield await SSEManager.stream_stage_start(
            stage="testing",
            message="Генерирую тесты..."
        )
        
        tests = _test_generator.generate_tests(
            plan=plan,
            context=context,
            intent_type=intent_result.type
        )
        
        if not tests:
            yield await SSEManager.stream_error(
                stage="testing",
                error_message="Не удалось сгенерировать тесты"
            )
            return
        
        yield await SSEManager.stream_stage_end(
            stage="testing",
            message="Тесты сгенерированы",
            result={"tests_length": len(tests)}
        )
        
        # Шаг 5: Генерация кода
        yield await SSEManager.stream_stage_start(
            stage="coding",
            message="Генерирую код..."
        )
        
        code = _coder_agent.generate_code(
            plan=plan,
            tests=tests,
            context=context,
            intent_type=intent_result.type
        )
        
        if not code:
            yield await SSEManager.stream_error(
                stage="coding",
                error_message="Не удалось сгенерировать код"
            )
            return
        
        yield await SSEManager.stream_stage_end(
            stage="coding",
            message="Код сгенерирован",
            result={"code_length": len(code)}
        )
        
        # Шаг 6: Валидация
        yield await SSEManager.stream_stage_start(
            stage="validation",
            message="Валидирую код (pytest, mypy, bandit)..."
        )
        
        validation_results = validate_code(code_str=code, test_str=tests)
        
        yield await SSEManager.stream_stage_end(
            stage="validation",
            message="Валидация завершена",
            result=validation_results
        )
        
        # Цикл self-healing (до max_iterations итераций)
        iteration = 1
        while not validation_results.get("all_passed", False) and iteration < max_iterations:
            logger.info(f"🔄 Итерация исправления {iteration}/{max_iterations - 1}...")
            
            # Этап Debug: Анализ ошибок через Debugger
            yield await SSEManager.stream_stage_start(
                stage="debug",
                message=f"Анализирую ошибки (итерация {iteration})..."
            )
            
            if not _debugger_agent:
                logger.warning("⚠️ Debugger Agent не инициализирован, пропускаем цикл self-healing")
                break
            
            debug_result = _debugger_agent.analyze_errors(
                validation_results=validation_results,
                code=code,
                tests=tests,
                task=task
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
            
            # Этап Fixing: Исправление кода через Coder
            yield await SSEManager.stream_stage_start(
                stage="fixing",
                message=f"Исправляю код по инструкциям (итерация {iteration})..."
            )
            
            fixed_code = _coder_agent.fix_code(
                code=code,
                instructions=debug_result.fix_instructions,
                tests=tests,
                validation_results=validation_results
            )
            
            if fixed_code:
                code = fixed_code
                yield await SSEManager.stream_stage_end(
                    stage="fixing",
                    message="Код исправлен",
                    result={"code_length": len(code)}
                )
            else:
                logger.warning("⚠️ Не удалось исправить код, прерываем цикл")
                yield await SSEManager.stream_stage_end(
                    stage="fixing",
                    message="Не удалось исправить код",
                    result={"error": "fix_failed"}
                )
                break
            
            # Повторная валидация
            yield await SSEManager.stream_stage_start(
                stage="validation",
                message=f"Повторная валидация (итерация {iteration})..."
            )
            
            validation_results = validate_code(code_str=code, test_str=tests)
            
            yield await SSEManager.stream_stage_end(
                stage="validation",
                message="Повторная валидация завершена",
                result=validation_results
            )
            
            iteration += 1
        
        # Шаг 7: Рефлексия
        yield await SSEManager.stream_stage_start(
            stage="reflection",
            message="Анализирую результаты..."
        )
        
        reflection_result = _reflection_agent.reflect(
            task=task,
            plan=plan,
            context=context,
            tests=tests,
            code=code,
            validation_results=validation_results
        )
        
        # Сохраняем опыт в память
        _memory_agent.save_task_experience(
            task=task,
            intent_type=intent_result.type,
            reflection_result=reflection_result,
            key_decisions=plan[:500] if plan else "",
            what_worked=reflection_result.analysis
        )
        
        # Сохраняем артефакты
        artifact_saver = ArtifactSaver()
        artifacts_dir = None
        try:
            artifacts_dir = artifact_saver.save_all_artifacts(
                task=task,
                code=code,
                tests=tests,
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
            # Не прерываем workflow при ошибке сохранения
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
        
        # Подсчитываем токены и проверяем лимиты
        estimated_tokens = estimate_workflow_tokens(
            task=task,
            plan=plan,
            context=context,
            tests=tests,
            code=code,
            prompts_used=prompts_used
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
        
        # Финальный результат
        yield await SSEManager.stream_final_result(
            task_id=task_id,
            results={
                "task": task,
                "intent": {
                    "type": intent_result.type,
                    "confidence": intent_result.confidence,
                    "description": intent_result.description
                },
                "plan": plan,
                "context": context,
                "tests": tests,
                "code": code,
                "validation": validation_results,
                "reflection": {
                    "planning_score": reflection_result.planning_score,
                    "research_score": reflection_result.research_score,
                    "testing_score": reflection_result.testing_score,
                    "coding_score": reflection_result.coding_score,
                    "overall_score": reflection_result.overall_score,
                    "analysis": reflection_result.analysis,
                    "improvements": reflection_result.improvements,
                    "should_retry": reflection_result.should_retry
                },
                "tokens_used": estimated_tokens,
                "token_warning": token_status["warning"]
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
    
    Returns:
        Словарь с списком доступных моделей
    """
    models = get_all_available_models()
    return {
        "models": models,
        "count": len(models)
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
        async for event in run_workflow_stream(
            task=task,
            model=model,
            temperature=temperature,
            disable_web_search=disable_web_search,
            max_iterations=max_iterations
        ):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
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
    if not _memory_agent:
        _initialize_agents(model=None)
    
    if request.feedback not in ["positive", "negative"]:
        raise HTTPException(status_code=400, detail="feedback должен быть 'positive' или 'negative'")
    
    # Создаём фиктивный ReflectionResult для сохранения feedback
    # В реальности лучше хранить task_id и обновлять существующую запись
    from agents.reflection import ReflectionResult
    
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
    
    _memory_agent.save_task_experience(
        task=request.task,
        intent_type="unknown",  # Не знаем intent для feedback
        reflection_result=fake_reflection,
        feedback=request.feedback
    )
    
    return {
        "status": "success",
        "message": f"Feedback '{request.feedback}' сохранён"
    }
