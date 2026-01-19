"""Тесты для LangGraph workflow."""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from infrastructure.workflow_graph import create_workflow_graph
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
    reflection_node
)
from infrastructure.workflow_edges import (
    should_skip_greeting,
    should_continue_self_healing
)
from agents.intent import IntentAgent, IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult


def create_test_state(**overrides) -> AgentState:
    """Создаёт тестовый AgentState с дефолтными значениями."""
    default: AgentState = {
        "task": "test task",
        "max_iterations": 3,
        "disable_web_search": False,
        "model": None,
        "temperature": 0.25,
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
        "iteration": 0,
        "task_id": "test-123",
        "enable_sse": False,
        "file_path": None,
        "file_context": None,
        "interaction_mode": "code",
        "conversation_id": None,
        "conversation_history": None,
        "chat_response": None,
        "project_path": None,
        "file_extensions": None,
        "critic_report": None
    }
    default.update(overrides)
    return default


# Общий патч для декораторных функций (метрики и checkpoints)
DECORATOR_PATCHES = [
    'infrastructure.workflow_decorators._save_checkpoint',
    'infrastructure.workflow_decorators._record_stage_duration',
]


class TestWorkflowGraph:
    """Тесты для графа LangGraph."""
    
    def test_create_workflow_graph(self):
        """Тест создания графа."""
        graph = create_workflow_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "astream")
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._intent_agent', new_callable=Mock)
    async def test_intent_node_greeting(self, mock_agent, mock_init, mock_record, mock_save):
        """Тест узла intent для greeting."""
        with patch.object(IntentAgent, 'is_greeting_fast', return_value=True):
            state = create_test_state(task="привет")
            result = await intent_node(state)
        
        assert result["intent_result"] is not None
        assert result["intent_result"].type == "greeting"
        assert result["intent_result"].confidence == 0.95
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._intent_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_intent_node_create(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла intent для create."""
        mock_result = IntentResult(
            type="create",
            confidence=0.9,
            description="Создание нового кода"
        )
        mock_agent.determine_intent.return_value = mock_result
        
        with patch('infrastructure.workflow_nodes.IntentAgent.is_greeting_fast', return_value=False):
            state = create_test_state(task="создать функцию")
            result = await intent_node(state)
        
        assert result["intent_result"] is not None
        assert result["intent_result"].type == "create"
        assert result["intent_result"].confidence == 0.9
    
    def test_should_skip_greeting(self):
        """Тест условного перехода skip/continue для greeting."""
        greeting_state = create_test_state(
            intent_result=IntentResult(type="greeting", confidence=1.0, description="Test")
        )
        assert should_skip_greeting(greeting_state) == "skip"
        
        create_state = create_test_state(
            intent_result=IntentResult(type="create", confidence=1.0, description="Test")
        )
        assert should_skip_greeting(create_state) == "continue"
    
    def test_should_continue_self_healing(self):
        """Тест условного перехода для self-healing."""
        success_state = create_test_state(
            validation_results={"all_passed": True},
            iteration=1,
            max_iterations=3
        )
        assert should_continue_self_healing(success_state) == "finish"
        
        fail_state = create_test_state(
            validation_results={"all_passed": False},
            iteration=1,
            max_iterations=3
        )
        assert should_continue_self_healing(fail_state) == "continue"
        
        max_iter_state = create_test_state(
            validation_results={"all_passed": False},
            iteration=3,
            max_iterations=3
        )
        assert should_continue_self_healing(max_iter_state) == "finish"
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._planner_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_planner_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла planner."""
        mock_agent.create_plan.return_value = "Plan step 1\nPlan step 2"
        
        state = create_test_state(
            task="создать калькулятор",
            intent_result=IntentResult(type="create", confidence=0.9, description="Test")
        )
        
        result = await planner_node(state)
        
        assert result["plan"] == "Plan step 1\nPlan step 2"
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._researcher_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_researcher_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла researcher."""
        mock_agent.research.return_value = "Context from research"
        
        state = create_test_state(
            task="создать функцию",
            intent_result=IntentResult(type="create", confidence=0.9, description="Test")
        )
        
        result = await researcher_node(state)
        
        assert "Context" in result.get("context", "") or result["context"] == ""
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._test_generator')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_generator_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла generator (test_generator)."""
        mock_agent.generate_tests.return_value = "def test_example(): assert True"
        
        state = create_test_state(
            plan="Create a function",
            context="Some context",
            intent_result=IntentResult(type="create", confidence=0.9, description="Test")
        )
        
        result = await generator_node(state)
        
        assert "test" in result.get("tests", "").lower() or result["tests"] == ""
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._coder_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_coder_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла coder."""
        mock_agent.generate_code.return_value = "def hello(): return 'world'"
        
        state = create_test_state(
            plan="Create hello function",
            tests="def test_hello(): assert hello() == 'world'",
            context="",
            intent_result=IntentResult(type="create", confidence=0.9, description="Test")
        )
        
        result = await coder_node(state)
        
        assert "def" in result.get("code", "") or result["code"] == ""
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes.validate_code')
    async def test_validator_node(self, mock_validate, mock_record, mock_save):
        """Тест узла validator."""
        mock_validate.return_value = {
            "pytest": {"success": True, "output": "1 passed"},
            "mypy": {"success": True, "errors": ""},
            "bandit": {"success": True, "issues": ""},
            "all_passed": True
        }
        
        state = create_test_state(
            code="def hello(): return 'world'",
            tests="def test_hello(): assert hello() == 'world'"
        )
        
        result = await validator_node(state)
        
        assert result["validation_results"]["all_passed"] is True
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._debugger_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_debugger_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла debugger."""
        mock_agent.analyze_errors.return_value = DebugResult(
            error_summary="Test error",
            root_cause="Test cause",
            fix_instructions="Fix it",
            confidence=0.9,
            error_type="pytest"
        )
        
        state = create_test_state(
            code="def broken(): pass",
            tests="def test(): assert broken() == 1",
            validation_results={"all_passed": False, "pytest": {"success": False}}
        )
        
        result = await debugger_node(state)
        
        assert result["debug_result"] is not None
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._coder_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_fixer_node(self, mock_init, mock_agent, mock_record, mock_save):
        """Тест узла fixer."""
        mock_agent.fix_code.return_value = "def fixed(): return 1"
        
        state = create_test_state(
            code="def broken(): pass",
            tests="def test(): assert broken() == 1",
            debug_result=DebugResult(
                error_summary="Error",
                root_cause="Cause",
                fix_instructions="Return 1",
                confidence=0.9,
                error_type="pytest"
            ),
            iteration=0
        )
        
        result = await fixer_node(state)
        
        assert result["iteration"] == 1
    
    @pytest.mark.asyncio
    @patch('infrastructure.workflow_decorators._save_checkpoint')
    @patch('infrastructure.workflow_decorators._record_stage_duration')
    @patch('infrastructure.workflow_nodes._get_memory_agent')
    @patch('infrastructure.workflow_nodes._reflection_agent')
    @patch('infrastructure.workflow_nodes._initialize_agents')
    async def test_reflection_node(self, mock_init, mock_agent, mock_memory, mock_record, mock_save):
        """Тест узла reflection."""
        mock_agent.reflect.return_value = ReflectionResult(
            planning_score=0.8,
            research_score=0.7,
            testing_score=0.9,
            coding_score=0.85,
            overall_score=0.81,
            analysis="Good job",
            improvements="None needed",
            should_retry=False
        )
        mock_memory.return_value = Mock(save_task_experience=Mock())
        
        state = create_test_state(
            task="create function",
            plan="Plan",
            context="Context",
            tests="Tests",
            code="Code",
            validation_results={"all_passed": True},
            intent_result=IntentResult(type="create", confidence=0.9, description="Test")
        )
        
        result = await reflection_node(state)
        
        assert result["reflection_result"] is not None
        assert result["reflection_result"].overall_score == 0.81
