"""Тесты для WorkflowStreamer."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from backend.workflow_streamer import WorkflowStreamer
from infrastructure.workflow_state import AgentState
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult
from agents.critic import CriticReport
import asyncio


@pytest.fixture
def mock_sse_queue():
    """Создаёт мок очереди SSE."""
    return asyncio.Queue()


@pytest.fixture
def sample_state() -> AgentState:
    """Создаёт примерное состояние для тестов."""
    return {
        "task": "test task",
        "max_iterations": 3,
        "disable_web_search": False,
        "model": "test-model",
        "temperature": 0.25,
        "interaction_mode": "code",
        "conversation_id": None,
        "conversation_history": None,
        "chat_response": None,
        "project_path": None,
        "file_extensions": None,
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
        "critic_report": None,
        "iteration": 0,
        "task_id": "test-task-id",
        "enable_sse": True,
        "event_references": None,
        "file_path": None,
        "file_context": None
    }


@pytest.fixture
def streamer(mock_sse_queue, sample_state):
    """Создаёт экземпляр WorkflowStreamer для тестов."""
    return WorkflowStreamer(
        task="test task",
        task_id="test-task-id",
        sse_queue=mock_sse_queue,
        initial_state=sample_state
    )


class TestWorkflowStreamerInit:
    """Тесты инициализации WorkflowStreamer."""
    
    def test_init(self, mock_sse_queue, sample_state):
        """Тест инициализации."""
        streamer = WorkflowStreamer(
            task="test",
            task_id="test-id",
            sse_queue=mock_sse_queue,
            initial_state=sample_state
        )
        
        assert streamer.task == "test"
        assert streamer.task_id == "test-id"
        assert streamer.sse_queue == mock_sse_queue
        assert streamer.initial_state == sample_state


class TestWorkflowStreamerHandlers:
    """Тесты обработчиков нодов."""
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager')
    async def test_handle_planner(self, mock_sse_manager, streamer, sample_state):
        """Тест обработки planner нода."""
        sample_state["plan"] = "Test plan"
        
        mock_sse_manager.stream_stage_start = AsyncMock(return_value="start_event")
        mock_sse_manager.stream_stage_end = AsyncMock(return_value="end_event")
        
        events = []
        async for event in streamer._handle_planner(sample_state):
            events.append(event)
        
        # _handle_planner возвращает только stage_end если есть plan
        # stage_start отправляется в workflow_handler
        assert len(events) >= 1
        mock_sse_manager.stream_stage_end.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager')
    async def test_handle_researcher(self, mock_sse_manager, streamer, sample_state):
        """Тест обработки researcher нода."""
        sample_state["context"] = "Test context"
        
        mock_sse_manager.stream_stage_start = AsyncMock(return_value="start_event")
        mock_sse_manager.stream_stage_end = AsyncMock(return_value="end_event")
        
        events = []
        async for event in streamer._handle_researcher(sample_state):
            events.append(event)
        
        assert len(events) == 2
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager')
    async def test_handle_intent_greeting(self, mock_sse_manager, streamer, sample_state):
        """Тест обработки intent нода с greeting."""
        intent_result = IntentResult(
            type="greeting",
            confidence=0.95,
            description="Test greeting"
        )
        sample_state["intent_result"] = intent_result
        
        mock_sse_manager.stream_stage_start = AsyncMock(return_value="start_event")
        mock_sse_manager.stream_stage_end = AsyncMock(return_value="end_event")
        mock_sse_manager.stream_final_result = AsyncMock(return_value="final_event")
        
        events = []
        async for event in streamer._handle_intent(
            sample_state,
            greeting_message="Test greeting",
            help_message="Test help"
        ):
            events.append(event)
        
        # Должны быть: start, end, greeting_end, final_result, STOP_WORKFLOW
        assert len(events) >= 4
        assert events[-1] == "__STOP_WORKFLOW__"
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager')
    async def test_handle_coder(self, mock_sse_manager, streamer, sample_state):
        """Тест обработки coder нода."""
        sample_state["code"] = "def test(): pass"
        
        mock_sse_manager.stream_stage_start = AsyncMock(return_value="start_event")
        mock_sse_manager.stream_code_chunk = AsyncMock(return_value="chunk_event")
        mock_sse_manager.stream_stage_end = AsyncMock(return_value="end_event")
        
        events = []
        async for event in streamer._handle_coder(sample_state):
            events.append(event)
        
        assert len(events) == 3
        mock_sse_manager.stream_code_chunk.assert_called_once()


class TestWorkflowStreamerNodeHandler:
    """Тесты универсального обработчика нодов."""
    
    @pytest.mark.asyncio
    @patch('backend.workflow_streamer.SSEManager')
    async def test_handle_node(self, mock_sse_manager, streamer, sample_state):
        """Тест handle_node для существующего нода."""
        sample_state["plan"] = "Test plan"
        
        mock_sse_manager.stream_stage_start = AsyncMock(return_value="start_event")
        mock_sse_manager.stream_stage_end = AsyncMock(return_value="end_event")
        
        events = []
        async for event in streamer.handle_node("planner", sample_state):
            events.append(event)
        
        # handle_node возвращает только stage_end если есть plan
        assert len(events) >= 1
    
    @pytest.mark.asyncio
    async def test_handle_node_unknown(self, streamer, sample_state):
        """Тест handle_node для неизвестного нода."""
        events = []
        async for event in streamer.handle_node("unknown_node", sample_state):
            events.append(event)
        
        # Неизвестный нод не должен генерировать события
        assert len(events) == 0
