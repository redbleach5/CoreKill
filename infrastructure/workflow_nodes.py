"""Узлы (nodes) для LangGraph workflow.

Каждый узел соответствует одному агенту в workflow.
Агенты инициализируются лениво при первом вызове.
MemoryAgent используется через DependencyContainer (Singleton).

ВАЖНО: Все узлы теперь асинхронные (async def) для совместимости с FastAPI.

Поддержка стриминговых агентов:
- Если config.toml: [streaming] use_streaming_agents = true — используются Streaming* агенты
- Стриминговые агенты позволяют real-time вывод <think> блоков reasoning моделей
- Для SSE стриминга используйте stream_node_* функции

Обработка ошибок, метрики и checkpoints — через декоратор @workflow_node.
"""
import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, Any
from infrastructure.workflow_state import AgentState
from infrastructure.workflow_decorators import workflow_node
from agents.intent import IntentAgent, IntentResult
from agents.researcher import ResearcherAgent
from backend.dependencies import get_memory_agent
from utils.validation import validate_code
from utils.config import get_config
from utils.logger import get_logger
from utils.file_context import extract_file_path_from_task, read_file_context, prepare_modify_context

# Синхронные агенты (fallback)
from agents.planner import PlannerAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.critic import CriticAgent, get_critic_agent

# Стриминговые агенты (real-time <think> блоки)
from agents.streaming_planner import StreamingPlannerAgent
from agents.streaming_test_generator import StreamingTestGeneratorAgent
from agents.streaming_coder import StreamingCoderAgent
from agents.streaming_debugger import StreamingDebuggerAgent
from agents.streaming_reflection import StreamingReflectionAgent
from agents.streaming_critic import StreamingCriticAgent

# Incremental Coder для Compiler-in-the-Loop (Phase 3)
from agents.incremental_coder import IncrementalCoder
from utils.model_checker import TaskComplexity
from infrastructure.debate import run_debate_if_enabled, is_debate_enabled

if TYPE_CHECKING:
    from agents.memory import MemoryAgent

logger = get_logger()


def _is_streaming_enabled() -> bool:
    """Проверяет включён ли режим стриминга в config.toml."""
    try:
        config = get_config()
        streaming_config = config._config_data.get("streaming", {})
        return streaming_config.get("use_streaming_agents", False)
    except Exception:
        return False


# Глобальные агенты (инициализируются один раз)
# Синхронные версии
_intent_agent: IntentAgent | None = None
_planner_agent: PlannerAgent | None = None
_researcher_agent: ResearcherAgent | None = None
_test_generator: TestGeneratorAgent | None = None
_coder_agent: CoderAgent | None = None
_debugger_agent: DebuggerAgent | None = None
_reflection_agent: ReflectionAgent | None = None
_critic_agent: CriticAgent | None = None

# Стриминговые версии
_streaming_planner: StreamingPlannerAgent | None = None
_streaming_test_generator: StreamingTestGeneratorAgent | None = None
_streaming_coder: StreamingCoderAgent | None = None
_streaming_debugger: StreamingDebuggerAgent | None = None
_streaming_reflection: StreamingReflectionAgent | None = None
_streaming_critic: StreamingCriticAgent | None = None


def _get_memory_agent() -> 'MemoryAgent':
    """Возвращает глобальный MemoryAgent через DependencyContainer.
    
    Returns:
        Singleton экземпляр MemoryAgent
    """
    return get_memory_agent()


