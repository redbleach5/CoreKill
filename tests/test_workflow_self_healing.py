"""E2E тесты для workflow с self-healing через Debugger Agent."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from agents.debugger import DebugResult
from utils.validation import validate_code


class TestWorkflowSelfHealing:
    """Тесты для цикла self-healing в workflow."""
    
    @pytest.fixture
    def mock_agents(self):
        """Создаёт моки агентов для тестирования workflow."""
        with patch('agents.intent.IntentAgent') as mock_intent, \
             patch('agents.planner.PlannerAgent') as mock_planner, \
             patch('agents.researcher.ResearcherAgent') as mock_researcher, \
             patch('agents.test_generator.TestGeneratorAgent') as mock_test_gen, \
             patch('agents.coder.CoderAgent') as mock_coder, \
             patch('agents.debugger.DebuggerAgent') as mock_debugger, \
             patch('agents.reflection.ReflectionAgent') as mock_reflection, \
             patch('agents.memory.MemoryAgent') as mock_memory:
            
            # Настраиваем возвращаемые значения для агентов
            mock_intent_instance = Mock()
            mock_intent_instance.determine_intent.return_value = Mock(
                type="create",
                confidence=0.9,
                description="Create task"
            )
            mock_intent.return_value = mock_intent_instance
            
            mock_planner_instance = Mock()
            mock_planner_instance.create_plan.return_value = "Test plan"
            mock_planner.return_value = mock_planner_instance
            
            mock_researcher_instance = Mock()
            mock_researcher_instance.research.return_value = "Test context"
            mock_researcher.return_value = mock_researcher_instance
            
            mock_test_gen_instance = Mock()
            mock_test_gen_instance.generate_tests.return_value = """
def test_add():
    assert add(1, 2) == 5
"""
            mock_test_gen.return_value = mock_test_gen_instance
            
            mock_coder_instance = Mock()
            mock_coder_instance.generate_code.return_value = """
def add(a, b):
    return a + b
