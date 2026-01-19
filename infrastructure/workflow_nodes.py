"""Узлы (nodes) для LangGraph workflow."""
from typing import TYPE_CHECKING
from infrastructure.workflow_state import AgentState
from agents.intent import IntentAgent, IntentResult
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent, DebugResult
from agents.reflection import ReflectionAgent, ReflectionResult
from agents.critic import CriticAgent, get_critic_agent, CriticReport
from agents.memory import MemoryAgent
from utils.validation import validate_code
from utils.logger import get_logger
from utils.file_context import extract_file_path_from_task, read_file_context, prepare_modify_context

if TYPE_CHECKING:
    from backend.sse_manager import SSEManager

logger = get_logger()

# Глобальные агенты (инициализируются один раз)
_memory_agent: MemoryAgent | None = None
_intent_agent: IntentAgent | None = None
_planner_agent: PlannerAgent | None = None
_researcher_agent: ResearcherAgent | None = None
_test_generator: TestGeneratorAgent | None = None
_coder_agent: CoderAgent | None = None
_debugger_agent: DebuggerAgent | None = None
_reflection_agent: ReflectionAgent | None = None
_critic_agent: CriticAgent | None = None


def _initialize_agents(state: AgentState) -> None:
    """Инициализирует агентов если они ещё не инициализированы.
    
    Args:
        state: State с параметрами для инициализации
    """
    global _memory_agent, _intent_agent, _planner_agent, _researcher_agent
    global _test_generator, _coder_agent, _debugger_agent, _reflection_agent, _critic_agent
    
    if _memory_agent is None:
        _memory_agent = MemoryAgent()
    
    if _intent_agent is None:
        _intent_agent = IntentAgent(model=None, temperature=0.2)
    
    if _planner_agent is None:
        _planner_agent = PlannerAgent(
            model=state.get("model"),
            temperature=state.get("temperature", 0.25),
            memory_agent=_memory_agent
        )
    
    if _researcher_agent is None:
        _researcher_agent = ResearcherAgent(memory_agent=_memory_agent)
    
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




def intent_node(state: AgentState) -> AgentState:
    """Узел для определения намерения пользователя.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с intent_result
    """
    _initialize_agents(state)
    
    task = state.get("task", "")
    
    logger.info("📋 Определяю намерение...")
    
    try:
        # Быстрая проверка на greeting
        if _intent_agent and IntentAgent.is_greeting_fast(task):
            intent_result = IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие пользователя"
            )
        elif _intent_agent:
            intent_result = _intent_agent.determine_intent(task)
        else:
            # Fallback если агент не инициализирован
            intent_result = IntentResult(
                type="explain",
                confidence=0.5,
                description="Не удалось определить намерение"
            )
        
        state["intent_result"] = intent_result
        logger.info(f"✅ Намерение определено: {intent_result.type} (уверенность: {intent_result.confidence:.2f})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка определения намерения: {e}", error=e)
        # Fallback на explain
        state["intent_result"] = IntentResult(
            type="explain",
            confidence=0.5,
            description=f"Ошибка: {str(e)}"
        )
    
    return state


def planner_node(state: AgentState) -> AgentState:
    """Узел для создания плана выполнения задачи.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с plan
    """
    _initialize_agents(state)
    
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, пропускаем планирование")
        state["plan"] = ""
        return state
    
    if intent_result.type == "greeting":
        state["plan"] = ""
        return state
    
    logger.info("📝 Создаю план...")
    
    try:
        if _planner_agent:
            plan = _planner_agent.create_plan(
                task=task,
                intent_type=intent_result.type
            )
            state["plan"] = plan
            logger.info(f"✅ План создан (размер: {len(plan)} символов)")
        else:
            state["plan"] = ""
            logger.warning("⚠️ Planner Agent не инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка создания плана: {e}", error=e)
        state["plan"] = ""
    
    return state


