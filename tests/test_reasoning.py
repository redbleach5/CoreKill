"""Тесты для reasoning utilities и structured output."""
import pytest
from unittest.mock import MagicMock, patch

from infrastructure.reasoning_utils import (
    ReasoningResponse,
    parse_reasoning_response,
    extract_answer_only,
    extract_code_from_reasoning,
    is_reasoning_response,
    format_thinking_for_log,
    get_thinking_summary,
)
from models.agent_responses import (
    IntentType,
    IntentResponse,
    PlanStep,
    PlanResponse,
    ErrorType,
    DebugResponse,
    IssueSeverity,
    CodeIssue,
    CriticResponse,
)
from pydantic import ValidationError


class TestReasoningResponse:
    """Тесты для ReasoningResponse dataclass."""
    
    def test_basic_response(self):
        """Тест базового создания ReasoningResponse."""
        resp = ReasoningResponse(
            thinking="Думаю...",
            answer="Ответ",
            raw="<think>Думаю...</think>\nОтвет",
            has_thinking=True
        )
        assert resp.thinking == "Думаю..."
        assert resp.answer == "Ответ"
        assert resp.has_thinking is True
        assert resp.thinking_lines == 1
        assert resp.answer_lines == 1
    
    def test_empty_response(self):
        """Тест пустого ответа."""
        resp = ReasoningResponse(
            thinking="",
            answer="",
            raw="",
            has_thinking=False
        )
        assert resp.thinking_lines == 0  # Пустая строка = 0 строк (split возвращает [''] но len считает содержимое)
        assert resp.answer_lines == 0


class TestParseReasoningResponse:
    """Тесты для парсинга <think> блоков."""
    
    def test_parse_with_think_block(self):
        """Тест парсинга ответа с <think> блоком."""
        response = """<think>
Анализирую задачу...
Шаг 1: понять требования
Шаг 2: написать код
</think>

def hello():
    print("Hello!")"""
        
        parsed = parse_reasoning_response(response)
        
        assert parsed.has_thinking is True
        assert "Анализирую задачу" in parsed.thinking
        assert "Шаг 1" in parsed.thinking
        assert "def hello" in parsed.answer
        assert "<think>" not in parsed.answer
        assert "</think>" not in parsed.answer
    
    def test_parse_without_think_block(self):
        """Тест парсинга ответа без <think> блока."""
        response = "def hello(): pass"
        
        parsed = parse_reasoning_response(response)
        
        assert parsed.has_thinking is False
        assert parsed.thinking == ""
        assert parsed.answer == "def hello(): pass"
    
    def test_parse_empty_response(self):
        """Тест парсинга пустого ответа."""
        parsed = parse_reasoning_response("")
        
        assert parsed.has_thinking is False
        assert parsed.thinking == ""
        assert parsed.answer == ""
    
    def test_parse_thinking_alternative_tag(self):
        """Тест парсинга с альтернативным тегом <thinking>."""
        response = """<thinking>
Рассуждаю...
</thinking>

result = 42"""
        
        parsed = parse_reasoning_response(response)
        
        assert parsed.has_thinking is True
        assert "Рассуждаю" in parsed.thinking
        assert "result = 42" in parsed.answer
    
    def test_parse_multiline_thinking(self):
        """Тест многострочного <think> блока."""
        response = """<think>
Строка 1
Строка 2
Строка 3
Строка 4
Строка 5
</think>

код здесь"""
        
        parsed = parse_reasoning_response(response)
        
        assert parsed.thinking_lines >= 5
        assert "Строка 3" in parsed.thinking


class TestExtractAnswerOnly:
    """Тесты для extract_answer_only."""
    
    def test_extract_removes_think(self):
        """Тест что <think> блок удаляется."""
        response = "<think>Думаю...</think>\n\nОтвет"
        answer = extract_answer_only(response)
        
        assert answer == "Ответ"
        assert "<think>" not in answer
    
    def test_extract_no_think(self):
        """Тест без <think> блока."""
        response = "Просто ответ"
        answer = extract_answer_only(response)
        
        assert answer == "Просто ответ"