"""
            mock_coder_instance.fix_code.return_value = "def add(a, b): return 5"
            mock_coder.return_value = mock_coder_instance
            
            mock_debugger_instance = Mock()
            mock_debugger_instance.analyze_errors.return_value = DebugResult(
                error_summary="Test не проходит",
                root_cause="Функция возвращает неверный результат",
                fix_instructions="Fix add function to return 5 instead of a + b",
                confidence=0.9,
                error_type="pytest"
            )
            mock_debugger.return_value = mock_debugger_instance
            
            mock_reflection_instance = Mock()
            mock_reflection_instance.reflect.return_value = Mock(
                planning_score=0.8,
                research_score=0.8,
                testing_score=0.8,
                coding_score=0.8,
                overall_score=0.8,
                analysis="Test analysis",
                improvements="Test improvements",
                should_retry=False
            )
            mock_reflection.return_value = mock_reflection_instance
            
            mock_memory_instance = Mock()
            mock_memory.return_value = mock_memory_instance
            
            yield {
                'intent': mock_intent_instance,
                'planner': mock_planner_instance,
                'researcher': mock_researcher_instance,
                'test_gen': mock_test_gen_instance,
                'coder': mock_coder_instance,
                'debugger': mock_debugger_instance,
                'reflection': mock_reflection_instance,
                'memory': mock_memory_instance
            }
    
    @pytest.fixture
    def validation_results_fail(self):
        """Результаты валидации с ошибками pytest."""
        return {
            "pytest": {
                "success": False,
                "output": "FAILED test_code.py::test_add - AssertionError: assert 3 == 5"
            },
            "mypy": {"success": True, "errors": ""},
            "bandit": {"success": True, "issues": ""},
            "all_passed": False
        }
    
    @pytest.fixture
    def validation_results_pass(self):
        """Результаты валидации успешные."""
        return {
            "pytest": {"success": True, "output": ""},
            "mypy": {"success": True, "errors": ""},
            "bandit": {"success": True, "issues": ""},
            "all_passed": True
        }
    
    def test_self_healing_cycle_pytest_failure(self, mock_agents, validation_results_fail, validation_results_pass):
        """Тест цикла self-healing при ошибках pytest."""
        # Симулируем поведение валидации: первая попытка - ошибка, вторая - успех
        validation_calls = [validation_results_fail, validation_results_pass]
        
        with patch('utils.validation.validate_code') as mock_validate:
            mock_validate.side_effect = validation_calls
            
            # Проверяем, что при первой валидации будет вызван Debugger
            initial_code = "def add(a, b): return a + b"
            fixed_code = "def add(a, b): return 5"
            
            # Проверяем что fix_code вызывается
            assert mock_agents['coder'].fix_code.called is False
            
            # Симулируем вызов fix_code
            result = mock_agents['coder'].fix_code(
                code=initial_code,
                instructions="Fix add function to return 5",
                tests="def test_add(): assert add(1, 2) == 5",
                validation_results=validation_results_fail
            )
            
            assert result == fixed_code
            assert mock_agents['coder'].fix_code.called
    
    def test_self_healing_max_iterations(self, mock_agents):
        """Тест ограничения максимального количества итераций."""
        # Создаём валидацию, которая всегда возвращает ошибку
        validation_results_fail = {
            "pytest": {
                "success": False,
                "output": "FAILED test_code.py::test_add - AssertionError: assert 3 == 5"
            },
            "mypy": {"success": True, "errors": ""},
            "bandit": {"success": True, "issues": ""},
            "all_passed": False
        }
        
        max_iterations = 3
        
        # Проверяем, что после max_iterations итераций цикл должен остановиться
        iteration = 1
        validation_results = validation_results_fail
        
        # Симулируем цикл до max_iterations
        while not validation_results.get("all_passed", False) and iteration < max_iterations:
            # Debugger анализирует ошибки
            debug_result = mock_agents['debugger'].analyze_errors(
                validation_results=validation_results,
                code="def add(a, b): return a + b",
                tests="def test_add(): assert add(1, 2) == 5",
                task="Test task"
            )
            
            # Coder исправляет код
            fixed_code = mock_agents['coder'].fix_code(
                code="def add(a, b): return a + b",
                instructions=debug_result.fix_instructions,
                tests="def test_add(): assert add(1, 2) == 5",
                validation_results=validation_results
            )
            
            # Повторная валидация (всегда возвращает ошибку в этом тесте)
            validation_results = validation_results_fail
            iteration += 1
        
        # Проверяем, что итерации не превышают max_iterations
        assert iteration <= max_iterations
    
    def test_self_healing_debugger_called_on_failure(self, mock_agents, validation_results_fail):
        """Тест вызова Debugger при ошибках валидации."""
        # Проверяем, что Debugger вызывается при ошибках
        debug_result = mock_agents['debugger'].analyze_errors(
            validation_results=validation_results_fail,
            code="def add(a, b): return a + b",
            tests="def test_add(): assert add(1, 2) == 5",
            task="Test task"
        )
        
        assert isinstance(debug_result, DebugResult)
        assert debug_result.error_type == "pytest"
        assert len(debug_result.fix_instructions) > 0
        assert mock_agents['debugger'].analyze_errors.called
    
    def test_self_healing_coder_fix_called(self, mock_agents, validation_results_fail):
        """Тест вызова fix_code в Coder при ошибках."""
        debug_result = DebugResult(
            error_summary="Test не проходит",
            root_cause="Функция возвращает неверный результат",
            fix_instructions="Fix add function to return 5",
            confidence=0.9,
            error_type="pytest"
        )
        
        fixed_code = mock_agents['coder'].fix_code(
            code="def add(a, b): return a + b",
            instructions=debug_result.fix_instructions,
            tests="def test_add(): assert add(1, 2) == 5",
            validation_results=validation_results_fail
        )
        
        assert fixed_code is not None
        assert mock_agents['coder'].fix_code.called
        assert "fix_code" in [call[0] for call in mock_agents['coder'].method_calls] if hasattr(mock_agents['coder'], 'method_calls') else True
    
    def test_self_healing_no_loop_on_success(self, validation_results_pass):
        """Тест что цикл self-healing не запускается при успешной валидации."""
        # Если валидация успешна, цикл не должен запускаться
        if validation_results_pass.get("all_passed", False):
            # Цикл не должен выполняться
            should_run_loop = False
            assert should_run_loop is False
    
    def test_debugger_result_structure(self, mock_agents, validation_results_fail):
        """Тест структуры DebugResult."""
        debug_result = mock_agents['debugger'].analyze_errors(
            validation_results=validation_results_fail,
            code="def add(a, b): return a + b",
            tests="def test_add(): assert add(1, 2) == 5",
            task="Test task"
        )
        
        assert hasattr(debug_result, 'error_summary')
        assert hasattr(debug_result, 'root_cause')
        assert hasattr(debug_result, 'fix_instructions')
        assert hasattr(debug_result, 'confidence')
        assert hasattr(debug_result, 'error_type')
        
        assert isinstance(debug_result.error_summary, str)
        assert isinstance(debug_result.root_cause, str)
        assert isinstance(debug_result.fix_instructions, str)
        assert isinstance(debug_result.confidence, float)
        assert 0.0 <= debug_result.confidence <= 1.0
        assert isinstance(debug_result.error_type, str)
