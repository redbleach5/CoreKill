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
from backend.dependencies import (
    get_memory_agent,
    get_intent_agent,
    get_planner_agent,
    get_researcher_agent,
    get_test_generator_agent,
    get_coder_agent,
    get_debugger_agent,
    get_reflection_agent,
    get_critic_agent,
    get_streaming_planner_agent,
    get_streaming_test_generator_agent,
    get_streaming_coder_agent,
    get_streaming_debugger_agent,
    get_streaming_reflection_agent,
    get_streaming_critic_agent
)
from utils.validation import validate_code
from utils.config import get_config
from utils.logger import get_logger
from utils.file_context import extract_file_path_from_task, read_file_context, prepare_modify_context
from infrastructure.workflow_config import get_workflow_config
# Синхронные агенты (fallback) - используются только для типизации
from agents.planner import PlannerAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.critic import CriticAgent
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
        workflow_config = get_workflow_config()
        return workflow_config.streaming_enabled
    except Exception:
        return False


def _get_streaming_node_adapter(streaming_node_func, stage_name: str, fallback_key: str = "", fallback_value: Any = ""):
    """Создаёт адаптер для стримингового узла, совместимый с LangGraph.
    
    Адаптер использует EventStore для хранения событий вне state,
    предотвращая раздувание состояния при длительных задачах.
    
    Args:
        streaming_node_func: Функция стримингового узла (stream_planner_node, etc.)
        stage_name: Название этапа для декоратора
        fallback_key: Ключ в state для fallback значения
        fallback_value: Fallback значение при ошибке
        
    Returns:
        Функция-адаптер, совместимая с LangGraph (принимает и возвращает AgentState)
    """
    @workflow_node(stage=stage_name, fallback_key=fallback_key if fallback_key else None, fallback_value=fallback_value)
    async def adapter(state: AgentState) -> AgentState:
        """Адаптер для стримингового узла с использованием EventStore."""
        # Получаем session_id для изоляции событий
        session_id = state.get("task_id") or state.get("session_id") or "default"
        
        # Инициализируем EventStore для сессии
        from infrastructure.event_store import get_event_store
        event_store = await get_event_store(session_id)
        
        # Инициализируем список ссылок на события если его нет или он None
        if "event_references" not in state or state.get("event_references") is None:
            state["event_references"] = []
        
        # Вызываем стриминговый узел и сохраняем события в EventStore
        final_state = None
        try:
            async for event_type, data in streaming_node_func(state):
                if event_type == "done":
                    final_state = data
                else:
                    # Сохраняем событие в EventStore и получаем ID
                    event_id = await event_store.save_event(event_type, data)
                    # Сохраняем только ID события в state (не сами данные)
                    # Убеждаемся что event_references это список
                    if state.get("event_references") is None:
                        state["event_references"] = []
                    state["event_references"].append(event_id)
                    
                    logger.debug(
                        f"💾 Событие сохранено в EventStore: {event_type} "
                        f"(ID: {event_id[:8]}..., всего ссылок: {len(state['event_references'])})"
                    )
        except Exception as e:
            logger.error(f"❌ Ошибка в стриминговом узле {stage_name}: {e}", error=e)
            # Возвращаем state с fallback значением
            if fallback_key:
                state[fallback_key] = fallback_value
        
        # Возвращаем финальный state (или исходный если не получен)
        if final_state:
            # Сохраняем ссылки на события в финальном state
            final_state["event_references"] = state.get("event_references", [])
            return final_state
        
        return state
    
    return adapter


def _get_memory_agent() -> 'MemoryAgent':
    """Возвращает глобальный MemoryAgent через DependencyContainer.
    
    Returns:
        Singleton экземпляр MemoryAgent
    """
    return get_memory_agent()


