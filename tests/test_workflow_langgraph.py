"""Тесты для LangGraph workflow."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from infrastructure.workflow_graph import create_workflow_graph
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
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult


class TestWorkflowGraph:
    """Тесты для графа LangGraph."""
    
    def test_create_workflow_graph(self):
        """Тест создания графа."""
        graph = create_workflow_graph()
        assert graph is not None
        # Проверяем что граф скомпилирован (имеет метод invoke)
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "astream")
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('agents.intent.IntentAgent.is_greeting_fast')
    def test_intent_node_greeting(self, mock_greeting, mock_init):
        """Тест узла intent для greeting."""
        mock_greeting.return_value = True
        
        state: AgentState = {
            "task": "привет",
            "max_iterations": 1,
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
            "file_context": None
        }
        
        result = intent_node(state)
        
        assert result["intent_result"] is not None
        assert result["intent_result"].type == "greeting"
        assert result["intent_result"].confidence == 0.95
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._intent_agent')
    def test_intent_node_create(self, mock_agent, mock_init):
        """Тест узла intent для create."""
        mock_result = IntentResult(
            type="create",
            confidence=0.9,
            description="Создание нового кода"
        )
        mock_agent.determine_intent.return_value = mock_result
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
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
            "file_context": None
        }
        
        result = intent_node(state)
        
        assert result["intent_result"] is not None
        assert result["intent_result"].type == "create"
    
    def test_should_skip_greeting(self):
        """Тест условной функции should_skip_greeting."""
        # Тест с greeting
        state_greeting: AgentState = {
            "task": "привет",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="greeting",
                confidence=0.95,
                description="Приветствие"
            ),
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
            "file_context": None
        }
        
        result = should_skip_greeting(state_greeting)
        assert result == "skip"
        
        # Тест без greeting
        state_create: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
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
            "file_context": None
        }
        
        result = should_skip_greeting(state_create)
        assert result == "continue"
    
    def test_should_continue_self_healing(self):
        """Тест условной функции should_continue_self_healing."""
        # Тест с проваленной валидацией и итерациями в запасе
        state_continue: AgentState = {
            "task": "создать функцию",
            "max_iterations": 3,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "",
            "context": "",
            "tests": "",
            "code": "",
            "validation_results": {
                "all_passed": False
            },
            "debug_result": None,
            "reflection_result": None,
            "iteration": 1,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = should_continue_self_healing(state_continue)
        assert result == "continue"
        
        # Тест с пройденной валидацией
        state_finish_passed: AgentState = {
            **state_continue,
            "validation_results": {
                "all_passed": True
            }
        }
        
        result = should_continue_self_healing(state_finish_passed)
        assert result == "finish"
        
        # Тест с достигнутым лимитом итераций
        state_finish_limit: AgentState = {
            **state_continue,
            "iteration": 3,
            "max_iterations": 3
        }
        
        result = should_continue_self_healing(state_finish_limit)
        assert result == "finish"
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._planner_agent')
    def test_planner_node(self, mock_agent, mock_init):
        """Тест узла planner."""
        mock_agent.create_plan.return_value = "План выполнения задачи"
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
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
            "file_context": None
        }
        
        result = planner_node(state)
        
        assert result["plan"] == "План выполнения задачи"
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._researcher_agent')
    def test_researcher_node(self, mock_agent, mock_init):
        """Тест узла researcher."""
        mock_agent.research.return_value = "Контекст из RAG"
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
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
            "file_context": None
        }
        
        result = researcher_node(state)
        
        assert result["context"] == "Контекст из RAG"
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._test_generator')
    def test_test_generator_node(self, mock_agent, mock_init):
        """Тест узла test_generator."""
        mock_agent.generate_tests.return_value = "def test_function(): pass"
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "",
            "code": "",
            "validation_results": {},
            "debug_result": None,
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = test_generator_node(state)
        
        assert result["tests"] == "def test_function(): pass"
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._coder_agent')
    def test_coder_node(self, mock_agent, mock_init):
        """Тест узла coder."""
        mock_agent.generate_code.return_value = "def function(): pass"
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "def test_function(): pass",
            "code": "",
            "validation_results": {},
            "debug_result": None,
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = coder_node(state)
        
        assert result["code"] == "def function(): pass"
    
    @patch('utils.validation.validate_code')
    def test_validator_node(self, mock_validate):
        """Тест узла validator."""
        mock_validate.return_value = {
            "pytest": {"success": True, "output": ""},
            "mypy": {"success": True, "errors": ""},
            "bandit": {"success": True, "issues": ""},
            "all_passed": True
        }
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "def test_function(): pass",
            "code": "def function(): pass",
            "validation_results": {},
            "debug_result": None,
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = validator_node(state)
        
        assert result["validation_results"]["all_passed"] is True
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._debugger_agent')
    def test_debugger_node(self, mock_agent, mock_init):
        """Тест узла debugger."""
        mock_result = DebugResult(
            error_summary="Ошибка в коде",
            root_cause="Синтаксическая ошибка",
            fix_instructions="Исправить синтаксис",
            confidence=0.8,
            error_type="syntax"
        )
        mock_agent.analyze_errors.return_value = mock_result
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "def test_function(): pass",
            "code": "def function(): pass",
            "validation_results": {
                "all_passed": False
            },
            "debug_result": None,
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = debugger_node(state)
        
        assert result["debug_result"] is not None
        assert result["debug_result"].error_type == "syntax"
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._coder_agent')
    def test_fixer_node(self, mock_agent, mock_init):
        """Тест узла fixer."""
        mock_agent.fix_code.return_value = "def function_fixed(): pass"
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 3,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "def test_function(): pass",
            "code": "def function(): pass",
            "validation_results": {
                "all_passed": False
            },
            "debug_result": DebugResult(
                error_summary="Ошибка",
                root_cause="Причина",
                fix_instructions="Исправить",
                confidence=0.8,
                error_type="syntax"
            ),
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = fixer_node(state)
        
        assert result["code"] == "def function_fixed(): pass"
        assert result["iteration"] == 1  # Итерация должна увеличиться
    
    @patch('infrastructure.workflow_nodes._initialize_agents')
    @patch('infrastructure.workflow_nodes._reflection_agent')
    @patch('infrastructure.workflow_nodes._memory_agent')
    def test_reflection_node(self, mock_memory, mock_agent, mock_init):
        """Тест узла reflection."""
        mock_result = ReflectionResult(
            planning_score=0.8,
            research_score=0.7,
            testing_score=0.9,
            coding_score=0.85,
            overall_score=0.81,
            analysis="Хороший результат",
            improvements="Можно улучшить",
            should_retry=False
        )
        mock_agent.reflect.return_value = mock_result
        
        state: AgentState = {
            "task": "создать функцию",
            "max_iterations": 1,
            "disable_web_search": False,
            "model": None,
            "temperature": 0.25,
            "intent_result": IntentResult(
                type="create",
                confidence=0.9,
                description="Создание"
            ),
            "plan": "План",
            "context": "Контекст",
            "tests": "def test_function(): pass",
            "code": "def function(): pass",
            "validation_results": {
                "all_passed": True
            },
            "debug_result": None,
            "reflection_result": None,
            "iteration": 0,
            "task_id": "test-123",
            "enable_sse": False,
            "file_path": None,
            "file_context": None
        }
        
        result = reflection_node(state)
        
        assert result["reflection_result"] is not None
        assert result["reflection_result"].overall_score == 0.81
        # Проверяем что память была вызвана
        mock_memory.save_task_experience.assert_called_once()
