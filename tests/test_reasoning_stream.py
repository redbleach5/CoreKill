"""Тесты для модуля стриминга рассуждений."""
import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from infrastructure.reasoning_stream import (
    ReasoningStreamManager,
    ReasoningStreamConfig,
    ThinkingChunk,
    ThinkingStatus,
    get_reasoning_stream_manager,
    reset_reasoning_stream_manager,
)


class TestThinkingChunk:
    """Тесты для ThinkingChunk dataclass."""
    
    def test_create_chunk(self):
        """Тест создания чанка."""
        chunk = ThinkingChunk(
            content="Думаю о задаче...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=500,
            total_chars=100
        )
        
        assert chunk.content == "Думаю о задаче..."
        assert chunk.status == ThinkingStatus.IN_PROGRESS
        assert chunk.stage == "coding"
        assert chunk.elapsed_ms == 500
        assert chunk.total_chars == 100


class TestReasoningStreamConfig:
    """Тесты для конфигурации."""
    
    def test_default_config(self):
        """Тест значений по умолчанию."""
        config = ReasoningStreamConfig()
        
        assert config.enabled is True
        assert config.chunk_size == 100
        assert config.debounce_ms == 50
        assert config.max_thinking_time_ms == 120_000
        assert config.show_summary_only is False
    
    def test_custom_config(self):
        """Тест кастомной конфигурации."""
        config = ReasoningStreamConfig(
            enabled=False,
            chunk_size=200,
            debounce_ms=100
        )
        
        assert config.enabled is False
        assert config.chunk_size == 200
        assert config.debounce_ms == 100


class TestReasoningStreamManager:
    """Тесты для ReasoningStreamManager."""
    
    def setup_method(self):
        """Сброс singleton перед каждым тестом."""
        reset_reasoning_stream_manager()
    
    def test_create_manager(self):
        """Тест создания менеджера."""
        manager = ReasoningStreamManager()
        
        assert manager.config is not None
        assert manager._interrupted is False
    
    def test_interrupt(self):
        """Тест прерывания стриминга."""
        manager = ReasoningStreamManager()
        
        assert manager._interrupted is False
        manager.interrupt()
        assert manager._interrupted is True
    
    def test_reset(self):
        """Тест сброса состояния."""
        manager = ReasoningStreamManager()
        manager.interrupt()
        manager._current_stage = "coding"
        
        manager.reset()
        
        assert manager._interrupted is False
        assert manager._current_stage is None
    
    @pytest.mark.asyncio
    async def test_create_thinking_event_started(self):
        """Тест создания SSE события начала."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="",
            status=ThinkingStatus.STARTED,
            stage="coding",
            elapsed_ms=0,
            total_chars=500
        )
        
        event = await manager.create_thinking_event(chunk)
        
        assert "event: thinking_started" in event
        assert '"stage": "coding"' in event
        assert '"status": "started"' in event
        assert '"total_chars": 500' in event
    
    @pytest.mark.asyncio
    async def test_create_thinking_event_in_progress(self):
        """Тест создания SSE события прогресса."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="Анализирую код...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="intent",
            elapsed_ms=150,
            total_chars=50
        )
        
        event = await manager.create_thinking_event(chunk)
        
        assert "event: thinking_in_progress" in event
        assert '"content": "Анализирую код..."' in event
        assert '"elapsed_ms": 150' in event
    
    @pytest.mark.asyncio
    async def test_create_thinking_event_completed(self):
        """Тест создания SSE события завершения."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="Полное рассуждение о задаче",
            status=ThinkingStatus.COMPLETED,
            stage="planning",
            elapsed_ms=2000,
            total_chars=100
        )
        
        event = await manager.create_thinking_event(chunk)
        
        assert "event: thinking_completed" in event
        assert '"summary"' in event  # Должен быть summary
    
    @pytest.mark.asyncio
    async def test_stream_thinking_content_disabled(self):
        """Тест что стриминг не работает когда отключен."""
        config = ReasoningStreamConfig(enabled=False)
        manager = ReasoningStreamManager(config)
        
        events = []
        async for event in manager.stream_thinking_content(
            thinking="Рассуждаю...",
            stage="coding",
            start_time=datetime.now()
        ):
            events.append(event)
        
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_stream_thinking_content_empty(self):
        """Тест пустого thinking."""
        manager = ReasoningStreamManager()
        
        events = []
        async for event in manager.stream_thinking_content(
            thinking="",
            stage="coding",
            start_time=datetime.now()
        ):
            events.append(event)
        
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_stream_thinking_content_chunks(self):
        """Тест что thinking разбивается на чанки."""
        config = ReasoningStreamConfig(
            enabled=True,
            chunk_size=10,  # Маленькие чанки для теста
            debounce_ms=1   # Минимальная задержка для быстрого теста
        )
        manager = ReasoningStreamManager(config)
        
        thinking = "Это длинное рассуждение для теста разбиения на чанки"
        
        events = []
        async for event in manager.stream_thinking_content(
            thinking=thinking,
            stage="coding",
            start_time=datetime.now()
        ):
            events.append(event)
        
        # Должен быть started + несколько in_progress + completed
        assert len(events) >= 3
        
        # Проверяем первое событие - started
        assert "thinking_started" in events[0]
        
        # Проверяем последнее событие - completed
        assert "thinking_completed" in events[-1]
    
    @pytest.mark.asyncio
    async def test_stream_thinking_interrupt(self):
        """Тест прерывания стриминга."""
        config = ReasoningStreamConfig(
            enabled=True,
            chunk_size=5,
            debounce_ms=1
        )
        manager = ReasoningStreamManager(config)
        
        thinking = "Очень длинное рассуждение " * 10
        
        events = []
        count = 0
        async for event in manager.stream_thinking_content(
            thinking=thinking,
            stage="coding",
            start_time=datetime.now()
        ):
            events.append(event)
            count += 1
            if count == 3:  # Прерываем после 3 событий
                manager.interrupt()
        
        # Последнее событие должно быть interrupted
        assert "thinking_interrupted" in events[-1]
        assert "прервано пользователем" in events[-1]
    
    @pytest.mark.asyncio
    async def test_process_response_with_thinking(self):
        """Тест обработки ответа с <think> блоком."""
        config = ReasoningStreamConfig(
            enabled=True,
            chunk_size=50,
            debounce_ms=1
        )
        manager = ReasoningStreamManager(config)
        
        response = """<think>
