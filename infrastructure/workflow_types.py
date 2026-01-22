"""Типы для workflow nodes.

Определяет Protocol интерфейсы для узлов workflow,
обеспечивая единообразную типизацию.
"""
from typing import Protocol, Union, AsyncIterator, Any
from infrastructure.workflow_state import AgentState


class WorkflowNode(Protocol):
    """Протокол для обычных workflow узлов.
    
    Узел принимает AgentState и возвращает обновлённый AgentState.
    """
    
    async def __call__(self, state: AgentState) -> AgentState:
        """Выполняет узел workflow.
        
        Args:
            state: Текущее состояние workflow
            
        Returns:
            Обновлённое состояние workflow
        """
        ...


class StreamingWorkflowNode(Protocol):
    """Протокол для стриминговых workflow узлов.
    
    Узел принимает AgentState и возвращает AsyncIterator событий.
    Каждое событие - это кортеж (event_type, data).
    """
    
    async def __call__(
        self, 
        state: AgentState
    ) -> AsyncIterator[tuple[str, Any]]:
        """Выполняет стриминговый узел workflow.
        
        Args:
            state: Текущее состояние workflow
            
        Yields:
            tuple[event_type, data]: События для SSE
                - event_type: Тип события (thinking, code_chunk, done, etc.)
                - data: Данные события
        """
        ...


# Type alias для совместимости
from typing import Any
WorkflowNodeFunc = Union[WorkflowNode, StreamingWorkflowNode]
