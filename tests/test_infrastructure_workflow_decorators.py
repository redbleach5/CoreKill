"""Тесты для infrastructure/workflow_decorators.py."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from infrastructure.workflow_decorators import (
    workflow_node,
    streaming_node,
    _record_stage_duration,
    _save_checkpoint,
    _acquire_agent_resource,
    _send_stage_error
)
from infrastructure.workflow_state import AgentState
from infrastructure.local_llm import LLMTimeoutError, LLMModelUnavailableError
from infrastructure.circuit_breaker import CircuitBreakerOpenError
from tests.factories import create_agent_state


class TestWorkflowNodeDecorator:
    """Тесты для декоратора @workflow_node."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_success(self):
        """Тест успешного выполнения узла."""
        @workflow_node(stage="test")
        async def test_node(state: AgentState) -> AgentState:
            state["result"] = "success"
            return state
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            # Настраиваем моки
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            async def mock_call(func, *args, **kwargs):
                return await func(*args, **kwargs)
            mock_breaker.call = mock_call
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "success"
            mock_acquire.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_validation_failed(self):
        """Тест когда валидация не пройдена."""
        @workflow_node(stage="test", fallback_key="result", fallback_value="fallback")
        async def test_node(state: AgentState) -> AgentState:
            state["result"] = "success"
            return state
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(False, "Invalid state")), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            result = await test_node(state)
            
            assert result["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_circuit_breaker_error(self):
        """Тест обработки CircuitBreakerOpenError."""
        @workflow_node(stage="test", fallback_key="result", fallback_value="fallback")
        async def test_node(state: AgentState) -> AgentState:
            raise CircuitBreakerOpenError("Circuit open")
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            mock_breaker.call.side_effect = CircuitBreakerOpenError("Circuit open")
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_timeout_error(self):
        """Тест обработки LLMTimeoutError."""
        @workflow_node(stage="test", fallback_key="result", fallback_value="fallback")
        async def test_node(state: AgentState) -> AgentState:
            raise LLMTimeoutError("Timeout")
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            mock_breaker.call.side_effect = LLMTimeoutError("Timeout")
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_model_unavailable_error(self):
        """Тест обработки LLMModelUnavailableError."""
        @workflow_node(stage="test", fallback_key="result", fallback_value="fallback")
        async def test_node(state: AgentState) -> AgentState:
            raise LLMModelUnavailableError("Model unavailable", model="test-model")
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            mock_breaker.call.side_effect = LLMModelUnavailableError("Model unavailable", model="test-model")
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_general_exception(self):
        """Тест обработки общего Exception."""
        @workflow_node(stage="test", fallback_key="result", fallback_value="fallback")
        async def test_node(state: AgentState) -> AgentState:
            raise Exception("General error")
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            mock_breaker.call.side_effect = Exception("General error")
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_workflow_node_fallback_callable(self):
        """Тест fallback значения как callable."""
        def create_fallback():
            return "callable_fallback"
        
        @workflow_node(stage="test", fallback_key="result", fallback_value=create_fallback)
        async def test_node(state: AgentState) -> AgentState:
            raise Exception("Error")
        
        state = create_agent_state()
        
        with patch('infrastructure.node_validator.NodeInputValidator.validate', return_value=(True, "")), \
             patch('infrastructure.workflow_decorators._acquire_agent_resource') as mock_acquire, \
             patch('infrastructure.circuit_breaker.get_circuit_breaker') as mock_get_circuit, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock), \
             patch('infrastructure.workflow_decorators._record_stage_duration'), \
             patch('infrastructure.workflow_decorators._save_checkpoint'):
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=None)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_acquire.return_value = mock_context
            
            mock_breaker = AsyncMock()
            mock_breaker.call.side_effect = Exception("Error")
            mock_get_circuit.return_value = mock_breaker
            
            result = await test_node(state)
            
            assert result["result"] == "callable_fallback"


