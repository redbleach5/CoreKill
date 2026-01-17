"""Граф LangGraph для workflow агентов."""
from langgraph.graph import StateGraph, START, END
from infrastructure.workflow_state import AgentState
from infrastructure.workflow_nodes import (
    intent_node,
    planner_node,
    researcher_node,
    test_generator_node,
    coder_node,
    validator_node,
    debugger_node,
    fixer_node,
    reflection_node
)
from infrastructure.workflow_edges import (
    should_skip_greeting,
    should_continue_self_healing
)
from utils.logger import get_logger


logger = get_logger()


def create_workflow_graph() -> StateGraph:
    """Создаёт и компилирует граф LangGraph для workflow агентов.
    
    Структура графа:
    START → intent_node
    intent_node → should_skip_greeting
    should_skip_greeting → [skip: END, continue: planner_node]
    planner_node → researcher_node
    researcher_node → test_generator_node
    test_generator_node → coder_node
    coder_node → validator_node
    validator_node → should_continue_self_healing
    should_continue_self_healing → [continue: debugger_node, finish: reflection_node]
    debugger_node → fixer_node
    fixer_node → validator_node (цикл)
    reflection_node → END
    
    Returns:
        Скомпилированный граф LangGraph
    """
    # Создаём граф
    workflow = StateGraph(AgentState)
    
    # Добавляем узлы
    workflow.add_node("intent", intent_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("test_generator", test_generator_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("debugger", debugger_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("reflection", reflection_node)
    
    # Добавляем рёбра (переходы)
    # START → intent
    workflow.add_edge(START, "intent")
    
    # intent → should_skip_greeting (условный переход)
    workflow.add_conditional_edges(
        "intent",
        should_skip_greeting,
        {
            "skip": END,  # Если greeting, завершаем
            "continue": "planner"  # Иначе продолжаем
        }
    )
    
    # Линейная цепочка: planner → researcher → test_generator → coder → validator
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "test_generator")
    workflow.add_edge("test_generator", "coder")
    workflow.add_edge("coder", "validator")
    
    # validator → should_continue_self_healing (условный переход)
    workflow.add_conditional_edges(
        "validator",
        should_continue_self_healing,
        {
            "continue": "debugger",  # Если нужно исправить, идём в debugger
            "finish": "reflection"  # Иначе завершаем с рефлексией
        }
    )
    
    # Цикл self-healing: debugger → fixer → validator (обратно)
    workflow.add_edge("debugger", "fixer")
    workflow.add_edge("fixer", "validator")  # Возвращаемся к валидации
    
    # reflection → END
    workflow.add_edge("reflection", END)
    
    # Компилируем граф
    graph = workflow.compile()
    
    logger.info("✅ LangGraph workflow скомпилирован")
    
    return graph
