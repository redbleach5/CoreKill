"""Условные функции (edges) для LangGraph workflow."""
from infrastructure.workflow_state import AgentState
from utils.logger import get_logger


logger = get_logger()


def should_skip_greeting(state: AgentState) -> str:
    """Проверяет нужно ли пропустить workflow для greeting.
    
    Args:
        state: Текущий state
        
    Returns:
        "skip" если это greeting, "continue" иначе
    """
    intent_result = state.get("intent_result")
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, продолжаем workflow")
        return "continue"
    
    if intent_result.type == "greeting":
        logger.info("ℹ️ Обнаружено приветствие, пропускаем основной workflow")
        return "skip"
    
    return "continue"


def should_continue_self_healing(state: AgentState) -> str:
    """Проверяет нужно ли продолжить цикл self-healing.
    
    Args:
        state: Текущий state
        
    Returns:
        "continue" если нужно продолжить цикл, "finish" если завершить
    """
    validation_results = state.get("validation_results", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 1)
    
    # Проверяем прошла ли валидация
    all_passed = validation_results.get("all_passed", False)
    
    if all_passed:
        logger.info("✅ Валидация пройдена, завершаем цикл self-healing")
        return "finish"
    
    # Проверяем не превышен ли лимит итераций
    if iteration >= max_iterations:
        logger.info(f"⏱️ Достигнут лимит итераций ({max_iterations}), завершаем цикл")
        return "finish"
    
    logger.info(f"🔄 Продолжаем цикл self-healing (итерация {iteration + 1}/{max_iterations})")
    return "continue"