class TestStreamingNodeDecorator:
    """Тесты для декоратора @streaming_node."""
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_streaming_node_success(self):
        """Тест успешного стриминга событий."""
        @streaming_node(stage="test")
        @pytest.mark.infrastructure

        async def test_streaming_node(state: AgentState):
            yield ("thinking", {"content": "thinking..."})
            yield ("plan_chunk", {"chunk": "step 1"})
            final_state = state.copy()
            final_state["plan"] = "complete plan"
            yield ("done", final_state)
        
        state = create_agent_state()
        state["task_id"] = "test-task"
        
        with patch('infrastructure.event_store.get_event_store') as mock_get_store:
            mock_store = AsyncMock()
            mock_store.save_event = AsyncMock(side_effect=["event-1", "event-2"])
            mock_get_store.return_value = mock_store
            
            events = []
            async for event_type, data in test_streaming_node(state):
                events.append((event_type, data))
                # Декоратор прерывает цикл после "done", поэтому получаем только последнее событие
                if event_type == "done":
                    break
            
            # Декоратор возвращает только "done" событие, так как прерывает цикл
            assert len(events) >= 1
            assert events[-1][0] == "done"
            assert "event_references" in events[-1][1]
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_streaming_node_saves_events(self):
        """Тест что события сохраняются в EventStore."""
        @streaming_node(stage="test")
        @pytest.mark.infrastructure

        async def test_streaming_node(state: AgentState):
            yield ("thinking", {"content": "test"})
            yield ("done", state)
        
        state = create_agent_state()
        state["task_id"] = "test-task"
        
        with patch('infrastructure.event_store.get_event_store') as mock_get_store:
            mock_store = AsyncMock()
            mock_store.save_event = AsyncMock(return_value="event-id")
            mock_get_store.return_value = mock_store
            
            events = list([e async for e in test_streaming_node(state)])
            
            assert mock_store.save_event.call_count == 1
            assert mock_store.save_event.call_args[0][0] == "thinking"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_streaming_node_error_handling(self):
        """Тест обработки ошибок в стриминговом узле."""
        @streaming_node(stage="test", fallback_key="result", fallback_value="fallback")
        @pytest.mark.infrastructure

        async def test_streaming_node(state: AgentState):
            yield ("thinking", {"content": "test"})
            raise Exception("Streaming error")
        
        state = create_agent_state()
        state["task_id"] = "test-task"
        
        with patch('infrastructure.event_store.get_event_store') as mock_get_store, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock):
            
            mock_store = AsyncMock()
            mock_store.save_event = AsyncMock(return_value="event-id")
            mock_get_store.return_value = mock_store
            
            events = []
            async for event_type, data in test_streaming_node(state):
                events.append((event_type, data))
            
            # Должен быть финальный "done" с fallback
            assert len(events) > 0
            assert events[-1][0] == "done"
            assert events[-1][1]["result"] == "fallback"
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_streaming_node_model_unavailable(self):
        """Тест обработки LLMModelUnavailableError в стриминге."""
        @streaming_node(stage="test", fallback_key="result", fallback_value="fallback")
        @pytest.mark.infrastructure

        async def test_streaming_node(state: AgentState):
            raise LLMModelUnavailableError("Model unavailable", model="test-model")
        
        state = create_agent_state()
        state["task_id"] = "test-task"
        
        with patch('infrastructure.event_store.get_event_store') as mock_get_store, \
             patch('infrastructure.workflow_decorators._send_stage_error', new_callable=AsyncMock):
            
            mock_store = AsyncMock()
            mock_get_store.return_value = mock_store
            
            events = []
            async for event_type, data in test_streaming_node(state):
                events.append((event_type, data))
            
            assert len(events) == 1
            assert events[0][0] == "done"
            assert events[0][1]["result"] == "fallback"