def _get_agent_from_container(agent_type: str, state: AgentState) -> Any:
    """Получает агента через DependencyContainer (thread-safe).
    
    Args:
        agent_type: Тип агента (intent, planner, coder, etc.)
        state: State с параметрами для инициализации
        
    Returns:
        Экземпляр агента
    """
    model = state.get("model")
    temperature = state.get("temperature", 0.25)
    memory_agent = _get_memory_agent()
    
    if agent_type == "intent":
        return get_intent_agent(model=None, temperature=0.2)
    elif agent_type == "planner":
        return get_planner_agent(model=model, temperature=temperature, memory_agent=memory_agent)
    elif agent_type == "researcher":
        return get_researcher_agent(memory_agent=memory_agent)
    elif agent_type == "test_generator":
        return get_test_generator_agent(model=model, temperature=0.18)
    elif agent_type == "coder":
        return get_coder_agent(model=model, temperature=temperature)
    elif agent_type == "debugger":
        return get_debugger_agent(model=model, temperature=0.2)
    elif agent_type == "reflection":
        return get_reflection_agent(model=model, temperature=temperature)
    elif agent_type == "critic":
        return get_critic_agent()
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def _get_streaming_agent_for_state(agent_type: str, state: AgentState) -> Any:
    """Лениво получает стримингового агента для конкретного state.
    
    Использует DependencyContainer для потокобезопасного кэширования.
    
    Args:
        agent_type: Тип агента (planner, coder, test_generator, etc.)
        state: State с параметрами для инициализации
        
    Returns:
        Экземпляр стримингового агента или None если стриминг отключён
    """
    if not _is_streaming_enabled():
        return None
    
    model = state.get("model")
    temperature = state.get("temperature", 0.25)
    memory_agent = _get_memory_agent()
    
    if agent_type == "planner":
        return get_streaming_planner_agent(
            model=None,  # Авто-выбор быстрой модели для planning
            temperature=temperature,
            memory_agent=memory_agent
        )
    elif agent_type == "test_generator":
        return get_streaming_test_generator_agent(
            model=model,
            temperature=0.18
        )
    elif agent_type == "coder":
        return get_streaming_coder_agent(
            model=model,
            temperature=temperature
        )
    elif agent_type == "debugger":
        return get_streaming_debugger_agent(
            model=model,
            temperature=0.2
        )
    elif agent_type == "reflection":
        return get_streaming_reflection_agent(
            model=model,
            temperature=temperature
        )
    elif agent_type == "critic":
        return get_streaming_critic_agent()
    else:
        raise ValueError(f"Unknown streaming agent type: {agent_type}")




def _default_intent() -> IntentResult:
    """Fallback для intent при ошибке."""
    return IntentResult(type="explain", confidence=0.5, description="Fallback")


