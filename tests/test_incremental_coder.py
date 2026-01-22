"""Тесты для IncrementalCoder (Compiler-in-the-Loop Phase 3)."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

from agents.incremental_coder import IncrementalCoder, FunctionSpec, GenerationStep
from utils.validation import validate_code_quick


class TestValidateCodeQuick:
    """Тесты для validate_code_quick()."""
    
    def test_valid_code_no_tests(self):
        """Тест валидного кода без тестов."""
        code = "def add(a, b): return a + b"
        result = validate_code_quick(code)
        assert result["passed"] is True
        assert result["error"] is None
    
    def test_valid_code_with_passing_tests(self):
        """Тест валидного кода с проходящими тестами."""
        code = "def add(a, b): return a + b"
        tests = "assert add(1, 2) == 3"
        result = validate_code_quick(code, tests)
        assert result["passed"] is True
        assert result["error"] is None
    
    def test_valid_code_with_failing_tests(self):
        """Тест валидного кода с падающими тестами."""
        code = "def add(a, b): return a + b"
        tests = "assert add(1, 2) == 5"  # Неверный ожидаемый результат
        result = validate_code_quick(code, tests)
        assert result["passed"] is False
        assert "AssertionError" in result["error"]
    
    def test_syntax_error(self):
        """Тест кода с синтаксической ошибкой."""
        code = "def add(a, b return a + b"  # Отсутствует ):
        result = validate_code_quick(code)
        assert result["passed"] is False
        assert "SyntaxError" in result["error"]
    
    def test_empty_code(self):
        """Тест пустого кода."""
        result = validate_code_quick("")
        assert result["passed"] is False
        assert "Empty code" in result["error"]
    
    def test_runtime_error(self):
        """Тест с runtime ошибкой."""
        code = "def divide(a, b): return a / b"
        tests = "divide(1, 0)"  # Division by zero
        result = validate_code_quick(code, tests)
        assert result["passed"] is False
        assert "RuntimeError" in result["error"] or "ZeroDivision" in result["error"]
    
    def test_name_error(self):
        """Тест с NameError."""
        code = "def greet(): return hello"  # hello не определено
        tests = "greet()"
        result = validate_code_quick(code, tests)
        assert result["passed"] is False
        assert "NameError" in result["error"]
    
    def test_type_error(self):
        """Тест с TypeError."""
        code = "def add(a, b): return a + b"
        tests = "add('1', 2)"  # Нельзя сложить str и int
        result = validate_code_quick(code, tests)
        assert result["passed"] is False
        assert "TypeError" in result["error"]


class TestFunctionSpec:
    """Тесты для FunctionSpec dataclass."""
    
    def test_function_spec_creation(self):
        """Тест создания FunctionSpec."""
        spec = FunctionSpec(
            name="calculate_sum",
            signature="def calculate_sum(numbers: list[int]) -> int",
            description="Вычисляет сумму чисел"
        )
        assert spec.name == "calculate_sum"
        assert "list[int]" in spec.signature
        assert spec.dependencies == []
    
    def test_function_spec_with_dependencies(self):
        """Тест FunctionSpec с зависимостями."""
        spec = FunctionSpec(
            name="process_data",
            signature="def process_data(data: list) -> list",
            description="Обработка данных",
            dependencies=["validate_data", "transform_data"]
        )
        assert len(spec.dependencies) == 2
        assert "validate_data" in spec.dependencies


class TestGenerationStep:
    """Тесты для GenerationStep dataclass."""
    
    def test_generation_step_success(self):
        """Тест успешного шага генерации."""
        step = GenerationStep(
            function_name="add",
            code="def add(a, b): return a + b",
            tests_passed=True,
            status="passed"
        )
        assert step.tests_passed is True
        assert step.fix_attempts == 0
        assert step.error is None
    
    def test_generation_step_failure(self):
        """Тест неуспешного шага генерации."""
        step = GenerationStep(
            function_name="divide",
            code="def divide(a, b): return a / b",
            tests_passed=False,
            error="ZeroDivisionError",
            fix_attempts=3,
            status="failed"
        )
        assert step.tests_passed is False
        assert step.fix_attempts == 3
        assert "ZeroDivision" in step.error


class TestIncrementalCoder:
    """Тесты для IncrementalCoder."""
    
    @pytest.fixture
    def mock_llm(self):
        """Мок LLM."""
        mock = Mock()
        mock.generate = Mock(return_value='```python\ndef test_func(): pass\n```')
        return mock
    
    def test_init(self):
        """Тест инициализации IncrementalCoder."""
        with patch('agents.incremental_coder.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.incremental_coder.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = Mock()
                
                coder = IncrementalCoder()
                assert coder.model == "test-model"
                assert coder.MAX_FIX_ATTEMPTS == 3
    
    def test_parse_functions_json_valid(self):
        """Тест парсинга валидного JSON с функциями."""
        with patch('agents.incremental_coder.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.incremental_coder.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = Mock()
                
                coder = IncrementalCoder()
                
                response = """Here are the functions:
                [
                    {"name": "add", "signature": "def add(a: int, b: int) -> int", "description": "Adds two numbers"},
                    {"name": "multiply", "signature": "def multiply(a: int, b: int) -> int", "description": "Multiplies numbers", "dependencies": ["add"]}
                ]
                """
                
                functions = coder._parse_functions_json(response)
                assert len(functions) == 2
                assert functions[0].name == "add"
                assert functions[1].name == "multiply"
                assert "add" in functions[1].dependencies
    
    def test_parse_functions_json_invalid(self):
        """Тест парсинга невалидного JSON."""
        with patch('agents.incremental_coder.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.incremental_coder.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = Mock()
                
                coder = IncrementalCoder()
                
                response = "This is not valid JSON"
                
                functions = coder._parse_functions_json(response)
                assert len(functions) == 0
    
    def test_extract_function_code(self):
        """Тест извлечения кода функции."""
        with patch('agents.incremental_coder.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.incremental_coder.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = Mock()
                
                coder = IncrementalCoder()
                
                response = """Here is the function:
                ```python
                def add(a: int, b: int) -> int:
                    \"\"\"Adds two integers.\"\"\"
                    return a + b
                ```
                """
                
                code = coder._extract_function_code(response, "add")
                assert "def add" in code
                assert "return a + b" in code
    
    def test_extract_relevant_tests(self):
        """Тест извлечения релевантных тестов."""
        with patch('agents.incremental_coder.get_model_router') as mock_router:
            mock_router_instance = Mock()
            mock_router_instance.select_model.return_value = Mock(model="test-model")
            mock_router.return_value = mock_router_instance
            
            with patch('agents.incremental_coder.create_llm_for_stage') as mock_llm_factory:
                mock_llm_factory.return_value = Mock()
                
                coder = IncrementalCoder()
                
                tests = """