def _initialize_agents(state: AgentState) -> None:
    """Инициализирует агентов если они ещё не инициализированы.
    
    Инициализирует синхронные агенты. Стриминговые агенты
    инициализируются отдельно через _initialize_streaming_agents().
    
    Args:
        state: State с параметрами для инициализации
    """
    global _intent_agent, _planner_agent, _researcher_agent
    global _test_generator, _coder_agent, _debugger_agent, _reflection_agent, _critic_agent
    
    # MemoryAgent получаем через DependencyContainer (Singleton)
    memory_agent = _get_memory_agent()
    
    if _intent_agent is None:
        _intent_agent = IntentAgent(model=None, temperature=0.2)
    
    if _planner_agent is None:
        _planner_agent = PlannerAgent(
            model=state.get("model"),
            temperature=state.get("temperature", 0.25),
            memory_agent=memory_agent
        )
    
    if _researcher_agent is None:
        _researcher_agent = ResearcherAgent(memory_agent=memory_agent)
    
    if _test_generator is None:
        _test_generator = TestGeneratorAgent(
            model=state.get("model"),
            temperature=0.18
        )
    
    if _coder_agent is None:
        _coder_agent = CoderAgent(
            model=state.get("model"),
            temperature=state.get("temperature", 0.25)
        )
    
    if _debugger_agent is None:
        _debugger_agent = DebuggerAgent(
            model=state.get("model"),
            temperature=0.2
        )
    
    if _reflection_agent is None:
        _reflection_agent = ReflectionAgent(
            model=state.get("model"),
            temperature=state.get("temperature", 0.25)
        )
    
    if _critic_agent is None:
        _critic_agent = get_critic_agent()


# Кэш текущей модели для отслеживания изменений
_current_streaming_model: str | None = None


def _initialize_streaming_agents(state: AgentState) -> None:
    """Инициализирует стриминговые агенты если они ещё не инициализированы.
    
    Вызывается только если use_streaming_agents = true в config.toml.
    Переинициализирует агентов если модель изменилась.
    
    Args:
        state: State с параметрами для инициализации
    """
    global _streaming_planner, _streaming_test_generator, _streaming_coder
    global _streaming_debugger, _streaming_reflection, _streaming_critic
    global _current_streaming_model
    
    memory_agent = _get_memory_agent()
    requested_model = state.get("model")
    
    # Переинициализируем агентов если модель изменилась
    model_changed = _current_streaming_model is not None and requested_model != _current_streaming_model
    if model_changed:
        logger.info(f"🔄 Модель изменилась: {_current_streaming_model} → {requested_model}, переинициализирую агентов")
        _streaming_planner = None
        _streaming_test_generator = None
        _streaming_coder = None
        _streaming_debugger = None
        _streaming_reflection = None
        _streaming_critic = None
    
    _current_streaming_model = requested_model
    
    if _streaming_planner is None:
        # Для планирования используем быструю модель (не reasoning)
        # Агент сам выберет подходящую через router
        _streaming_planner = StreamingPlannerAgent(
            model=None,  # Авто-выбор быстрой модели для planning
            temperature=state.get("temperature", 0.25),
            memory_agent=memory_agent
        )
    
    if _streaming_test_generator is None:
        _streaming_test_generator = StreamingTestGeneratorAgent(
            model=requested_model,
            temperature=0.18
        )
    
    if _streaming_coder is None:
        _streaming_coder = StreamingCoderAgent(
            model=requested_model,
            temperature=state.get("temperature", 0.25)
        )
    
    if _streaming_debugger is None:
        _streaming_debugger = StreamingDebuggerAgent(
            model=requested_model,
            temperature=0.2
        )
    
    if _streaming_reflection is None:
        _streaming_reflection = StreamingReflectionAgent(
            model=requested_model,
            temperature=state.get("temperature", 0.25)
        )
    
    if _streaming_critic is None:
        _streaming_critic = StreamingCriticAgent()




def _default_intent() -> IntentResult:
    """Fallback для intent при ошибке."""
    return IntentResult(type="explain", confidence=0.5, description="Fallback")