class TestExtractCodeFromReasoning:
    """Тесты для извлечения кода."""
    
    def test_extract_code_with_markdown(self):
        """Тест извлечения кода из markdown блока."""
        response = """<think>
Пишу функцию...
</think>

```python
def add(a, b):
    return a + b
```"""
        
        code = extract_code_from_reasoning(response)
        
        assert "def add" in code
        assert "```" not in code
        assert "<think>" not in code
    
    def test_extract_code_without_markdown(self):
        """Тест когда код без markdown блока."""
        response = """<think>Думаю</think>

def add(a, b):
    return a + b"""
        
        code = extract_code_from_reasoning(response)
        
        assert "def add" in code
    
    def test_extract_empty(self):
        """Тест пустого ответа."""
        code = extract_code_from_reasoning("")
        assert code == ""


class TestIsReasoningResponse:
    """Тесты для is_reasoning_response."""
    
    def test_is_reasoning_true(self):
        """Тест обнаружения <think> блока."""
        assert is_reasoning_response("<think>test</think>") is True
        assert is_reasoning_response("<thinking>test</thinking>") is True
        assert is_reasoning_response("<THINK>test</THINK>") is True
    
    def test_is_reasoning_false(self):
        """Тест отсутствия <think> блока."""
        assert is_reasoning_response("just text") is False
        assert is_reasoning_response("") is False
        assert is_reasoning_response("think about it") is False


class TestFormatThinkingForLog:
    """Тесты для форматирования логов."""
    
    def test_format_short(self):
        """Тест короткого текста."""
        thinking = "Строка 1\nСтрока 2\nСтрока 3"
        formatted = format_thinking_for_log(thinking, max_lines=10)
        
        assert formatted == thinking
    
    def test_format_long(self):
        """Тест длинного текста."""
        lines = [f"Строка {i}" for i in range(20)]
        thinking = "\n".join(lines)
        formatted = format_thinking_for_log(thinking, max_lines=6)
        
        assert "скрыто" in formatted
        assert "Строка 0" in formatted  # Первые строки
        assert "Строка 19" in formatted  # Последние строки
    
    def test_format_empty(self):
        """Тест пустого текста."""
        formatted = format_thinking_for_log("")
        assert formatted == "(пусто)"


class TestGetThinkingSummary:
    """Тесты для краткой сводки."""
    
    def test_summary_short(self):
        """Тест короткого текста."""
        thinking = "Короткая мысль."
        summary = get_thinking_summary(thinking)
        
        assert summary == "Короткая мысль."
    
    def test_summary_long(self):
        """Тест длинного текста."""
        thinking = "Это очень длинное предложение " * 10
        summary = get_thinking_summary(thinking, max_length=50)
        
        assert len(summary) <= 55  # 50 + "..."
        assert summary.endswith("...")
    
    def test_summary_empty(self):
        """Тест пустого текста."""
        summary = get_thinking_summary("")
        assert summary == ""


class TestIntentResponse:
    """Тесты для Pydantic модели IntentResponse."""
    
    def test_valid_response(self):
        """Тест валидного ответа."""
        data = {
            "intent": "create",
            "confidence": 0.95,
            "complexity": "medium",
            "reasoning": "Пользователь хочет создать код"
        }
        
        response = IntentResponse.model_validate(data)
        
        assert response.intent == IntentType.CREATE
        assert response.confidence == 0.95
        assert response.complexity == "medium"
        assert response.reasoning == "Пользователь хочет создать код"
    
    def test_invalid_confidence_too_high(self):
        """Тест невалидной confidence > 1."""
        data = {
            "intent": "create",
            "confidence": 1.5,
            "complexity": "medium"
        }
        
        with pytest.raises(ValidationError):
            IntentResponse.model_validate(data)
    
    def test_invalid_confidence_negative(self):
        """Тест отрицательной confidence."""
        data = {
            "intent": "create",
            "confidence": -0.1,
            "complexity": "medium"
        }
        
        with pytest.raises(ValidationError):
            IntentResponse.model_validate(data)
    
    def test_invalid_intent_type(self):
        """Тест невалидного типа intent."""
        data = {
            "intent": "invalid_type",
            "confidence": 0.9,
            "complexity": "medium"
        }
        
        with pytest.raises(ValidationError):
            IntentResponse.model_validate(data)
    
    def test_invalid_complexity(self):
        """Тест невалидной сложности."""
        data = {
            "intent": "create",
            "confidence": 0.9,
            "complexity": "super_complex"
        }
        
        with pytest.raises(ValidationError):
            IntentResponse.model_validate(data)
    
    def test_optional_reasoning(self):
        """Тест что reasoning опционален."""
        data = {
            "intent": "debug",
            "confidence": 0.8,
            "complexity": "simple"
        }
        
        response = IntentResponse.model_validate(data)
        assert response.reasoning is None
    
    def test_json_serialization(self):
        """Тест сериализации в JSON."""
        response = IntentResponse(
            intent=IntentType.ANALYZE,
            confidence=0.9,
            complexity="complex"
        )
        
        json_str = response.model_dump_json()
        assert '"intent":"analyze"' in json_str or '"intent": "analyze"' in json_str


