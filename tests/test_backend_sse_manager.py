"""Тесты для SSE manager."""
import pytest
from unittest.mock import Mock, patch
from backend.sse_manager import SSEManager, get_sse_manager


class TestSendEvent:
    """Тесты для send_event."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_send_event_basic(self):
        """Тест базовой отправки события."""
        event = await SSEManager.send_event(
            event_type="test",
            data={"message": "test message"}
        )
        
        assert "id:" in event
        assert "event: test" in event
        assert "data:" in event
        assert "test message" in event
        assert event.endswith("\n\n")
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_send_event_with_custom_id(self):
        """Тест отправки события с кастомным ID."""
        custom_id = "custom-event-id-123"
        event = await SSEManager.send_event(
            event_type="test",
            data={"message": "test"},
            event_id=custom_id
        )
        
        assert f"id: {custom_id}" in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_send_event_adds_timestamp(self):
        """Тест что событие содержит timestamp."""
        event = await SSEManager.send_event(
            event_type="test",
            data={"message": "test"}
        )
        
        assert '"timestamp"' in event


class TestStreamStageStart:
    """Тесты для stream_stage_start."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_start_basic(self):
        """Тест базового события начала этапа."""
        event = await SSEManager.stream_stage_start(
            stage="coding",
            message="Генерирую код"
        )
        
        assert "event: stage_start" in event
        assert '"stage": "coding"' in event
        assert '"status": "start"' in event
        assert "Генерирую код" in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_start_with_metadata(self):
        """Тест события начала этапа с метаданными."""
        event = await SSEManager.stream_stage_start(
            stage="planning",
            message="Создаю план",
            metadata={"complexity": "medium"}
        )
        
        assert '"metadata"' in event
        assert '"complexity": "medium"' in event


class TestStreamStageProgress:
    """Тесты для stream_stage_progress."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_progress_basic(self):
        """Тест базового события прогресса."""
        event = await SSEManager.stream_stage_progress(
            stage="coding",
            progress=0.5,
            message="50% готово"
        )
        
        assert "event: stage_progress" in event
        assert '"progress": 0.5' in event
        assert '"status": "progress"' in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_progress_clamps_values(self):
        """Тест что прогресс ограничен 0.0-1.0."""
        event1 = await SSEManager.stream_stage_progress(
            stage="coding",
            progress=1.5  # Превышает максимум
        )
        assert '"progress": 1.0' in event1
        
        event2 = await SSEManager.stream_stage_progress(
            stage="coding",
            progress=-0.5  # Ниже минимума
        )
        assert '"progress": 0.0' in event2


class TestStreamStageEnd:
    """Тесты для stream_stage_end."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_end_basic(self):
        """Тест базового события завершения этапа."""
        event = await SSEManager.stream_stage_end(
            stage="coding",
            message="Код сгенерирован"
        )
        
        assert "event: stage_end" in event
        assert '"status": "end"' in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_stage_end_with_result(self):
        """Тест события завершения с результатом."""
        result = {"code": "def hello(): pass"}
        event = await SSEManager.stream_stage_end(
            stage="coding",
            message="Код готов",
            result=result
        )
        
        assert '"result"' in event
        assert "def hello" in event


class TestStreamError:
    """Тесты для stream_error."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_error_basic(self):
        """Тест базового события ошибки."""
        event = await SSEManager.stream_error(
            stage="coding",
            error_message="Ошибка генерации"
        )
        
        assert "event: error" in event
        assert '"status": "error"' in event
        assert "Ошибка генерации" in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_error_with_details(self):
        """Тест события ошибки с деталями."""
        error_details = {"type": "SyntaxError", "line": 10}
        event = await SSEManager.stream_error(
            stage="coding",
            error_message="Синтаксическая ошибка",
            error_details=error_details
        )
        
        assert '"error_details"' in event
        assert '"type": "SyntaxError"' in event


class TestStreamCodeChunk:
    """Тесты для stream_code_chunk."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_code_chunk_basic(self):
        """Тест базового события чанка кода."""
        event = await SSEManager.stream_code_chunk(
            chunk="def hello():\n    pass",
            is_final=False
        )
        
        assert "event: code_chunk" in event
        assert '"chunk":' in event
        assert "def hello" in event
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_code_chunk_final(self):
        """Тест финального чанка кода."""
        event = await SSEManager.stream_code_chunk(
            chunk="def hello():\n    return 'world'",
            is_final=True
        )
        
        assert '"is_final": true' in event


class TestStreamFinalResult:
    """Тесты для stream_final_result."""
    
    @pytest.mark.asyncio
    @pytest.mark.backend

    async def test_stream_final_result_basic(self):
        """Тест базового финального результата."""
        results = {"code": "def hello(): pass"}
        metrics = {"overall": 1.5}
        
        event = await SSEManager.stream_final_result(
            task_id="test-task-123",
            results=results,
            metrics=metrics
        )
        
        assert "event: complete" in event
        assert '"task_id": "test-task-123"' in event
        assert '"status": "complete"' in event
        assert '"results"' in event
        assert '"metrics"' in event


class TestGetSSEManager:
    """Тесты для get_sse_manager."""
    
    @pytest.mark.backend

    
    def test_get_sse_manager_returns_singleton(self):
        """Тест что get_sse_manager возвращает singleton."""
        manager1 = get_sse_manager()
        manager2 = get_sse_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, SSEManager)
