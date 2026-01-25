"""Условные функции (edges) для LangGraph workflow."""
from infrastructure.workflow_state import AgentState
from utils.logger import get_logger


logger = get_logger()


def should_skip_greeting(state: AgentState) -> str:
    """Проверяет нужно ли пропустить workflow для greeting/help.
    
    Args:
        state: Текущий state
        
    Returns:
        "skip" если это greeting или help, "continue" иначе
    """
    intent_result = state.get("intent_result")
    
    if not intent_result:
        logger.warning("⚠️ Intent result отсутствует, продолжаем workflow")
        return "continue"
    
    # Пропускаем полный workflow для простых запросов (приветствия и help)
    simple_intents = {"greeting", "help"}
    if intent_result.type in simple_intents:
        logger.info(f"ℹ️ Обнаружен простой запрос ({intent_result.type}), пропускаем основной workflow")
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
    code = state.get("code", "")
    
    # Проверяем прошла ли валидация
    all_passed = validation_results.get("all_passed", False)
    
    if all_passed:
        logger.info("✅ Валидация пройдена, завершаем цикл self-healing")
        return "finish"
    
    # Если код пустой и это не первая итерация, завершаем цикл
    # (пустой код обычно означает падение модели)
    if not code.strip() and iteration > 0:
        logger.warning(
            "⚠️ Код пустой после попыток исправления, возможно модель недоступна. "
            "Завершаем цикл self-healing"
        )
        return "finish"
    
    # Проверяем не превышен ли лимит итераций
    if iteration >= max_iterations:
        logger.info(f"⏱️ Достигнут лимит итераций ({max_iterations}), завершаем цикл")
        return "finish"
    
    logger.info(f"🔄 Продолжаем цикл self-healing (итерация {iteration + 1}/{max_iterations})")
    return "continue"