@workflow_node(stage="intent", fallback_key="intent_result", fallback_value=_default_intent)
async def intent_node(state: AgentState) -> AgentState:
    """Узел для определения намерения пользователя."""
    _initialize_agents(state)
    task = state.get("task", "")
    
    logger.info("📋 Определяю намерение...")
    
    # Быстрая проверка на greeting (не требует LLM)
    if _intent_agent and IntentAgent.is_greeting_fast(task):
        intent_result = IntentResult(
            type="greeting",
            confidence=0.95,
            description="Приветствие пользователя"
        )
    elif _intent_agent:
        # LLM вызов в отдельном потоке
        intent_result = await asyncio.to_thread(
            _intent_agent.determine_intent, task
        )
    else:
        intent_result = IntentResult(
            type="explain",
            confidence=0.5,
            description="Агент не инициализирован"
        )
    
    state["intent_result"] = intent_result
    logger.info(f"✅ Намерение: {intent_result.type} ({intent_result.confidence:.2f})")
    
    return state


@workflow_node(stage="planning", fallback_key="plan", fallback_value="")
async def planner_node(state: AgentState) -> AgentState:
    """Узел для создания плана выполнения задачи.
    
    Для стриминга используйте stream_planner_node().
    """
    _initialize_agents(state)
    
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result or intent_result.type == "greeting":
        state["plan"] = ""
        return state
    
    logger.info("📝 Создаю план...")
    
    if _planner_agent:
        plan = await asyncio.to_thread(
            _planner_agent.create_plan,
            task=task,
            intent_type=intent_result.type
        )
        state["plan"] = plan
        logger.info(f"✅ План создан ({len(plan)} символов)")
    else:
        state["plan"] = ""
    
    return state


