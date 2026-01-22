"""Тесты для Debugger Agent."""
import pytest
from unittest.mock import Mock, patch
from agents.debugger import DebuggerAgent, DebugResult


class TestDebuggerAgent:
    """Тесты для DebuggerAgent."""
    
    @pytest.fixture
    def debugger_agent(self):
        """Создаёт экземпляр DebuggerAgent для тестирования."""
        with patch('agents.debugger.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.debugger.create_llm_for_stage') as mock_llm:
                mock_llm.return_value = Mock()
                agent = DebuggerAgent(model="test-model")
                return agent
    
    @pytest.fixture
    def validation_results_pytest_fail(self):
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
    def validation_results_mypy_fail(self):
        """Результаты валидации с ошибками mypy."""
        return {
            "pytest": {"success": True, "output": ""},
            "mypy": {
                "success": False,
                "errors": "code.py:5: error: Incompatible return type \"str\" (expected \"int\")"
            },
            "bandit": {"success": True, "issues": ""},
            "all_passed": False
        }
    
    @pytest.fixture
    def validation_results_multiple_fail(self):
        """Результаты валидации с множественными ошибками."""
        return {
            "pytest": {
                "success": False,
                "output": "FAILED test_code.py::test_add - AssertionError: assert 3 == 5"
            },
            "mypy": {
                "success": False,
                "errors": "code.py:5: error: Missing return type annotation"
            },
            "bandit": {"success": True, "issues": ""},
            "all_passed": False
        }
    
    def test_init(self, debugger_agent):
        """Тест инициализации DebuggerAgent."""
        assert debugger_agent is not None
        assert debugger_agent.llm is not None
    
    def test_extract_error_details_pytest(self, debugger_agent, validation_results_pytest_fail):
        """Тест извлечения деталей ошибок pytest."""
        details = debugger_agent._extract_error_details(validation_results_pytest_fail)
        
        assert "pytest" in details
        assert details["pytest"] != ""
        assert "FAILED" in details["pytest"] or "AssertionError" in details["pytest"]
        assert details["mypy"] == ""
        assert details["bandit"] == ""
    
    def test_extract_error_details_mypy(self, debugger_agent, validation_results_mypy_fail):
        """Тест извлечения деталей ошибок mypy."""
        details = debugger_agent._extract_error_details(validation_results_mypy_fail)
        
        assert "mypy" in details
        assert details["mypy"] != ""
        assert "error:" in details["mypy"]
        assert details["pytest"] == ""
        assert details["bandit"] == ""
    
    def test_extract_error_details_multiple(self, debugger_agent, validation_results_multiple_fail):
        """Тест извлечения деталей при множественных ошибках."""
        details = debugger_agent._extract_error_details(validation_results_multiple_fail)
        
        assert details["pytest"] != ""
        assert details["mypy"] != ""
        assert "FAILED" in details["pytest"] or "AssertionError" in details["pytest"]
        assert "error:" in details["mypy"]
    
    def test_determine_error_type_pytest(self, debugger_agent, validation_results_pytest_fail):
        """Тест определения типа ошибки (pytest)."""
        error_type = debugger_agent._determine_error_type(validation_results_pytest_fail)
        assert error_type == "pytest"
    
    def test_determine_error_type_mypy(self, debugger_agent, validation_results_mypy_fail):
        """Тест определения типа ошибки (mypy)."""
        error_type = debugger_agent._determine_error_type(validation_results_mypy_fail)
        assert error_type == "mypy"
    
    def test_determine_error_type_multiple(self, debugger_agent, validation_results_multiple_fail):
        """Тест определения типа ошибки (multiple)."""
        error_type = debugger_agent._determine_error_type(validation_results_multiple_fail)
        assert error_type == "multiple"
    
    def test_build_analysis_prompt(self, debugger_agent, validation_results_pytest_fail):
        """Тест построения промпта для анализа."""
        error_details = debugger_agent._extract_error_details(validation_results_pytest_fail)
        error_type = debugger_agent._determine_error_type(validation_results_pytest_fail)
        
        prompt = debugger_agent._build_analysis_prompt(
            task="Test task",
            code="def add(a, b): return a + b",
            tests="def test_add(): assert add(1, 2) == 5",
            error_details=error_details,
            error_type=error_type
        )
        
        assert "Test task" in prompt
        assert "def add" in prompt
        assert "pytest ошибки" in prompt or "pytest" in prompt.lower()
        assert "ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ" in prompt or "ИНСТРУКЦИИ" in prompt
    
    def test_analyze_errors(self, validation_results_pytest_fail):
        """Тест анализа ошибок через LLM."""
        # Настраиваем мок LLM
        mock_llm = Mock()
        mock_llm.generate.return_value = """
ОПИСАНИЕ_ОШИБОК:
Тесты не проходят из-за неправильного результата функции

ПРИЧИНА:
Функция возвращает неверный результат. Тест ожидает 5, но получает 3.

ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ:
Fix the add function to return 5 instead of 3 when called with (1, 2)

УВЕРЕННОСТЬ: 0.9
"""
        
        with patch('agents.debugger.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.debugger.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = mock_llm
                
                # Отключаем structured output для теста (используем legacy путь с mock LLM)
                with patch('agents.debugger.is_structured_output_enabled', return_value=False):
                    agent = DebuggerAgent(model="test-model")
                    
                    result = agent.analyze_errors(
                        validation_results=validation_results_pytest_fail,
                        code="def add(a, b): return a + b",
                        tests="def test_add(): assert add(1, 2) == 5",
                        task="Test task"
                    )
                    
                    assert isinstance(result, DebugResult)
                    assert result.error_type == "pytest"
                    assert result.confidence > 0.0
                    assert len(result.fix_instructions) > 0
                    assert "Fix" in result.fix_instructions or "fix" in result.fix_instructions.lower()
    
    def test_parse_analysis_response(self, debugger_agent):
        """Тест парсинга ответа от LLM."""
        response = """
ОПИСАНИЕ_ОШИБОК:
Тесты не проходят

ПРИЧИНА:
Функция возвращает неверный результат

ИНСТРУКЦИИ_ДЛЯ_ИСПРАВЛЕНИЯ:
Fix the function to return correct value

УВЕРЕННОСТЬ: 0.85
"""
        
        error_details = {"pytest": "FAILED", "mypy": "", "bandit": ""}
        result = debugger_agent._parse_analysis_response(
            response=response,
            error_details=error_details,
            error_type="pytest"
        )
        
        assert isinstance(result, DebugResult)
        assert "Тесты не проходят" in result.error_summary or result.error_summary != ""
        assert "неверный результат" in result.root_cause or result.root_cause != ""
        assert "Fix" in result.fix_instructions or result.fix_instructions != ""
        assert result.confidence == 0.85
        assert result.error_type == "pytest"
    
    def test_parse_analysis_response_malformed(self, debugger_agent):
        """Тест парсинга некорректного ответа от LLM (fallback)."""
        response = "Some random text without structure"
        
        error_details = {"pytest": "FAILED", "mypy": "", "bandit": ""}
        result = debugger_agent._parse_analysis_response(
            response=response,
            error_details=error_details,
            error_type="pytest"
        )
        
        assert isinstance(result, DebugResult)
        # Должны быть базовые значения из error_details
        assert result.error_summary != ""
        assert result.fix_instructions != ""
        assert result.confidence >= 0.0
        assert result.error_type == "pytest"


class TestDebugResult:
    """Тесты для DebugResult dataclass."""
    
    def test_debug_result_creation(self):
        """Тест создания DebugResult."""
        result = DebugResult(
            error_summary="Test error",
            root_cause="Test cause",
            fix_instructions="Fix test",
            confidence=0.8,
            error_type="pytest"
        )
        
        assert result.error_summary == "Test error"
        assert result.root_cause == "Test cause"
        assert result.fix_instructions == "Fix test"
        assert result.confidence == 0.8
        assert result.error_type == "pytest"
