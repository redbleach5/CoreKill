"""Тесты для infrastructure/debug_events.py (Phase 7)."""

import pytest
import time
from unittest.mock import MagicMock, patch

from infrastructure.debug_events import (
    LogLevel,
    LogEntry,
    ToolCall,
    DebugEventEmitter,
    get_debug_emitter,
    debug_log,
    track_tool_call
)


class TestLogLevel:
    """Тесты для LogLevel enum."""
    
    def test_values(self):
        """Проверяет значения enum."""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"


class TestLogEntry:
    """Тесты для LogEntry dataclass."""
    
    def test_creation(self):
        """Проверяет создание записи лога."""
        entry = LogEntry(
            timestamp="2026-01-20T12:00:00",
            level=LogLevel.INFO,
            stage="coding",
            message="Test message"
        )
        assert entry.timestamp == "2026-01-20T12:00:00"
        assert entry.level == LogLevel.INFO
        assert entry.stage == "coding"
        assert entry.message == "Test message"
        assert entry.details == {}
    
    def test_to_dict(self):
        """Проверяет сериализацию в словарь."""
        entry = LogEntry(
            timestamp="2026-01-20T12:00:00",
            level=LogLevel.WARNING,
            stage="validation",
            message="Warning!",
            details={"key": "value"}
        )
        result = entry.to_dict()
        
        assert result["timestamp"] == "2026-01-20T12:00:00"
        assert result["level"] == "warning"
        assert result["stage"] == "validation"
        assert result["message"] == "Warning!"
        assert result["details"] == {"key": "value"}


class TestToolCall:
    """Тесты для ToolCall dataclass."""
    
    def test_creation(self):
        """Проверяет создание записи вызова."""
        call = ToolCall(
            id="abc123",
            type="llm",
            name="generate",
            input_preview="test prompt",
            start_time=time.time()
        )
        assert call.id == "abc123"
        assert call.type == "llm"
        assert call.status == "running"
        assert call.tokens_in == 0
    
    def test_to_dict_truncates_preview(self):
        """Проверяет обрезку превью."""
        long_input = "x" * 1000
        call = ToolCall(
            id="test",
            type="llm",
            name="test",
            input_preview=long_input,
            start_time=time.time()
        )
        result = call.to_dict()
        assert len(result["input_preview"]) == 500


class TestDebugEventEmitter:
    """Тесты для DebugEventEmitter."""
    
    def test_singleton(self):
        """Проверяет singleton паттерн."""
        emitter1 = DebugEventEmitter()
        emitter2 = DebugEventEmitter()
        assert emitter1 is emitter2
    
    def test_enabled_by_default(self):
        """Проверяет что эмиттер включен по умолчанию."""
        emitter = get_debug_emitter()
        assert emitter.enabled is True
    
    def test_log_without_callback(self):
        """Проверяет логирование без callback (не должно падать)."""
        emitter = get_debug_emitter()
        emitter._sse_callback = None
        # Не должно бросать исключение
        emitter.log("test", "Test message")
    
    def test_log_with_callback(self):
        """Проверяет вызов callback при логировании."""
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        emitter.log("coding", "Test message", LogLevel.INFO)
        
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "log"
        assert args[1]["stage"] == "coding"
        assert args[1]["message"] == "Test message"
        
        # Cleanup
        emitter._sse_callback = None
    
    def test_log_filtering_by_level(self):
        """Проверяет фильтрацию логов по уровню."""
        emitter = get_debug_emitter()
        emitter._log_level = LogLevel.WARNING
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        # DEBUG и INFO не должны вызывать callback
        emitter.log("test", "Debug", LogLevel.DEBUG)
        emitter.log("test", "Info", LogLevel.INFO)
        assert callback.call_count == 0
        
        # WARNING и ERROR должны
        emitter.log("test", "Warning", LogLevel.WARNING)
        emitter.log("test", "Error", LogLevel.ERROR)
        assert callback.call_count == 2
        
        # Cleanup
        emitter._sse_callback = None
        emitter._log_level = LogLevel.INFO
    
    def test_tool_call_lifecycle(self):
        """Проверяет lifecycle tool call."""
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        # Start
        emitter.tool_call_start("call-1", "llm", "generate", "prompt")
        assert "call-1" in emitter._tool_calls
        
        # End
        emitter.tool_call_end("call-1", "success", "output", 100)
        
        call = emitter._tool_calls.get("call-1")
        assert call is not None
        assert call.status == "success"
        assert call.tokens_out == 100
        
        # Cleanup
        emitter._sse_callback = None
        emitter._tool_calls.clear()
    
    def test_get_logs(self):
        """Проверяет получение логов."""
        emitter = get_debug_emitter()
        emitter._logs.clear()
        
        # Добавляем логи напрямую
        for i in range(10):
            entry = LogEntry(
                timestamp=f"2026-01-20T12:00:{i:02d}",
                level=LogLevel.INFO,
                stage="test",
                message=f"Log {i}"
            )
            emitter._logs.append(entry)
        
        logs = emitter.get_logs(limit=5)
        assert len(logs) == 5
        assert logs[-1]["message"] == "Log 9"
        
        # Cleanup
        emitter._logs.clear()
    
    def test_clear(self):
        """Проверяет очистку данных."""
        emitter = get_debug_emitter()
        
        # Добавляем данные
        emitter._logs.append(LogEntry(
            timestamp="test", level=LogLevel.INFO, stage="test", message="test"
        ))
        emitter._tool_calls["test"] = ToolCall(
            id="test", type="llm", name="test", input_preview="test", start_time=0
        )
        
        emitter.clear()
        
        assert len(emitter._logs) == 0
        assert len(emitter._tool_calls) == 0


class TestDebugLog:
    """Тесты для функции debug_log."""
    
    def test_debug_log_shortcut(self):
        """Проверяет shortcut функцию."""
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        debug_log("coding", "Test message", LogLevel.INFO, key="value")
        
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[1]["details"] == {"key": "value"}
        
        # Cleanup
        emitter._sse_callback = None


class TestTrackToolCallDecorator:
    """Тесты для декоратора track_tool_call."""
    
    def test_sync_function(self):
        """Проверяет декоратор с синхронной функцией."""
        @track_tool_call("validation", "pytest")
        def validate_code(code: str) -> bool:
            return True
        
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        result = validate_code("test code")
        
        assert result is True
        # Должны быть вызовы start и end
        assert callback.call_count == 2
        
        # Cleanup
        emitter._sse_callback = None
        emitter._tool_calls.clear()
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Проверяет декоратор с асинхронной функцией."""
        @track_tool_call("llm", "generate")
        async def generate(prompt: str) -> str:
            return "result"
        
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        result = await generate("test prompt")
        
        assert result == "result"
        assert callback.call_count == 2
        
        # Cleanup
        emitter._sse_callback = None
        emitter._tool_calls.clear()
    
    def test_error_handling(self):
        """Проверяет обработку ошибок."""
        @track_tool_call("test", "failing")
        def failing_function() -> None:
            raise ValueError("Test error")
        
        emitter = get_debug_emitter()
        callback = MagicMock()
        emitter.set_sse_callback(callback)
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Должен быть вызван end с error статусом
        assert callback.call_count == 2
        end_call = callback.call_args_list[1]
        assert end_call[0][1]["status"] == "error"
        
        # Cleanup
        emitter._sse_callback = None
        emitter._tool_calls.clear()