@workflow_node(stage="intent", fallback_key="intent_result", fallback_value=_default_intent)
async def intent_node(state: AgentState) -> AgentState:
    """Узел для определения намерения пользователя."""
    task = state.get("task", "")
    
    logger.info("📋 Определяю намерение...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    intent_agent = _get_agent_from_container("intent", state)
    
    # Быстрая проверка на greeting (не требует LLM)
    if IntentAgent.is_greeting_fast(task):
        intent_result = IntentResult(
            type="greeting",
            confidence=0.95,
            description="Приветствие пользователя"
        )
    else:
        # LLM вызов в отдельном потоке
        intent_result = await asyncio.to_thread(
            intent_agent.determine_intent, task
        )
    
    state["intent_result"] = intent_result
    logger.info(f"✅ Намерение: {intent_result.type} ({intent_result.confidence:.2f})")
    
    return state


@workflow_node(stage="planning", fallback_key="plan", fallback_value="")
async def planner_node(state: AgentState) -> AgentState:
    """Узел для создания плана выполнения задачи.
    
    Для стриминга используйте stream_planner_node().
    """
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result or intent_result.type == "greeting":
        state["plan"] = ""
        return state
    
    logger.info("📝 Создаю план...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    planner_agent = _get_agent_from_container("planner", state)
    plan = await asyncio.to_thread(
        planner_agent.create_plan,
        task=task,
        intent_type=intent_result.type
    )
    state["plan"] = plan
    if plan:
        logger.info(f"✅ План создан ({len(plan)} символов)")
    
    return state


async def stream_planner_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия planner_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
            - ("thinking", sse_event)
            - ("plan_chunk", chunk)
            - ("done", state)
    """
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result or intent_result.type == "greeting":
        state["plan"] = ""
        yield ("done", state)
        return
    
    logger.info("📝 Стриминг плана...")
    
    streaming_planner = _get_streaming_agent_for_state("planner", state)
    
    if streaming_planner:
        logger.info(f"✅ StreamingPlannerAgent получен (модель: {streaming_planner.model})")
        plan = ""
        event_count = 0
        async for event_type, data in streaming_planner.create_plan_stream(
            task=task,
            intent_type=intent_result.type,
            stage="planning"
        ):
            event_count += 1
            logger.debug(f"📤 Planner stream event #{event_count}: {event_type}")
            if event_type == "thinking":
                yield ("thinking", data)
            elif event_type == "plan_chunk":
                yield ("plan_chunk", data)
            elif event_type == "done":
                plan = data
        
        state["plan"] = plan
        logger.info(f"✅ План создан ({len(plan)} символов, {event_count} событий)")
    else:
        logger.warning("⚠️ StreamingPlannerAgent недоступен!")
        state["plan"] = ""
    
    yield ("done", state)


@workflow_node(stage="research", fallback_key="context", fallback_value="")
async def researcher_node(state: AgentState) -> AgentState:
    """Узел для сбора контекста (codebase + RAG + веб-поиск)."""
    
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
    researcher_agent = _get_agent_from_container("researcher", state)
    context = await asyncio.to_thread(
        researcher_agent.research,
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
    
    return state


@workflow_node(stage="testing", fallback_key="tests", fallback_value="")
async def generator_node(state: AgentState) -> AgentState:
    """Узел для генерации тестов (TDD).
    
    Для стриминга используйте stream_generator_node().
    """
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["tests"] = ""
        return state
    
    logger.info("🧪 Генерирую тесты...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    test_generator = _get_agent_from_container("test_generator", state)
    tests = await asyncio.to_thread(
        test_generator.generate_tests,
        plan=state.get("plan", ""),
        context=state.get("context", ""),
        intent_type=intent_result.type
    )
    state["tests"] = tests
    if tests:
        logger.info(f"✅ Тесты сгенерированы ({len(tests)} символов)")
    
    return state


async def stream_generator_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия generator_node (тесты).
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["tests"] = ""
        yield ("done", state)
        return
    
    logger.info("🧪 Стриминг тестов...")
    
    streaming_test_generator = _get_streaming_agent_for_state("test_generator", state)
    
    if streaming_test_generator:
        tests = ""
        async for event_type, data in streaming_test_generator.generate_tests_stream(
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
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["code"] = ""
        return state
    
    logger.info("💻 Генерирую код...")
    
    # Проверяем сложность задачи
    complexity = getattr(intent_result, 'complexity', TaskComplexity.SIMPLE)
    
    # Используем WorkflowConfig для проверки инкрементальной генерации
    workflow_config = get_workflow_config()
    use_incremental = workflow_config.should_use_incremental(complexity)
    
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
        coder_agent = _get_agent_from_container("coder", state)
        code = await asyncio.to_thread(
            coder_agent.generate_code,
            plan=state.get("plan", ""),
            tests=state.get("tests", ""),
            context=state.get("context", ""),
            intent_type=intent_result.type
        )
        state["code"] = code
        if code:
            logger.info(f"✅ Код сгенерирован ({len(code)} символов)")
    
    return state


async def stream_coder_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия coder_node.
    
    Поддерживает инкрементальную генерацию для COMPLEX задач (как и обычный coder_node).
    
    Yields:
        tuple[event_type, data]: События для SSE
            - ("thinking", sse_event) — рассуждения модели
            - ("code_chunk", chunk) — чанк кода
            - ("done", state)
    """
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["code"] = ""
        yield ("done", state)
        return
    
    logger.info("💻 Стриминг кода...")
    
    # Проверяем сложность задачи
    from utils.model_checker import TaskComplexity
    complexity = getattr(intent_result, 'complexity', TaskComplexity.SIMPLE)
    
    # Используем WorkflowConfig для проверки инкрементальной генерации
    workflow_config = get_workflow_config()
    use_incremental = workflow_config.should_use_incremental(complexity)
    
    if use_incremental:
        # Инкрементальная генерация для complex задач
        logger.info("⚡ Используем инкрементальную генерацию (Compiler-in-the-Loop) в стриминге...")
        
        incremental_coder = IncrementalCoder(model=state.get("model"))
        
        code_parts = []
        async for step in incremental_coder.generate_with_feedback(
            plan=state.get("plan", ""),
            tests=state.get("tests", ""),
            context=state.get("context", "")
        ):
            code_parts.append(step.code)
            # Отправляем событие о прогрессе инкрементальной генерации
            yield ("code_chunk", f"# {step.function_name}: {'✅' if step.tests_passed else '❌'}\n{step.code}\n")
            logger.info(
                f"  📦 {step.function_name}: "
                f"{'✅' if step.tests_passed else '❌'} "
                f"(попыток: {step.fix_attempts})"
            )
        
        state["code"] = "\n\n".join(code_parts)
        if state["code"]:
            logger.info(f"✅ Код сгенерирован инкрементально ({len(state['code'])} символов)")
    else:
        # Стандартная стриминговая генерация для simple/medium задач
        streaming_coder = _get_streaming_agent_for_state("coder", state)
        
        if streaming_coder:
            code = ""
            async for event_type, data in streaming_coder.generate_code_stream(
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
    logger.info("🐛 Анализирую ошибки...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    debugger_agent = _get_agent_from_container("debugger", state)
    debug_result = await asyncio.to_thread(
        debugger_agent.analyze_errors,
        validation_results=state.get("validation_results", {}),
        code=state.get("code", ""),
        tests=state.get("tests", ""),
        task=state.get("task", "")
    )
    state["debug_result"] = debug_result
    logger.info(f"✅ Анализ завершён. Тип: {debug_result.error_type}")
    
    return state


async def stream_debugger_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия debugger_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    logger.info("🐛 Стриминг анализа ошибок...")
    
    streaming_debugger = _get_streaming_agent_for_state("debugger", state)
    
    if streaming_debugger:
        debug_result = None
        async for event_type, data in streaming_debugger.analyze_errors_stream(
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
    
    # Увеличиваем счетчик итераций
    state["iteration"] = state.get("iteration", 0) + 1
    
    debug_result = state.get("debug_result")
    if not debug_result or not debug_result.fix_instructions:
        logger.warning("⚠️ Нет инструкций для исправления")
        return state
    
    logger.info(f"🔧 Исправляю код (итерация {state['iteration']})...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    coder_agent = _get_agent_from_container("coder", state)
    fixed_code = await asyncio.to_thread(
        coder_agent.fix_code,
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
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия fixer_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    state["iteration"] = state.get("iteration", 0) + 1
    
    debug_result = state.get("debug_result")
    if not debug_result or not debug_result.fix_instructions:
        logger.warning("⚠️ Нет инструкций для исправления")
        yield ("done", state)
        return
    
    logger.info(f"🔧 Стриминг исправления (итерация {state['iteration']})...")
    
    streaming_coder = _get_streaming_agent_for_state("coder", state)
    
    if streaming_coder:
        fixed_code = ""
        async for event_type, data in streaming_coder.fix_code_stream(
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
    intent_result = state.get("intent_result")
    if not intent_result:
        state["reflection_result"] = None
        return state
    
    logger.info("🔍 Анализирую результаты...")
    
    # Получаем агента через DependencyContainer (thread-safe)
    reflection_agent = _get_agent_from_container("reflection", state)
    reflection_result = await asyncio.to_thread(
        reflection_agent.reflect,
        task=state.get("task", ""),
        plan=state.get("plan", ""),
        context=state.get("context", ""),
        tests=state.get("tests", ""),
        code=state.get("code", ""),
        validation_results=state.get("validation_results", {})
    )
    state["reflection_result"] = reflection_result
    
    # Сохраняем опыт в память (включая код и план для переиспользования)
    memory_agent = _get_memory_agent()
    await asyncio.to_thread(
        memory_agent.save_task_experience,
        task=state.get("task", ""),
        intent_type=intent_result.type,
        reflection_result=reflection_result,
        key_decisions=state.get("plan", "")[:500],
        what_worked=reflection_result.analysis,
        code=state.get("code", ""),  # Сохраняем готовый код
        plan=state.get("plan", "")  # Сохраняем план
    )
    
    logger.info(f"✅ Рефлексия завершена. Оценка: {reflection_result.overall_score:.2f}")
    return state


async def stream_reflection_node(
    state: AgentState
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия reflection_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    intent_result = state.get("intent_result")
    if not intent_result:
        state["reflection_result"] = None
        yield ("done", state)
        return
    
    streaming_reflection = _get_streaming_agent_for_state("reflection", state)
    
    if not streaming_reflection:
        state["reflection_result"] = None
        yield ("done", state)
        return
    
    logger.info("🔍 Стриминг рефлексии...")
    
    reflection_result = None
    async for event_type, data in streaming_reflection.reflect_stream(
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
    
    # Сохраняем опыт в память (включая код и план для переиспользования)
    if reflection_result:
        memory_agent = _get_memory_agent()
        await asyncio.to_thread(
            memory_agent.save_task_experience,
            task=state.get("task", ""),
            intent_type=intent_result.type,
            reflection_result=reflection_result,
            key_decisions=state.get("plan", "")[:500],
            what_worked=reflection_result.analysis,
            code=state.get("code", ""),  # Сохраняем готовый код
            plan=state.get("plan", "")  # Сохраняем план
        )
        logger.info(f"✅ Рефлексия завершена. Оценка: {reflection_result.overall_score:.2f}")
    
    yield ("done", state)


@workflow_node(stage="critic", fallback_key="critic_report", fallback_value=None)
async def critic_node(state: AgentState) -> AgentState:
    """Узел для критического анализа кода.
    
    Включает multi-agent дебаты если enabled в config.
    Для стриминга используйте stream_critic_node().
    """
    code = state.get("code", "")
    if not code:
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
    
    # Получаем агента через DependencyContainer (thread-safe)
    critic_agent = _get_agent_from_container("critic", state)
    critic_report = await asyncio.to_thread(
        critic_agent.analyze,
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
) -> AsyncGenerator[tuple[str, Any], None]:
    """Стриминговая версия critic_node.
    
    Yields:
        tuple[event_type, data]: События для SSE
    """
    code = state.get("code", "")
    if not code:
        state["critic_report"] = None
        yield ("done", state)
        return
    
    streaming_critic = _get_streaming_agent_for_state("critic", state)
    
    if not streaming_critic:
        state["critic_report"] = None
        yield ("done", state)
        return
    
    logger.info("🔎 Стриминг критического анализа...")
    
    critic_report = None
    async for event_type, data in streaming_critic.analyze_stream(
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