def researcher_node(state: AgentState) -> AgentState:
    """Узел для сбора контекста (RAG + веб-поиск).
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с context
    """
    _initialize_agents(state)
    
    task = state.get("task", "")
    intent_result = state.get("intent_result")
    disable_web_search = state.get("disable_web_search", False)
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, пропускаем исследование")
        state["context"] = ""
        return state
    
    if intent_result.type == "greeting":
        state["context"] = ""
        return state
    
    logger.info("🔍 Собираю контекст...")
    
    try:
        # Проверяем есть ли файл для modify/debug режима
        file_path = extract_file_path_from_task(task)
        file_context = None
        
        if file_path and intent_result.type in ['modify', 'debug']:
            file_content = read_file_context(file_path)
            if file_content:
                file_context = prepare_modify_context(task, file_content)
                state["file_path"] = file_path
                state["file_context"] = file_context
                logger.info(f"📄 Найден файл для модификации: {file_path}")
        
        # Собираем контекст через Researcher
        if _researcher_agent:
            context = _researcher_agent.research(
                query=task,
                intent_type=intent_result.type,
                disable_web_search=disable_web_search
            )
            
            # Добавляем контекст файла в начало если есть
            if file_context:
                context = file_context + "\n\n---\n\n" + context if context else file_context
            
            state["context"] = context
            logger.info(f"✅ Контекст собран (размер: {len(context)} символов)")
        else:
            state["context"] = file_context or ""
            logger.warning("⚠️ Researcher Agent не инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка сбора контекста: {e}", error=e)
        state["context"] = state.get("file_context", "")
    
    return state


def generator_node(state: AgentState) -> AgentState:
    """Узел для генерации тестов (test generator node).
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с tests
    """
    _initialize_agents(state)
    
    plan = state.get("plan", "")
    context = state.get("context", "")
    intent_result = state.get("intent_result")
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, пропускаем генерацию тестов")
        state["tests"] = ""
        return state
    
    if intent_result.type == "greeting":
        state["tests"] = ""
        return state
    
    logger.info("🧪 Генерирую тесты...")
    
    try:
        if _test_generator:
            tests = _test_generator.generate_tests(
                plan=plan,
                context=context,
                intent_type=intent_result.type
            )
            state["tests"] = tests
            if tests:
                logger.info(f"✅ Тесты сгенерированы (размер: {len(tests)} символов)")
            else:
                logger.warning("⚠️ Не удалось сгенерировать тесты")
        else:
            state["tests"] = ""
            logger.warning("⚠️ TestGenerator Agent не инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации тестов: {e}", error=e)
        state["tests"] = ""
    
    return state


def coder_node(state: AgentState) -> AgentState:
    """Узел для генерации кода.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с code
    """
    _initialize_agents(state)
    
    plan = state.get("plan", "")
    tests = state.get("tests", "")
    context = state.get("context", "")
    intent_result = state.get("intent_result")
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, пропускаем генерацию кода")
        state["code"] = ""
        return state
    
    if intent_result.type == "greeting":
        state["code"] = ""
        return state
    
    logger.info("💻 Генерирую код...")
    
    try:
        if _coder_agent:
            code = _coder_agent.generate_code(
                plan=plan,
                tests=tests,
                context=context,
                intent_type=intent_result.type
            )
            state["code"] = code
            if code:
                logger.info(f"✅ Код сгенерирован (размер: {len(code)} символов)")
            else:
                logger.warning("⚠️ Не удалось сгенерировать код")
        else:
            state["code"] = ""
            logger.warning("⚠️ Coder Agent не инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации кода: {e}", error=e)
        state["code"] = ""
    
    return state


def validator_node(state: AgentState) -> AgentState:
    """Узел для валидации кода.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с validation_results
    """
    code = state.get("code", "")
    tests = state.get("tests", "")
    
    logger.info("🔍 Валидирую код...")
    
    try:
        validation_results = validate_code(code_str=code, test_str=tests if tests else None)
        state["validation_results"] = validation_results
        
        if validation_results.get("all_passed", False):
            logger.info("✅ Валидация пройдена")
        else:
            logger.warning("⚠️ Валидация не пройдена")
    except Exception as e:
        logger.error(f"❌ Ошибка валидации: {e}", error=e)
        state["validation_results"] = {
            "pytest": {"success": False, "output": str(e)},
            "mypy": {"success": False, "errors": str(e)},
            "bandit": {"success": False, "issues": str(e)},
            "all_passed": False
        }
    
    return state