def test_add_positive():
    assert add(1, 2) == 3

def test_multiply_positive():
    assert multiply(2, 3) == 6

def test_add_negative():
    assert add(-1, -2) == -3
"""
                
                relevant = coder._extract_relevant_tests(tests, "add")
                assert "test_add" in relevant
                # Может включать или не включать multiply в зависимости от логики


class TestSSEIncrementalProgress:
    """Тесты для SSE событий инкрементального прогресса."""
    
    @pytest.mark.asyncio
    async def test_stream_incremental_progress(self):
        """Тест генерации SSE события."""
        from backend.sse_manager import SSEManager
        
        event = await SSEManager.stream_incremental_progress(
            function_name="calculate_sum",
            status="passed",
            current=2,
            total=5,
            fix_attempts=0
        )
        
        assert "event: incremental_progress" in event
        assert "calculate_sum" in event
        assert '"status": "passed"' in event
        assert '"current": 2' in event
        assert '"total": 5' in event
    
    @pytest.mark.asyncio
    async def test_stream_incremental_progress_with_error(self):
        """Тест SSE события с ошибкой."""
        from backend.sse_manager import SSEManager
        
        event = await SSEManager.stream_incremental_progress(
            function_name="divide",
            status="failed",
            current=3,
            total=5,
            fix_attempts=3,
            error="ZeroDivisionError"
        )
        
        assert "event: incremental_progress" in event
        assert '"status": "failed"' in event
        assert "ZeroDivisionError" in event
