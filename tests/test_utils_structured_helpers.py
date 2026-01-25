"""Тесты для utils/structured_helpers.py."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pydantic import BaseModel
from infrastructure.local_llm import StructuredOutputError


class TestResponse(BaseModel):
    """Тестовая Pydantic модель для тестов."""
    value: str
    count: int


class TestIsStructuredOutputEnabled:
    """Тесты для функции is_structured_output_enabled."""
    
    @pytest.mark.utils

    
    def test_enabled_globally_and_for_agent(self):
        """Тест когда structured output включён глобально и для агента."""
        with patch('utils.structured_helpers.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "enabled": True,
                    "enabled_agents": ["intent", "debugger"]
                }
            }
            mock_get_config.return_value = mock_config
            
            from utils.structured_helpers import is_structured_output_enabled
            
            assert is_structured_output_enabled("intent") is True
            assert is_structured_output_enabled("debugger") is True
    
    @pytest.mark.utils

    
    def test_disabled_globally(self):
        """Тест когда structured output отключён глобально."""
        with patch('utils.structured_helpers.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "enabled": False,
                    "enabled_agents": ["intent"]
                }
            }
            mock_get_config.return_value = mock_config
            
            from utils.structured_helpers import is_structured_output_enabled
            
            assert is_structured_output_enabled("intent") is False
    
    @pytest.mark.utils

    
    def test_agent_not_in_enabled_list(self):
        """Тест когда агент не в списке enabled_agents."""
        with patch('utils.structured_helpers.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "enabled": True,
                    "enabled_agents": ["intent", "debugger"]
                }
            }
            mock_get_config.return_value = mock_config
            
            from utils.structured_helpers import is_structured_output_enabled
            
            assert is_structured_output_enabled("planner") is False
    
    @pytest.mark.utils

    
    def test_exception_handling(self):
        """Тест обработки исключений при проверке."""
        with patch('utils.structured_helpers.get_config', side_effect=Exception("Config error")):
            from utils.structured_helpers import is_structured_output_enabled
            
            # При ошибке должна вернуться False
            assert is_structured_output_enabled("intent") is False
    
    @pytest.mark.utils

    
    def test_default_enabled_true(self):
        """Тест когда enabled не указан (по умолчанию True)."""
        with patch('utils.structured_helpers.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "enabled_agents": ["intent"]
                }
            }
            mock_get_config.return_value = mock_config
            
            from utils.structured_helpers import is_structured_output_enabled
            
            assert is_structured_output_enabled("intent") is True


class TestGenerateWithFallback:
    """Тесты для функции generate_with_fallback (sync)."""
    
    @pytest.mark.utils

    
    def test_structured_output_disabled_uses_fallback(self):
        """Тест когда structured output отключён - используется fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=False):
            from utils.structured_helpers import generate_with_fallback
            
            mock_llm = Mock()
            fallback_result = TestResponse(value="fallback", count=1)
            fallback_fn = Mock(return_value=fallback_result)
            
            result = generate_with_fallback(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == fallback_result
            fallback_fn.assert_called_once()
            mock_llm.generate_structured.assert_not_called()
    
    @pytest.mark.utils

    
    def test_structured_output_success(self):
        """Тест успешного structured output."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True):
            from utils.structured_helpers import generate_with_fallback
            
            mock_llm = Mock()
            structured_result = TestResponse(value="structured", count=2)
            mock_llm.generate_structured.return_value = structured_result
            
            fallback_fn = Mock()
            
            result = generate_with_fallback(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == structured_result
            mock_llm.generate_structured.assert_called_once()
            fallback_fn.assert_not_called()
    
    @pytest.mark.utils

    
    def test_structured_output_error_with_fallback_allowed(self):
        """Тест ошибки structured output с разрешённым fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True), \
             patch('utils.structured_helpers.get_config') as mock_get_config:
            from utils.structured_helpers import generate_with_fallback
            
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "fallback_to_manual_parsing": True
                }
            }
            mock_get_config.return_value = mock_config
            
            mock_llm = Mock()
            mock_llm.generate_structured.side_effect = StructuredOutputError("Parse error")
            
            fallback_result = TestResponse(value="fallback", count=3)
            fallback_fn = Mock(return_value=fallback_result)
            
            result = generate_with_fallback(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == fallback_result
            fallback_fn.assert_called_once()
    
    @pytest.mark.utils

    
    def test_structured_output_error_with_fallback_disabled(self):
        """Тест ошибки structured output с отключённым fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True), \
             patch('utils.structured_helpers.get_config') as mock_get_config:
            from utils.structured_helpers import generate_with_fallback
            
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "fallback_to_manual_parsing": False
                }
            }
            mock_get_config.return_value = mock_config
            
            mock_llm = Mock()
            mock_llm.generate_structured.side_effect = StructuredOutputError("Parse error")
            
            fallback_fn = Mock()
            
            with pytest.raises(StructuredOutputError):
                generate_with_fallback(
                    llm=mock_llm,
                    prompt="test",
                    response_model=TestResponse,
                    fallback_fn=fallback_fn,
                    agent_name="intent"
                )
            
            fallback_fn.assert_not_called()
    
    @pytest.mark.utils

    
    def test_custom_num_predict_and_retries(self):
        """Тест передачи кастомных параметров num_predict и retries."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True):
            from utils.structured_helpers import generate_with_fallback
            
            mock_llm = Mock()
            structured_result = TestResponse(value="test", count=1)
            mock_llm.generate_structured.return_value = structured_result
            
            result = generate_with_fallback(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=Mock(),
                agent_name="intent",
                num_predict=2048,
                retries=3
            )
            
            mock_llm.generate_structured.assert_called_once_with(
                prompt="test",
                response_model=TestResponse,
                num_predict=2048,
                retries=3
            )


class TestGenerateWithFallbackAsync:
    """Тесты для функции generate_with_fallback_async."""
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_disabled_uses_fallback_sync(self):
        """Тест когда structured output отключён - используется sync fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=False):
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_llm = Mock()
            fallback_result = TestResponse(value="fallback", count=1)
            fallback_fn = Mock(return_value=fallback_result)
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == fallback_result
            fallback_fn.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_disabled_uses_fallback_async(self):
        """Тест когда structured output отключён - используется async fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=False):
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_llm = Mock()
            fallback_result = TestResponse(value="fallback", count=1)
            
            async def async_fallback():
                return fallback_result
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=async_fallback,
                agent_name="intent"
            )
            
            assert result == fallback_result
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_success(self):
        """Тест успешного async structured output."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True):
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_llm = AsyncMock()
            structured_result = TestResponse(value="structured", count=2)
            mock_llm.generate_structured_async.return_value = structured_result
            
            fallback_fn = Mock()
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == structured_result
            mock_llm.generate_structured_async.assert_called_once()
            fallback_fn.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_error_with_fallback_allowed(self):
        """Тест ошибки async structured output с разрешённым fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True), \
             patch('utils.structured_helpers.get_config') as mock_get_config:
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "fallback_to_manual_parsing": True
                }
            }
            mock_get_config.return_value = mock_config
            
            mock_llm = AsyncMock()
            mock_llm.generate_structured_async.side_effect = StructuredOutputError("Parse error")
            
            fallback_result = TestResponse(value="fallback", count=3)
            fallback_fn = Mock(return_value=fallback_result)
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=fallback_fn,
                agent_name="intent"
            )
            
            assert result == fallback_result
            fallback_fn.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_error_with_async_fallback(self):
        """Тест ошибки с async fallback функцией."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True), \
             patch('utils.structured_helpers.get_config') as mock_get_config:
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "fallback_to_manual_parsing": True
                }
            }
            mock_get_config.return_value = mock_config
            
            mock_llm = AsyncMock()
            mock_llm.generate_structured_async.side_effect = StructuredOutputError("Parse error")
            
            fallback_result = TestResponse(value="fallback", count=4)
            
            async def async_fallback():
                return fallback_result
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=async_fallback,
                agent_name="intent"
            )
            
            assert result == fallback_result
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_structured_output_error_with_fallback_disabled(self):
        """Тест ошибки async structured output с отключённым fallback."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True), \
             patch('utils.structured_helpers.get_config') as mock_get_config:
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_config = Mock()
            mock_config._config_data = {
                "structured_output": {
                    "fallback_to_manual_parsing": False
                }
            }
            mock_get_config.return_value = mock_config
            
            mock_llm = AsyncMock()
            mock_llm.generate_structured_async.side_effect = StructuredOutputError("Parse error")
            
            fallback_fn = Mock()
            
            with pytest.raises(StructuredOutputError):
                await generate_with_fallback_async(
                    llm=mock_llm,
                    prompt="test",
                    response_model=TestResponse,
                    fallback_fn=fallback_fn,
                    agent_name="intent"
                )
            
            fallback_fn.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.utils

    async def test_custom_num_predict_and_retries(self):
        """Тест передачи кастомных параметров для async версии."""
        with patch('utils.structured_helpers.is_structured_output_enabled', return_value=True):
            from utils.structured_helpers import generate_with_fallback_async
            
            mock_llm = AsyncMock()
            structured_result = TestResponse(value="test", count=1)
            mock_llm.generate_structured_async.return_value = structured_result
            
            result = await generate_with_fallback_async(
                llm=mock_llm,
                prompt="test",
                response_model=TestResponse,
                fallback_fn=Mock(),
                agent_name="intent",
                num_predict=2048,
                retries=3
            )
            
            mock_llm.generate_structured_async.assert_called_once_with(
                prompt="test",
                response_model=TestResponse,
                num_predict=2048,
                retries=3
            )