def debugger_node(state: AgentState) -> AgentState:
    """Узел для анализа ошибок через Debugger Agent.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с debug_result
    """
    _initialize_agents(state)
    
    validation_results = state.get("validation_results", {})
    code = state.get("code", "")
    tests = state.get("tests", "")
    task = state.get("task", "")
    
    logger.info("🐛 Анализирую ошибки...")
    
    try:
        if _debugger_agent:
            debug_result = _debugger_agent.analyze_errors(
                validation_results=validation_results,
                code=code,
                tests=tests,
                task=task
            )
            state["debug_result"] = debug_result
            logger.info(f"✅ Анализ завершён. Тип ошибки: {debug_result.error_type}")
        else:
            logger.warning("⚠️ Debugger Agent не инициализирован")
            state["debug_result"] = None
    except Exception as e:
        logger.error(f"❌ Ошибка анализа ошибок: {e}", error=e)
        state["debug_result"] = None
    
    return state


def fixer_node(state: AgentState) -> AgentState:
    """Узел для исправления кода по инструкциям от Debugger.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с исправленным code и увеличенным iteration
    """
    _initialize_agents(state)
    
    code = state.get("code", "")
    debug_result = state.get("debug_result")
    tests = state.get("tests", "")
    validation_results = state.get("validation_results", {})
    
    # Увеличиваем счетчик итераций
    current_iteration = state.get("iteration", 0)
    state["iteration"] = current_iteration + 1
    
    logger.info(f"🔧 Исправляю код (итерация {state['iteration']})...")
    
    if not debug_result or not debug_result.fix_instructions:
        logger.warning("⚠️ Нет инструкций для исправления")
        return state
    
    try:
        if _coder_agent:
            fixed_code = _coder_agent.fix_code(
                code=code,
                instructions=debug_result.fix_instructions,
                tests=tests,
                validation_results=validation_results
            )
            if fixed_code:
                state["code"] = fixed_code
                logger.info(f"✅ Код исправлен (размер: {len(fixed_code)} символов)")
            else:
                logger.warning("⚠️ Не удалось исправить код")
        else:
            logger.warning("⚠️ Coder Agent не инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка исправления кода: {e}", error=e)
    
    return state


def reflection_node(state: AgentState) -> AgentState:
    """Узел для рефлексии и оценки результатов.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с reflection_result
    """
    _initialize_agents(state)
    
    task = state.get("task", "")
    plan = state.get("plan", "")
    context = state.get("context", "")
    tests = state.get("tests", "")
    code = state.get("code", "")
    validation_results = state.get("validation_results", {})
    intent_result = state.get("intent_result")
    
    logger.info("🔍 Анализирую результаты...")
    
    try:
        if _reflection_agent and intent_result:
            reflection_result = _reflection_agent.reflect(
                task=task,
                plan=plan,
                context=context,
                tests=tests,
                code=code,
                validation_results=validation_results
            )
            state["reflection_result"] = reflection_result
            
            # Сохраняем опыт в память
            if _memory_agent:
                _memory_agent.save_task_experience(
                    task=task,
                    intent_type=intent_result.type,
                    reflection_result=reflection_result,
                    key_decisions=plan[:500] if plan else "",
                    what_worked=reflection_result.analysis
                )
            
            logger.info(f"✅ Рефлексия завершена. Общая оценка: {reflection_result.overall_score:.2f}")
        else:
            logger.warning("⚠️ Reflection Agent не инициализирован или отсутствует intent_result")
            state["reflection_result"] = None
    except Exception as e:
        logger.error(f"❌ Ошибка рефлексии: {e}", error=e)
        state["reflection_result"] = None
    
    return state


def critic_node(state: AgentState) -> AgentState:
    """Узел для критического анализа сгенерированного кода.
    
    Args:
        state: Текущий state
        
    Returns:
        Обновленный state с critic_report
    """
    _initialize_agents(state)
    
    code = state.get("code", "")
    tests = state.get("tests", "")
    task = state.get("task", "")
    validation_results = state.get("validation_results", {})
    
    logger.info("🔎 Критический анализ кода...")
    
    try:
        if _critic_agent and code:
            critic_report = _critic_agent.analyze(
                code=code,
                tests=tests,
                task_description=task,
                validation_results=validation_results
            )
            state["critic_report"] = critic_report
            logger.info(f"✅ Критический анализ завершён. Оценка: {critic_report.overall_score:.2f}")
        else:
            logger.warning("⚠️ Critic Agent не инициализирован или код пустой")
            state["critic_report"] = None
    except Exception as e:
        logger.error(f"❌ Ошибка критического анализа: {e}", error=e)
        state["critic_report"] = None
    
    return state