async def stream_planner_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия planner_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
            - ("thinking", sse_event)
            - ("plan_chunk", chunk)
            - ("done", state)
    """
    _initialize_streaming_agents(state)
    
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result or intent_result.type == "greeting":
        state["plan"] = ""
        yield ("done", state)
        return
    
    logger.info("📝 Стриминг плана...")
    
    if _streaming_planner:
        logger.info(f"✅ StreamingPlannerAgent инициализирован (модель: {_streaming_planner.model})")
        plan = ""
        event_count = 0
        async for event_type, data in _streaming_planner.create_plan_stream(
            task=task,
            intent_type=intent_result.type,
            stage="planning"
        ):
            event_count += 1
            logger.info(f"📤 Planner stream event #{event_count}: {event_type}, data_len={len(str(data)) if data else 0}")
            if event_type == "thinking":
                logger.info(f"🧠 Yielding thinking event из planner (SSE длина: {len(data) if isinstance(data, str) else 'N/A'})")
                yield ("thinking", data)
            elif event_type == "plan_chunk":
                yield ("plan_chunk", data)
            elif event_type == "done":
                plan = data
        
        state["plan"] = plan
        logger.info(f"✅ План создан ({len(plan)} символов, {event_count} событий)")
    else:
        logger.warning("⚠️ StreamingPlannerAgent не инициализирован!")
        state["plan"] = ""
    
    yield ("done", state)


@workflow_node(stage="research", fallback_key="context", fallback_value="")
async def researcher_node(state: AgentState) -> AgentState:
    """Узел для сбора контекста (codebase + RAG + веб-поиск)."""
    _initialize_agents(state)
    
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result or intent_result.type == "greeting":
        state["context"] = ""
        return state
    
    logger.info("🔍 Собираю контекст...")
    
    # Проверяем файл для modify/debug режима
    file_path = extract_file_path_from_task(task)
    file_context = None
    
    if file_path and intent_result.type in ['modify', 'debug']:
        file_content = await asyncio.to_thread(read_file_context, file_path)
        if file_content:
            file_context = prepare_modify_context(task, file_content)
            state["file_path"] = file_path
            state["file_context"] = file_context
            logger.info(f"📄 Файл для модификации: {file_path}")
    
    # Собираем контекст через Researcher
    if _researcher_agent:
        context = await asyncio.to_thread(
            _researcher_agent.research,
            query=task,
            intent_type=intent_result.type,
            disable_web_search=state.get("disable_web_search", False),
            project_path=state.get("project_path"),
            file_extensions=state.get("file_extensions")
        )
        
        if file_context:
            context = file_context + "\n\n---\n\n" + context if context else file_context
        
        state["context"] = context
        logger.info(f"✅ Контекст собран ({len(context)} символов)")
    else:
        state["context"] = file_context or ""
    
    return state


@workflow_node(stage="testing", fallback_key="tests", fallback_value="")
async def generator_node(state: AgentState) -> AgentState:
    """Узел для генерации тестов (TDD).
    
    Для стриминга используйте stream_generator_node().
    """
    _initialize_agents(state)
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["tests"] = ""
        return state
    
    logger.info("🧪 Генерирую тесты...")
    
    if _test_generator:
        tests = await asyncio.to_thread(
            _test_generator.generate_tests,
            plan=state.get("plan", ""),
            context=state.get("context", ""),
            intent_type=intent_result.type
        )
        state["tests"] = tests
        if tests:
            logger.info(f"✅ Тесты сгенерированы ({len(tests)} символов)")
    else:
        state["tests"] = ""
    
    return state


async def stream_generator_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия generator_node (тесты).
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    _initialize_streaming_agents(state)
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["tests"] = ""
        yield ("done", state)
        return
    
    logger.info("🧪 Стриминг тестов...")
    
    if _streaming_test_generator:
        tests = ""
        async for event_type, data in _streaming_test_generator.generate_tests_stream(
            plan=state.get("plan", ""),
            context=state.get("context", ""),
            intent_type=intent_result.type,
            stage="testing"
        ):
            if event_type == "thinking":
                yield ("thinking", data)
            elif event_type == "test_chunk":
                yield ("test_chunk", data)
            elif event_type == "done":
                tests = data
        
        state["tests"] = tests
        if tests:
            logger.info(f"✅ Тесты сгенерированы ({len(tests)} символов)")
    else:
        state["tests"] = ""
    
    yield ("done", state)


@workflow_node(stage="coding", fallback_key="code", fallback_value="")
async def coder_node(state: AgentState) -> AgentState:
    """Узел для генерации кода.
    
    Для COMPLEX задач использует IncrementalCoder (Compiler-in-the-Loop).
    Для SIMPLE/MEDIUM задач использует стандартный CoderAgent.
    Для стриминга используйте stream_coder_node().
    """
    _initialize_agents(state)
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["code"] = ""
        return state
    
    logger.info("💻 Генерирую код...")
    
    # Проверяем сложность задачи
    complexity = getattr(intent_result, 'complexity', TaskComplexity.SIMPLE)
    
    # Проверяем конфиг для инкрементальной генерации
    config = get_config()
    incremental_config = config._config_data.get("incremental_coding", {})
    incremental_enabled = incremental_config.get("enabled", False)
    min_complexity = incremental_config.get("min_complexity", "complex")
    
    # Определяем использовать ли инкрементальную генерацию
    use_incremental = (
        incremental_enabled and
        complexity == TaskComplexity.COMPLEX and
        min_complexity in ("simple", "medium", "complex")
    )
    
    if use_incremental:
        # Инкрементальная генерация для complex задач
        logger.info("⚡ Используем инкрементальную генерацию (Compiler-in-the-Loop)...")
        
        incremental_coder = IncrementalCoder(model=state.get("model"))
        
        code_parts = []
        async for step in incremental_coder.generate_with_feedback(
            plan=state.get("plan", ""),
            tests=state.get("tests", ""),
            context=state.get("context", "")
        ):
            code_parts.append(step.code)
            logger.info(
                f"  📦 {step.function_name}: "
                f"{'✅' if step.tests_passed else '❌'} "
                f"(попыток: {step.fix_attempts})"
            )
        
        state["code"] = "\n\n".join(code_parts)
        if state["code"]:
            logger.info(f"✅ Код сгенерирован инкрементально ({len(state['code'])} символов)")
    else:
        # Стандартная генерация для simple/medium задач
        if _coder_agent:
            code = await asyncio.to_thread(
                _coder_agent.generate_code,
                plan=state.get("plan", ""),
                tests=state.get("tests", ""),
                context=state.get("context", ""),
                intent_type=intent_result.type
            )
            state["code"] = code
            if code:
                logger.info(f"✅ Код сгенерирован ({len(code)} символов)")
        else:
            state["code"] = ""
    
    return state


async def stream_coder_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия coder_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
            - ("thinking", sse_event) — рассуждения модели
            - ("code_chunk", chunk) — чанк кода
            - ("done", state)
    """
    _initialize_streaming_agents(state)
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["code"] = ""
        yield ("done", state)
        return
    
    logger.info("💻 Стриминг кода...")
    
    if _streaming_coder:
        code = ""
        async for event_type, data in _streaming_coder.generate_code_stream(
            plan=state.get("plan", ""),
            tests=state.get("tests", ""),
            context=state.get("context", ""),
            intent_type=intent_result.type,
            stage="coding"
        ):
            if event_type == "thinking":
                yield ("thinking", data)
            elif event_type == "code_chunk":
                yield ("code_chunk", data)
            elif event_type == "done":
                code = data
        
        state["code"] = code
        if code:
            logger.info(f"✅ Код сгенерирован ({len(code)} символов)")
    else:
        state["code"] = ""
    
    yield ("done", state)


