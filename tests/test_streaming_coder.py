"""Тесты для StreamingCoderAgent."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from agents.streaming_coder import StreamingCoderAgent, get_streaming_coder_agent


class TestStreamingCoderAgentInit:
    """Тесты инициализации StreamingCoderAgent."""
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_init_with_model(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест инициализации с явно указанной моделью."""
        mock_llm = Mock()
        mock_create_llm.return_value = mock_llm
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test-model:7b", temperature=0.3)
        
        assert agent.model == "test-model:7b"
        assert agent.temperature == 0.3
        mock_create_llm.assert_called_once_with(
            stage="coding",
            model="test-model:7b",
            temperature=0.3,
            top_p=0.9
        )
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_init_without_model(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест инициализации без модели (автоматический выбор)."""
        mock_router_instance = Mock()
        mock_router_instance.select_model.return_value = Mock(model="auto-selected:7b")
        mock_router.return_value = mock_router_instance
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = StreamingCoderAgent()
        
        assert agent.model == "auto-selected:7b"
        mock_router_instance.select_model.assert_called_once()


class TestStreamingCoderAgentInterrupt:
    """Тесты прерывания генерации."""
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_interrupt(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест прерывания генерации."""
        mock_reasoning_manager = Mock()
        mock_reasoning.return_value = mock_reasoning_manager
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test:7b")
        
        assert agent._interrupted is False
        
        agent.interrupt()
        
        assert agent._interrupted is True
        mock_reasoning_manager.interrupt.assert_called_once()
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_reset(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест сброса состояния."""
        mock_reasoning_manager = Mock()
        mock_reasoning.return_value = mock_reasoning_manager
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test:7b")
        agent._interrupted = True
        
        agent.reset()
        
        assert agent._interrupted is False
        mock_reasoning_manager.reset.assert_called_once()


class TestGenerateCodeStream:
    """Тесты стриминга генерации кода."""
    
    @pytest.mark.asyncio
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    @patch('agents.streaming_coder.get_config')
    async def test_generate_greeting_skipped(
        self, 
        mock_config,
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест что для greeting не генерируется код."""
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test:7b")
        
        events = []
        async for event_type, data in agent.generate_code_stream(
            plan="",
            tests="",
            context="",
            intent_type="greeting"
        ):
            events.append((event_type, data))
        
        assert len(events) == 1
        assert events[0] == ("done", "")
    
    @pytest.mark.asyncio
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    @patch('agents.streaming_coder.get_config')
    async def test_generate_with_thinking(
        self, 
        mock_config,
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест генерации с thinking блоком."""
        mock_config_instance = Mock()
        mock_config_instance.llm_tokens_code = 4096
        mock_config.return_value = mock_config_instance
        
        mock_llm = Mock()
        mock_create_llm.return_value = mock_llm
        
        mock_enhancer_instance = Mock()
        mock_enhancer_instance.enhance_for_coding.return_value = "test prompt"
        mock_enhancer.return_value = mock_enhancer_instance
        
        # Мокаем reasoning manager чтобы возвращал thinking и code
        async def fake_stream(*args, **kwargs):
            yield ("thinking", "sse_event_1")
            yield ("thinking", "sse_event_2")
            yield ("content", "def hello():\n")
            yield ("content", "    pass\n")
            yield ("done", "def hello():\n    pass\n")
        
        mock_reasoning_manager = Mock()
        mock_reasoning_manager.stream_from_llm = fake_stream
        mock_reasoning_manager.reset = Mock()
        mock_reasoning.return_value = mock_reasoning_manager
        
        agent = StreamingCoderAgent(model="test:7b")
        
        events = []
        async for event_type, data in agent.generate_code_stream(
            plan="Create hello function",
            tests="def test_hello(): pass",
            context="",
            intent_type="create",
            user_query="напиши функцию hello"
        ):
            events.append((event_type, data))
        
        # Проверяем что были thinking события
        thinking_events = [e for e in events if e[0] == "thinking"]
        assert len(thinking_events) == 2
        
        # Проверяем что были code_chunk события
        code_events = [e for e in events if e[0] == "code_chunk"]
        assert len(code_events) == 2
        
        # Проверяем финальное событие
        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) == 1
        assert "def hello" in done_events[0][1]


class TestCleanCode:
    """Тесты очистки кода."""
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_clean_code_with_markdown(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест очистки кода от markdown."""
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test:7b")
        
        raw_code = """```python
def hello():
    return "Hello"
```"""
        
        cleaned = agent._clean_code(raw_code)
        
        assert "```" not in cleaned
        assert "def hello" in cleaned
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_clean_code_empty(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест очистки пустого кода."""
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = StreamingCoderAgent(model="test:7b")
        
        assert agent._clean_code("") == ""
        assert agent._clean_code("just text without code") == ""


class TestSyncMethods:
    """Тесты синхронных методов для обратной совместимости."""
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    @patch('agents.coder.CoderAgent')
    def test_sync_generate_code(
        self, 
        mock_coder_agent,
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест синхронной генерации через CoderAgent."""
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        mock_sync_agent = Mock()
        mock_sync_agent.generate_code.return_value = "def test(): pass"
        mock_coder_agent.return_value = mock_sync_agent
        
        agent = StreamingCoderAgent(model="test:7b")
        
        result = agent.generate_code(
            plan="plan",
            tests="tests",
            context="context",
            intent_type="create"
        )
        
        assert result == "def test(): pass"
        mock_sync_agent.generate_code.assert_called_once()


class TestFactory:
    """Тесты factory функции."""
    
    @patch('agents.streaming_coder.get_model_router')
    @patch('agents.streaming_coder.create_llm_for_stage')
    @patch('agents.streaming_coder.get_prompt_enhancer')
    @patch('agents.streaming_coder.get_reasoning_stream_manager')
    def test_get_streaming_coder_agent(
        self, 
        mock_reasoning, 
        mock_enhancer, 
        mock_create_llm, 
        mock_router
    ):
        """Тест factory функции."""
        mock_create_llm.return_value = Mock()
        mock_enhancer.return_value = Mock()
        mock_reasoning.return_value = Mock()
        
        agent = get_streaming_coder_agent(model="custom:7b", temperature=0.2)
        
        assert isinstance(agent, StreamingCoderAgent)
        assert agent.model == "custom:7b"
        assert agent.temperature == 0.2