class TestPlanResponse:
    """Тесты для PlanResponse."""
    
    def test_valid_plan(self):
        """Тест валидного плана."""
        data = {
            "goal": "Создать HTTP клиент",
            "steps": [
                {
                    "step_number": 1,
                    "action": "Создать класс HTTPClient",
                    "expected_output": "Класс с базовыми методами",
                    "dependencies": []
                },
                {
                    "step_number": 2,
                    "action": "Добавить метод GET",
                    "expected_output": "Метод для GET запросов",
                    "dependencies": [1]
                }
            ],
            "estimated_complexity": "medium",
            "suggested_approach": "Использовать httpx для async"
        }
        
        response = PlanResponse.model_validate(data)
        
        assert response.goal == "Создать HTTP клиент"
        assert len(response.steps) == 2
        assert response.steps[0].step_number == 1
        assert response.steps[1].dependencies == [1]
    
    def test_empty_steps(self):
        """Тест что пустой список шагов невалиден."""
        data = {
            "goal": "Тест",
            "steps": [],
            "estimated_complexity": "simple",
            "suggested_approach": "Тест"
        }
        
        with pytest.raises(ValidationError):
            PlanResponse.model_validate(data)


class TestDebugResponse:
    """Тесты для DebugResponse."""
    
    def test_valid_debug(self):
        """Тест валидного debug ответа."""
        data = {
            "error_type": "type",
            "error_location": "utils/parser.py:42",
            "root_cause": "Передаётся str вместо int",
            "fix_instructions": "Добавить int() преобразование",
            "confidence": 0.9
        }
        
        response = DebugResponse.model_validate(data)
        
        assert response.error_type == ErrorType.TYPE
        assert response.confidence == 0.9


class TestCriticResponse:
    """Тесты для CriticResponse."""
    
    def test_valid_critic(self):
        """Тест валидного critic ответа."""
        data = {
            "overall_score": 0.75,
            "issues": [
                {
                    "severity": "medium",
                    "category": "performance",
                    "location": "main.py:10",
                    "description": "N+1 запрос",
                    "suggestion": "Использовать batch запрос"
                }
            ],
            "strengths": ["Хорошая документация"],
            "summary": "Код работает, но есть проблемы"
        }
        
        response = CriticResponse.model_validate(data)
        
        assert response.overall_score == 0.75
        assert len(response.issues) == 1
        assert response.issues[0].severity == IssueSeverity.MEDIUM


class TestModelChecker:
    """Тесты для детекции reasoning моделей в model_checker."""
    
    def test_is_reasoning_model_deepseek(self):
        """Тест детекции DeepSeek-R1."""
        from utils.model_checker import _is_reasoning_model
        
        assert _is_reasoning_model("deepseek-r1:7b") is True
        assert _is_reasoning_model("deepseek-r1:14b") is True
        assert _is_reasoning_model("DEEPSEEK-R1:32B") is True
    
    def test_is_reasoning_model_qwq(self):
        """Тест детекции QwQ."""
        from utils.model_checker import _is_reasoning_model
        
        assert _is_reasoning_model("qwq:32b") is True
        assert _is_reasoning_model("QWQ:32B") is True
    
    def test_is_reasoning_model_false(self):
        """Тест что обычные модели не reasoning."""
        from utils.model_checker import _is_reasoning_model
        
        assert _is_reasoning_model("qwen2.5-coder:7b") is False
        assert _is_reasoning_model("llama3:8b") is False
        assert _is_reasoning_model("codellama:13b") is False


class TestModelInfo:
    """Тесты для ModelInfo с reasoning."""
    
    def test_model_info_with_reasoning(self):
        """Тест что ModelInfo содержит is_reasoning поле."""
        from utils.model_checker import ModelInfo
        
        info = ModelInfo(
            name="deepseek-r1:7b",
            size_bytes=4_000_000_000,
            parameter_size="7B",
            quantization="Q4_K_M",
            family="deepseek",
            is_coder=False,
            is_reasoning=True,
            estimated_quality=0.85
        )
        
        assert info.is_reasoning is True
        assert info.name == "deepseek-r1:7b"