def _default_validation() -> dict:
    """Fallback для validation при ошибке."""
    return {
        "pytest": {"success": False, "output": "Validation error"},
        "mypy": {"success": False, "errors": "Validation error"},
        "bandit": {"success": False, "issues": "Validation error"},
        "all_passed": False
    }


@workflow_node(stage="validation", fallback_key="validation_results", fallback_value=_default_validation)
async def validator_node(state: AgentState) -> AgentState:
    """Узел для валидации кода (pytest, mypy, bandit)."""
    logger.info("🔍 Валидирую код...")
    
    validation_results = await asyncio.to_thread(
        validate_code,
        code_str=state.get("code", ""),
        test_str=state.get("tests") or None
    )
    state["validation_results"] = validation_results
    
    if validation_results.get("all_passed", False):
        logger.info("✅ Валидация пройдена")
    else:
        logger.warning("⚠️ Валидация не пройдена")
    
    return state


@workflow_node(stage="debug", fallback_key="debug_result", fallback_value=None)
async def debugger_node(state: AgentState) -> AgentState:
    """Узел для анализа ошибок.
    
    Для стриминга используйте stream_debugger_node().
    """
    _initialize_agents(state)
    
    logger.info("🐛 Анализирую ошибки...")
    
    if _debugger_agent:
        debug_result = await asyncio.to_thread(
            _debugger_agent.analyze_errors,
            validation_results=state.get("validation_results", {}),
            code=state.get("code", ""),
            tests=state.get("tests", ""),
            task=state.get("task", "")
        )
        state["debug_result"] = debug_result
        logger.info(f"✅ Анализ завершён. Тип: {debug_result.error_type}")
    else:
        state["debug_result"] = None
    
    return state


async def stream_debugger_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия debugger_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    _initialize_streaming_agents(state)
    
    logger.info("🐛 Стриминг анализа ошибок...")
    
    if _streaming_debugger:
        debug_result = None
        async for event_type, data in _streaming_debugger.analyze_errors_stream(
            validation_results=state.get("validation_results", {}),
            code=state.get("code", ""),
            tests=state.get("tests", ""),
            task=state.get("task", ""),
            stage="debugging"
        ):
            if event_type == "thinking":
                yield ("thinking", data)
            elif event_type == "analysis_chunk":
                yield ("analysis_chunk", data)
            elif event_type == "done":
                debug_result = data
        
        state["debug_result"] = debug_result
        if debug_result:
            logger.info(f"✅ Анализ завершён. Тип: {debug_result.error_type}")
    else:
        state["debug_result"] = None
    
    yield ("done", state)


