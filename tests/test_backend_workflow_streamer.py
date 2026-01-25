"""Тесты для workflow streamer."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from backend.workflow_streamer import WorkflowStreamer
from infrastructure.workflow_state import AgentState
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult
from agents.critic import CriticReport


@pytest.fixture
def mock_sse_queue():
    """Мок SSE очереди."""
    return asyncio.Queue()


@pytest.fixture
def initial_state():
    """Начальное состояние workflow."""
    return {
        "task": "напиши функцию hello",
        "task_id": "test-task-123"
    }


@pytest.fixture
def workflow_streamer(mock_sse_queue, initial_state):
    """Создает экземпляр WorkflowStreamer."""
    return WorkflowStreamer(
        task="напиши функцию hello",
        task_id="test-task-123",
        sse_queue=mock_sse_queue,
        initial_state=initial_state
    )


class TestWorkflowStreamerInit:
    """Тесты инициализации WorkflowStreamer."""
    
    @pytest.mark.backend

    
    def test_init_sets_attributes(self, workflow_streamer, mock_sse_queue, initial_state):
        """Тест что инициализация устанавливает атрибуты."""
        assert workflow_streamer.task == "напиши функцию hello"
        assert workflow_streamer.task_id == "test-task-123"
        assert workflow_streamer.sse_queue == mock_sse_queue
        assert workflow_streamer.initial_state == initial_state
    
    @pytest.mark.backend

    
    def test_init_has_node_to_stage_mapping(self, workflow_streamer):
        """Тест что есть маппинг node -> stage."""
        assert "intent" in workflow_streamer.node_to_stage
        assert "planner" in workflow_streamer.node_to_stage
        assert "coder" in workflow_streamer.node_to_stage
    
    @pytest.mark.backend

    
    def test_init_has_stage_messages(self, workflow_streamer):
        """Тест что есть сообщения для этапов."""
        assert "intent" in workflow_streamer.stage_messages
        assert "planning" in workflow_streamer.stage_messages
        assert "coding" in workflow_streamer.stage_messages


class TestHandleNode:
    """Тесты для handle_node."""
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_intent_node(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки intent нода."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        node_state = {
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание кода"
            )
        }
        
        events = []
        async for event in workflow_streamer.handle_node("intent", node_state):
            events.append(event)
        
        assert len(events) > 0
        mock_start.assert_called()
        mock_end.assert_called()
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_planner_node(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки planner нода."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        node_state = {
            "plan": "1. Создать функцию\n2. Добавить тесты"
        }
        
        events = []
        async for event in workflow_streamer.handle_node("planner", node_state):
            events.append(event)
        
        assert len(events) > 0
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_coder_node(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки coder нода."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        node_state = {
            "code": "def hello():\n    return 'world'"
        }
        
        events = []
        async for event in workflow_streamer.handle_node("coder", node_state):
            events.append(event)
        
        assert len(events) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_handle_unknown_node(self, workflow_streamer):
        """Тест обработки неизвестного нода."""
        node_state = {}
        
        events = []
        async for event in workflow_streamer.handle_node("unknown_node", node_state):
            events.append(event)
        
        # Неизвестный нод не должен генерировать события
        assert len(events) == 0


class TestNodeHandlers:
    """Тесты для обработчиков нодов."""
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_intent_with_greeting(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки intent с greeting."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        node_state = {
            "intent_result": IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие"
            )
        }
        
        events = []
        async for event in workflow_streamer._handle_intent(
            node_state,
            greeting_message="Привет!",
            help_message="Помощь"
        ):
            events.append(event)
        
        assert len(events) > 0
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_debugger_node(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки debugger нода."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        # Используем правильные параметры для DebugResult
        node_state = {
            "debug_result": DebugResult(
                error_summary="Синтаксическая ошибка",
                root_cause="Неверный синтаксис",
                fix_instructions="Fix syntax error",
                confidence=0.9,
                error_type="syntax"
            )
        }
        
        events = []
        async for event in workflow_streamer._handle_debugger(node_state):
            events.append(event)
        
        assert len(events) > 0
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager.stream_stage_start')
    @patch('backend.workflow_streamer.SSEManager.stream_stage_end')
    @pytest.mark.backend

    async def test_handle_reflection_node(
        self,
        mock_end,
        mock_start,
        workflow_streamer
    ):
        """Тест обработки reflection нода."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        
        # Используем правильные параметры для ReflectionResult
        from tests.factories import create_reflection_result
        node_state = {
            "reflection_result": create_reflection_result()
        }
        
        events = []
        async for event in workflow_streamer._handle_reflection(node_state):
            events.append(event)
        
        assert len(events) > 0
