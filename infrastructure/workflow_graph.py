"""Граф LangGraph для workflow агентов."""
from typing import Any
from langgraph.graph import StateGraph, START, END
from infrastructure.workflow_state import AgentState
from infrastructure.workflow_nodes import (
    intent_node,
    planner_node,
    researcher_node,
    generator_node,
    coder_node,
    validator_node,
    debugger_node,
    fixer_node,
    reflection_node,
    critic_node,
    _is_streaming_enabled,
    _get_streaming_node_adapter,
    stream_planner_node,
    stream_generator_node,
    stream_coder_node,
    stream_debugger_node,
    stream_fixer_node,
    stream_reflection_node,
    stream_critic_node
)
from infrastructure.workflow_edges import (
    should_skip_greeting,
    should_continue_self_healing
)
from utils.logger import get_logger


logger = get_logger()


def create_workflow_graph() -> Any:
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
    reflection_node → critic_node
    critic_node → END
    
    Если включён use_streaming_agents в config.toml, используются стриминговые узлы
    через адаптеры, которые собирают SSE события в state.
    
    Returns:
        Скомпилированный граф LangGraph
    """
    # Проверяем, включён ли стриминг
    use_streaming = _is_streaming_enabled()
    
    if use_streaming:
        logger.info("🧠 Используются стриминговые узлы в графе LangGraph")
    
    # Создаём граф
    workflow = StateGraph(AgentState)
    
    # Выбираем узлы в зависимости от флага стриминга
    # Intent и researcher всегда обычные (не имеют стриминговых версий)
    workflow.add_node("intent", intent_node)  # type: ignore[call-overload]
    workflow.add_node("researcher", researcher_node)  # type: ignore[call-overload]
    
    # Planner
    if use_streaming:
        planner_adapter = _get_streaming_node_adapter(stream_planner_node, "planning", "plan", "")
        workflow.add_node("planner", planner_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("planner", planner_node)  # type: ignore[call-overload]
    
    # Test Generator
    if use_streaming:
        generator_adapter = _get_streaming_node_adapter(stream_generator_node, "testing", "tests", "")
        workflow.add_node("test_generator", generator_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("test_generator", generator_node)  # type: ignore[call-overload]
    
    # Coder
    if use_streaming:
        coder_adapter = _get_streaming_node_adapter(stream_coder_node, "coding", "code", "")
        workflow.add_node("coder", coder_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("coder", coder_node)  # type: ignore[call-overload]
    
    # Validator всегда обычный
    workflow.add_node("validator", validator_node)  # type: ignore[call-overload]
    
    # Debugger
    if use_streaming:
        debugger_adapter = _get_streaming_node_adapter(stream_debugger_node, "debug", "debug_result", None)
        workflow.add_node("debugger", debugger_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("debugger", debugger_node)  # type: ignore[call-overload]
    
    # Fixer
    if use_streaming:
        fixer_adapter = _get_streaming_node_adapter(stream_fixer_node, "fixing", "code", "")
        workflow.add_node("fixer", fixer_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("fixer", fixer_node)  # type: ignore[call-overload]
    
    # Reflection
    if use_streaming:
        reflection_adapter = _get_streaming_node_adapter(stream_reflection_node, "reflection", "reflection_result", None)
        workflow.add_node("reflection", reflection_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("reflection", reflection_node)  # type: ignore[call-overload]
    
    # Critic
    if use_streaming:
        critic_adapter = _get_streaming_node_adapter(stream_critic_node, "critic", "critic_report", None)
        workflow.add_node("critic", critic_adapter)  # type: ignore[call-overload]
    else:
        workflow.add_node("critic", critic_node)  # type: ignore[call-overload]
    
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
    
    # reflection → critic → END
    workflow.add_edge("reflection", "critic")
    workflow.add_edge("critic", END)
    
    # Компилируем граф
    graph = workflow.compile()
    
    logger.info("✅ LangGraph workflow скомпилирован")
    
    return graph