@workflow_node(stage="fixing")
async def fixer_node(state: AgentState) -> AgentState:
    """Узел для исправления кода по инструкциям от Debugger.
    
    Для стриминга используйте stream_fixer_node().
    """
    _initialize_agents(state)
    
    # Увеличиваем счетчик итераций
    state["iteration"] = state.get("iteration", 0) + 1
    
    debug_result = state.get("debug_result")
    if not debug_result or not debug_result.fix_instructions:
        logger.warning("⚠️ Нет инструкций для исправления")
        return state
    
    logger.info(f"🔧 Исправляю код (итерация {state['iteration']})...")
    
    if _coder_agent:
        fixed_code = await asyncio.to_thread(
            _coder_agent.fix_code,
            code=state.get("code", ""),
            instructions=debug_result.fix_instructions,
            tests=state.get("tests", ""),
            validation_results=state.get("validation_results", {})
        )
        if fixed_code:
            state["code"] = fixed_code
            logger.info(f"✅ Код исправлен ({len(fixed_code)} символов)")
    
    return state


async def stream_fixer_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия fixer_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    _initialize_streaming_agents(state)
    
    state["iteration"] = state.get("iteration", 0) + 1
    
    debug_result = state.get("debug_result")
    if not debug_result or not debug_result.fix_instructions:
        logger.warning("⚠️ Нет инструкций для исправления")
        yield ("done", state)
        return
    
    logger.info(f"🔧 Стриминг исправления (итерация {state['iteration']})...")
    
    if _streaming_coder:
        fixed_code = ""
        async for event_type, data in _streaming_coder.fix_code_stream(
            code=state.get("code", ""),
            instructions=debug_result.fix_instructions,
            tests=state.get("tests", ""),
            validation_results=state.get("validation_results", {}),
            stage="fixing"
        ):
            if event_type == "thinking":
                yield ("thinking", data)
            elif event_type == "code_chunk":
                yield ("code_chunk", data)
            elif event_type == "done":
                fixed_code = data
        
        if fixed_code:
            state["code"] = fixed_code
            logger.info(f"✅ Код исправлен ({len(fixed_code)} символов)")
    
    yield ("done", state)


@workflow_node(stage="reflection", fallback_key="reflection_result", fallback_value=None)
async def reflection_node(state: AgentState) -> AgentState:
    """Узел для рефлексии и оценки результатов.
    
    Для стриминга используйте stream_reflection_node().
    """
    _initialize_agents(state)
    
    intent_result = state.get("intent_result")
    if not _reflection_agent or not intent_result:
        state["reflection_result"] = None
        return state
    
    logger.info("🔍 Анализирую результаты...")
    
    reflection_result = await asyncio.to_thread(
        _reflection_agent.reflect,
        task=state.get("task", ""),
        plan=state.get("plan", ""),
        context=state.get("context", ""),
        tests=state.get("tests", ""),
        code=state.get("code", ""),
        validation_results=state.get("validation_results", {})
    )
    state["reflection_result"] = reflection_result
    
    # Сохраняем опыт в память
    memory_agent = _get_memory_agent()
    await asyncio.to_thread(
        memory_agent.save_task_experience,
        task=state.get("task", ""),
        intent_type=intent_result.type,
        reflection_result=reflection_result,
        key_decisions=state.get("plan", "")[:500],
        what_worked=reflection_result.analysis
    )
    
    logger.info(f"✅ Рефлексия завершена. Оценка: {reflection_result.overall_score:.2f}")
    return state


