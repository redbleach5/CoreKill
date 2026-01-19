"""Тесты для валидаторов."""
import pytest
from backend.validators import TaskRequestV2, FeedbackRequestV2


class TestTaskRequestV2:
    """Тесты для TaskRequestV2."""
    
    def test_valid_task_request(self):
        """Тест валидного запроса."""
        req = TaskRequestV2(task="Create a function")
        assert req.task == "Create a function"
        assert req.temperature == 0.25
    
    def test_task_too_short(self):
        """Тест слишком короткой задачи."""
        with pytest.raises(ValueError):
            TaskRequestV2(task="")
    
    def test_task_with_dangerous_pattern(self):
        """Тест задачи с опасным паттерном."""
        with pytest.raises(ValueError):
            TaskRequestV2(task="eval('print(1)')")
    
    def test_temperature_bounds(self):
        """Тест граничных значений температуры."""
        req_min = TaskRequestV2(task="test", temperature=0.1)
        assert req_min.temperature == 0.1
        
        req_max = TaskRequestV2(task="test", temperature=0.7)
        assert req_max.temperature == 0.7


class TestFeedbackRequestV2:
    """Тесты для FeedbackRequestV2."""
    
    def test_valid_positive_feedback(self):
        """Тест валидного положительного feedback."""
        req = FeedbackRequestV2(
            task="Create function",
            feedback="positive"
        )
        assert req.feedback == "positive"
    
    def test_valid_negative_feedback(self):
        """Тест валидного отрицательного feedback."""
        req = FeedbackRequestV2(
            task="Create function",
            feedback="negative"
        )
        assert req.feedback == "negative"
    
    def test_invalid_feedback(self):
        """Тест невалидного feedback."""
        with pytest.raises(ValueError):
            FeedbackRequestV2(
                task="Create function",
                feedback="invalid"
            )
