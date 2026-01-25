"""Тесты для SSE helpers."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from backend.sse_helpers import (
    send_stage_events,
    send_greeting_response,
    send_error_response
)


class TestSendStageEvents:
    """Тесты для send_stage_events."""
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_stage_start')
    @patch('backend.sse_helpers.SSEManager.stream_stage_end')
    @patch('backend.sse_helpers.ui_sleep')
    @pytest.mark.backend

    async def test_send_stage_events_basic(
        self,
        mock_sleep,
        mock_end,
        mock_start
    ):
        """Тест базовой отправки событий этапа."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        mock_sleep.return_value = None
        
        events = []
        async for event in send_stage_events(
            stage="coding",
            message="Генерирую код"
        ):
            events.append(event)
        
        assert len(events) == 2
        assert "stage_start" in events[0]
        assert "stage_end" in events[1]
        mock_start.assert_called_once()
        mock_end.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_stage_start')
    @patch('backend.sse_helpers.SSEManager.stream_stage_end')
    @patch('backend.sse_helpers.ui_sleep')
    @pytest.mark.backend

    async def test_send_stage_events_with_result(
        self,
        mock_sleep,
        mock_end,
        mock_start
    ):
        """Тест отправки событий с результатом."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        mock_sleep.return_value = None
        
        result = {"code": "def hello(): pass"}
        events = []
        async for event in send_stage_events(
            stage="coding",
            message="Код готов",
            result=result
        ):
            events.append(event)
        
        assert len(events) == 2
        # Проверяем что result передан в stream_stage_end
        mock_end.assert_called_once()
        call_args = mock_end.call_args
        assert call_args[1]["result"] == result


class TestSendGreetingResponse:
    """Тесты для send_greeting_response."""
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_stage_start')
    @patch('backend.sse_helpers.SSEManager.stream_stage_end')
    @patch('backend.sse_helpers.SSEManager.stream_final_result')
    @patch('backend.sse_helpers.ui_sleep')
    @pytest.mark.backend

    async def test_send_greeting_response_basic(
        self,
        mock_sleep,
        mock_final,
        mock_end,
        mock_start
    ):
        """Тест базовой отправки greeting ответа."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        mock_final.return_value = "event: complete\n\n"
        mock_sleep.return_value = None
        
        events = []
        async for event in send_greeting_response(
            task_id="test-123",
            greeting_message="Привет! Как дела?"
        ):
            events.append(event)
        
        assert len(events) == 4  # stage_start, stage_end (intent), stage_end (greeting), final_result
        mock_start.assert_called()
        assert mock_end.call_count == 2
        mock_final.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_stage_start')
    @patch('backend.sse_helpers.SSEManager.stream_stage_end')
    @patch('backend.sse_helpers.SSEManager.stream_final_result')
    @patch('backend.sse_helpers.ui_sleep')
    @pytest.mark.backend

    async def test_send_greeting_response_with_task(
        self,
        mock_sleep,
        mock_final,
        mock_end,
        mock_start
    ):
        """Тест greeting ответа с задачей."""
        mock_start.return_value = "event: stage_start\n\n"
        mock_end.return_value = "event: stage_end\n\n"
        mock_final.return_value = "event: complete\n\n"
        mock_sleep.return_value = None
        
        events = []
        async for event in send_greeting_response(
            task_id="test-123",
            greeting_message="Привет!",
            task="привет"
        ):
            events.append(event)
        
        assert len(events) == 4
        # Проверяем что task включен в results
        mock_final.assert_called_once()
        call_args = mock_final.call_args
        assert "task" in call_args[1]["results"]


class TestSendErrorResponse:
    """Тесты для send_error_response."""
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_error')
    @pytest.mark.backend

    async def test_send_error_response_basic(self, mock_stream_error):
        """Тест базовой отправки ошибки."""
        mock_stream_error.return_value = "event: error\n\n"
        
        event = await send_error_response(
            stage="coding",
            error_message="Ошибка генерации"
        )
        
        assert "error" in event
        mock_stream_error.assert_called_once()
        call_args = mock_stream_error.call_args
        assert call_args[1]["stage"] == "coding"
        assert call_args[1]["error_message"] == "Ошибка генерации"
    
    @pytest.mark.asyncio
    @patch('backend.sse_helpers.SSEManager.stream_error')
    @pytest.mark.backend

    async def test_send_error_response_with_details(self, mock_stream_error):
        """Тест отправки ошибки с деталями."""
        mock_stream_error.return_value = "event: error\n\n"
        
        error_details = {"type": "SyntaxError", "line": 10}
        event = await send_error_response(
            stage="coding",
            error_message="Синтаксическая ошибка",
            error_details=error_details
        )
        
        mock_stream_error.assert_called_once()
        call_args = mock_stream_error.call_args
        assert call_args[1]["error_details"] == error_details
