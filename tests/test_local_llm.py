"""Тесты для LocalLLM."""
import pytest
from infrastructure.local_llm import LocalLLM


class TestLocalLLM:
    """Тесты для класса LocalLLM."""
    
    def test_init(self):
        """Тест инициализации LocalLLM."""
        llm = LocalLLM(model="test-model", temperature=0.25)
        assert llm is not None
        assert llm.model == "test-model"
        assert llm.temperature == 0.25
    
    def test_temperature_bounds(self):
        """Тест граничных значений температуры."""
        llm_min = LocalLLM(model="test", temperature=0.0)
        assert llm_min.temperature == 0.0
        
        llm_max = LocalLLM(model="test", temperature=1.0)
        assert llm_max.temperature == 1.0