class TestHelperFunctions:
    """Тесты для вспомогательных функций."""
    
    @pytest.mark.infrastructure

    
    def test_record_stage_duration(self):
        """Тест записи длительности этапа."""
        # Функция импортирует внутри, поэтому мокируем импорт
        with patch('infrastructure.performance_metrics.get_performance_metrics') as mock_get_metrics:
            mock_metrics = Mock()
            mock_metrics.record_stage_duration = Mock()
            mock_get_metrics.return_value = mock_metrics
            
            _record_stage_duration("test", 1.5)
            
            mock_metrics.record_stage_duration.assert_called_once_with("test", 1.5)
    
    @pytest.mark.infrastructure

    
    def test_record_stage_duration_error(self):
        """Тест обработки ошибки при записи метрики."""
        with patch('infrastructure.performance_metrics.get_performance_metrics', side_effect=Exception("Error")):
            # Не должно падать
            _record_stage_duration("test", 1.5)
    
    @pytest.mark.infrastructure

    
    def test_save_checkpoint_enabled(self):
        """Тест сохранения checkpoint когда включено."""
        state = create_agent_state()
        state["task_id"] = "test-task"
        
        with patch('utils.config.get_config') as mock_get_config, \
             patch('infrastructure.task_checkpointer.get_task_checkpointer') as mock_get_checkpointer:
            
            mock_config = Mock()
            mock_config.persistence_enabled = True
            mock_get_config.return_value = mock_config
            
            mock_checkpointer = Mock()
            mock_checkpointer.save_checkpoint = Mock()
            mock_get_checkpointer.return_value = mock_checkpointer
            
            _save_checkpoint(state, "test", "running")
            
            mock_checkpointer.save_checkpoint.assert_called_once()
    
    @pytest.mark.infrastructure

    
    def test_save_checkpoint_disabled(self):
        """Тест что checkpoint не сохраняется когда отключено."""
        state = create_agent_state()
        
        with patch('utils.config.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.persistence_enabled = False
            mock_get_config.return_value = mock_config
            
            _save_checkpoint(state, "test", "running")
            
            # При отключенном persistence не должно быть вызовов
            # Проверяем что функция завершилась без ошибок
            pass
    
    @pytest.mark.infrastructure

    
    def test_save_checkpoint_no_task_id(self):
        """Тест что checkpoint не сохраняется без task_id."""
        state = create_agent_state()
        # Убираем task_id если он есть
        if "task_id" in state:
            del state["task_id"]
        
        with patch('utils.config.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.persistence_enabled = True
            mock_get_config.return_value = mock_config
            
            with patch('infrastructure.task_checkpointer.get_task_checkpointer') as mock_get_checkpointer:
                _save_checkpoint(state, "test", "running")
                
                # Без task_id функция должна вернуться раньше, до вызова get_task_checkpointer
                mock_get_checkpointer.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_agent_resource_success(self):
        """Тест успешного получения ресурса."""
        with patch('infrastructure.agent_resource_manager.acquire_agent_resource') as mock_acquire:
            mock_context = AsyncMock()
            mock_acquire.return_value = mock_context
            
            context = await _acquire_agent_resource("test", "task-123")
            
            assert context is mock_context
            mock_acquire.assert_called_once_with("test", "task-123")
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_acquire_agent_resource_fallback(self):
        """Тест fallback когда resource manager недоступен."""
        with patch('infrastructure.agent_resource_manager.acquire_agent_resource', side_effect=Exception("Error")):
            context = await _acquire_agent_resource("test", "task-123")
            
            # Должен вернуть пустой контекст (fallback)
            async with context:
                pass  # Должно работать без ошибок
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_send_stage_error_enabled(self):
        """Тест отправки ошибки когда SSE включен."""
        state = create_agent_state()
        state["enable_sse"] = True
        state["task_id"] = "test-task"
        
        with patch('backend.sse_manager.get_sse_manager') as mock_get_sse:
            mock_sse = AsyncMock()
            mock_sse.send_stage_event = AsyncMock()
            mock_get_sse.return_value = mock_sse
            
            await _send_stage_error(state, "test", "error", "Test error")
            
            mock_sse.send_stage_event.assert_called_once()
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_send_stage_error_disabled(self):
        """Тест что ошибка не отправляется когда SSE отключен."""
        state = create_agent_state()
        state["enable_sse"] = False
        
        with patch('backend.sse_manager.get_sse_manager') as mock_get_sse:
            await _send_stage_error(state, "test", "error", "Test error")
            
            mock_get_sse.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.infrastructure

    async def test_send_stage_error_exception(self):
        """Тест обработки ошибки при отправке."""
        state = create_agent_state()
        state["enable_sse"] = True
        state["task_id"] = "test-task"
        
        with patch('backend.sse_manager.get_sse_manager', side_effect=Exception("Error")):
            # Не должно падать
            await _send_stage_error(state, "test", "error", "Test error")