async def stream_reflection_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия reflection_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    _initialize_streaming_agents(state)
    
    intent_result = state.get("intent_result")
    if not _streaming_reflection or not intent_result:
        state["reflection_result"] = None
        yield ("done", state)
        return
    
    logger.info("🔍 Стриминг рефлексии...")
    
    reflection_result = None
    async for event_type, data in _streaming_reflection.reflect_stream(
        task=state.get("task", ""),
        plan=state.get("plan", ""),
        context=state.get("context", ""),
        tests=state.get("tests", ""),
        code=state.get("code", ""),
        validation_results=state.get("validation_results", {}),
        stage="reflection"
    ):
        if event_type == "thinking":
            yield ("thinking", data)
        elif event_type == "reflection_chunk":
            yield ("reflection_chunk", data)
        elif event_type == "done":
            reflection_result = data
    
    state["reflection_result"] = reflection_result
    
    # Сохраняем опыт в память
    if reflection_result:
        memory_agent = _get_memory_agent()
        await asyncio.to_thread(
            memory_agent.save_task_experience,
            task=state.get("task", ""),
            intent_type=intent_result.type,
            reflection_result=reflection_result,
            key_decisions=state.get("plan", "")[:500],
            what_worked=reflection_result.analysis
        )
        logger.info(f"✅ Рефлексия завершена. Оценка: {reflection_result.overall_score:.2f}")
    
    yield ("done", state)


@workflow_node(stage="critic", fallback_key="critic_report", fallback_value=None)
async def critic_node(state: AgentState) -> AgentState:
    """Узел для критического анализа кода.
    
    Включает multi-agent дебаты если enabled в config.
    Для стриминга используйте stream_critic_node().
    """
    _initialize_agents(state)
    
    code = state.get("code", "")
    if not _critic_agent or not code:
        state["critic_report"] = None
        return state
    
    # Phase 5: Multi-Agent Debate
    if is_debate_enabled():
        logger.info("🎭 Запускаю multi-agent дебаты...")
        final_code, debate_result = await run_debate_if_enabled(
            code=code,
            tests=state.get("tests", ""),
            task=state.get("task", ""),
            model=state.get("model")
        )
        
        if debate_result:
            state["debate_result"] = debate_result.to_dict()  # type: ignore[typeddict-unknown-key]
            if final_code != code:
                state["code"] = final_code
                logger.info(f"💬 Код обновлён после дебатов ({debate_result.total_rounds} раундов)")
    
    logger.info("🔎 Критический анализ кода...")
    
    critic_report = await asyncio.to_thread(
        _critic_agent.analyze,
        code=state.get("code", code),  # Используем обновлённый код
        tests=state.get("tests", ""),
        task_description=state.get("task", ""),
        validation_results=state.get("validation_results", {})
    )
    state["critic_report"] = critic_report
    logger.info(f"✅ Критический анализ завершён. Оценка: {critic_report.overall_score:.2f}")
    
    return state


async def stream_critic_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], AgentState]:
    """Стриминговая версия critic_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    _initialize_streaming_agents(state)
    
    code = state.get("code", "")
    if not _streaming_critic or not code:
        state["critic_report"] = None
        yield ("done", state)
        return
    
    logger.info("🔎 Стриминг критического анализа...")
    
    critic_report = None
    async for event_type, data in _streaming_critic.analyze_stream(
        code=code,
        tests=state.get("tests", ""),
        task_description=state.get("task", ""),
        validation_results=state.get("validation_results", {}),
        stage="critic"
    ):
        if event_type == "static_analysis":
            yield ("static_analysis", data)
        elif event_type == "thinking":
            yield ("thinking", data)
        elif event_type == "critic_chunk":
            yield ("critic_chunk", data)
        elif event_type == "done":
            critic_report = data
    
    state["critic_report"] = critic_report
    if critic_report:
        logger.info(f"✅ Критический анализ завершён. Оценка: {critic_report.overall_score:.2f}")
    
    yield ("done", state)


# === Вспомогательные функции ===

def get_streaming_node(node_name: str):
    """Возвращает стриминговую версию узла по имени.
    
    Args:
        node_name: Имя узла (planner, generator, coder, debugger, fixer, reflection, critic)
        
    Returns:
        Функция стриминговой версии узла или None
    """
    streaming_nodes = {
        "planner": stream_planner_node,
        "generator": stream_generator_node,
        "coder": stream_coder_node,
        "debugger": stream_debugger_node,
        "fixer": stream_fixer_node,
        "reflection": stream_reflection_node,
        "critic": stream_critic_node,
    }
    return streaming_nodes.get(node_name)
