"""Узлы (nodes) для LangGraph workflow.

Каждый узел соответствует одному агенту в workflow.
Агенты инициализируются лениво при первом вызове.
MemoryAgent используется через DependencyContainer (Singleton).

ВАЖНО: Все узлы теперь асинхронные (async def) для совместимости с FastAPI.
Тяжёлые LLM операции выполняются через asyncio.to_thread() чтобы не блокировать event loop.

Обработка ошибок, метрики и checkpoints — через декоратор @workflow_node.
"""
import asyncio
from typing import TYPE_CHECKING
from infrastructure.workflow_state import AgentState
from infrastructure.workflow_decorators import workflow_node
from agents.intent import IntentAgent, IntentResult
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.reflection import ReflectionAgent
from agents.critic import CriticAgent, get_critic_agent
from backend.dependencies import get_memory_agent
from utils.validation import validate_code
from utils.config import get_config
from utils.logger import get_logger
from utils.file_context import extract_file_path_from_task, read_file_context, prepare_modify_context

if TYPE_CHECKING:
    from agents.memory import MemoryAgent

logger = get_logger()

# Глобальные агенты (инициализируются один раз)
# MemoryAgent теперь через DependencyContainer
_intent_agent: IntentAgent | None = None
_planner_agent: PlannerAgent | None = None
_researcher_agent: ResearcherAgent | None = None
_test_generator: TestGeneratorAgent | None = None
_coder_agent: CoderAgent | None = None
_debugger_agent: DebuggerAgent | None = None
_reflection_agent: ReflectionAgent | None = None
_critic_agent: CriticAgent | None = None


def _get_memory_agent() -> 'MemoryAgent':
    """Возвращает глобальный MemoryAgent через DependencyContainer.
    
    Returns:
        Singleton экземпляр MemoryAgent
    """
    return get_memory_agent()


def _initialize_agents(state: AgentState) -> None:
    """Инициализирует агентов если они ещё не инициализированы.
    
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
    """Узел для создания плана выполнения задачи."""
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
    """Узел для генерации тестов (TDD)."""
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


@workflow_node(stage="coding", fallback_key="code", fallback_value="")
async def coder_node(state: AgentState) -> AgentState:
    """Узел для генерации кода."""
    _initialize_agents(state)
    
    intent_result = state.get("intent_result")
    if not intent_result or intent_result.type == "greeting":
        state["code"] = ""
        return state
    
    logger.info("💻 Генерирую код...")
    
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
    """Узел для анализа ошибок."""
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


@workflow_node(stage="fixing")
async def fixer_node(state: AgentState) -> AgentState:
    """Узел для исправления кода по инструкциям от Debugger."""
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


@workflow_node(stage="reflection", fallback_key="reflection_result", fallback_value=None)
async def reflection_node(state: AgentState) -> AgentState:
    """Узел для рефлексии и оценки результатов."""
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


@workflow_node(stage="critic", fallback_key="critic_report", fallback_value=None)
async def critic_node(state: AgentState) -> AgentState:
    """Узел для критического анализа кода."""
    _initialize_agents(state)
    
    code = state.get("code", "")
    if not _critic_agent or not code:
        state["critic_report"] = None
        return state
    
    logger.info("🔎 Критический анализ кода...")
    
    critic_report = await asyncio.to_thread(
        _critic_agent.analyze,
        code=code,
        tests=state.get("tests", ""),
        task_description=state.get("task", ""),
        validation_results=state.get("validation_results", {})
    )
    state["critic_report"] = critic_report
    logger.info(f"✅ Критический анализ завершён. Оценка: {critic_report.overall_score:.2f}")
    
    return state