Анализирую задачу...
Шаг 1: понять требования
Шаг 2: написать код
</think>

def hello():
    print("Hello!")"""
        
        events = []
        async for event in manager.process_response_with_thinking(
            response=response,
            stage="coding"
        ):
            events.append(event)
        
        # Должны быть события для thinking
        assert len(events) >= 3
        assert "thinking_started" in events[0]
        assert "thinking_completed" in events[-1]
    
    @pytest.mark.asyncio
    async def test_process_response_without_thinking(self):
        """Тест обработки ответа без <think> блока."""
        manager = ReasoningStreamManager()
        
        response = "def hello(): pass"
        
        events = []
        async for event in manager.process_response_with_thinking(
            response=response,
            stage="coding"
        ):
            events.append(event)
        
        # Не должно быть событий
        assert len(events) == 0


class TestSingleton:
    """Тесты для singleton паттерна."""
    
    def setup_method(self):
        """Сброс singleton перед каждым тестом."""
        reset_reasoning_stream_manager()
    
    def test_get_singleton(self):
        """Тест получения singleton."""
        manager1 = get_reasoning_stream_manager()
        manager2 = get_reasoning_stream_manager()
        
        assert manager1 is manager2
    
    def test_reset_singleton(self):
        """Тест сброса singleton."""
        manager1 = get_reasoning_stream_manager()
        reset_reasoning_stream_manager()
        manager2 = get_reasoning_stream_manager()
        
        assert manager1 is not manager2
    
    @patch('infrastructure.reasoning_stream._load_config_from_toml')
    def test_config_from_toml(self, mock_load):
        """Тест загрузки конфига из TOML."""
        mock_load.return_value = ReasoningStreamConfig(
            enabled=True,
            chunk_size=200
        )
        
        reset_reasoning_stream_manager()
        manager = get_reasoning_stream_manager()
        
        assert manager.config.chunk_size == 200
        mock_load.assert_called_once()


class TestSSEEventFormat:
    """Тесты для формата SSE событий."""
    
    @pytest.mark.asyncio
    async def test_event_has_required_fields(self):
        """Тест что событие содержит все обязательные поля."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="test",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=100,
            total_chars=50
        )
        
        event = await manager.create_thinking_event(chunk)
        
        # Проверяем структуру SSE
        assert event.startswith("id: ")
        assert "\nevent: " in event
        assert "\ndata: " in event
        assert event.endswith("\n\n")
    
    @pytest.mark.asyncio
    async def test_event_data_is_valid_json(self):
        """Тест что data - валидный JSON."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="тест с юникодом 🧠",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=100,
            total_chars=50
        )
        
        event = await manager.create_thinking_event(chunk)
        
        # Извлекаем data часть
        for line in event.split("\n"):
            if line.startswith("data: "):
                json_str = line[6:]  # Убираем "data: "
                data = json.loads(json_str)
                
                assert data["stage"] == "coding"
                assert data["content"] == "тест с юникодом 🧠"
                assert "timestamp" in data
                break
        else:
            pytest.fail("data line not found in event")
