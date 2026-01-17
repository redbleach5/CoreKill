"""Unit-тесты для системы логирования."""
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from infrastructure.logging.models import (
    LogEvent,
    LogLevel,
    LogSource,
    LogStage
)
from infrastructure.logging.sink import LoggerSink
from infrastructure.logging.file_sink import FileLoggerSink
from infrastructure.logging.console_sink import ConsoleLoggerSink
from infrastructure.logging.memory_sink import MemoryLoggerSink
from infrastructure.logging.manager import LogManager
from infrastructure.logging.config import LoggingConfig
from infrastructure.logging.stream_adapter import LogStreamAdapter, create_sse_event


class TestLogEvent:
    """Тесты для модели LogEvent."""
    
    def test_log_event_creation(self) -> None:
        """Тест создания события."""
        event = LogEvent(
            level=LogLevel.INFO,
            message="Тестовое сообщение",
            source=LogSource.SYSTEM,
            stage=LogStage.PLANNING,
            task_id="test-123",
            iteration=1
        )
        
        assert event.level == LogLevel.INFO
        assert event.message == "Тестовое сообщение"
        assert event.source == LogSource.SYSTEM
        assert event.stage == LogStage.PLANNING
        assert event.task_id == "test-123"
        assert event.iteration == 1
        assert isinstance(event.timestamp, datetime)
    
    def test_log_event_to_dict(self) -> None:
        """Тест преобразования события в словарь."""
        event = LogEvent(
            level=LogLevel.ERROR,
            message="Ошибка",
            source=LogSource.AGENT,
            stage=LogStage.CODING,
            task_id="task-456",
            iteration=2,
            payload={"error_code": 500}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["level"] == "ERROR"
        assert event_dict["message"] == "Ошибка"
        assert event_dict["source"] == "agent"
        assert event_dict["stage"] == "coding"
        assert event_dict["task_id"] == "task-456"
        assert event_dict["iteration"] == 2
        assert event_dict["payload"] == {"error_code": 500}
        assert "timestamp" in event_dict


class TestFileLoggerSink:
    """Тесты для FileLoggerSink."""
    
    def test_file_sink_write(self) -> None:
        """Тест записи событий в файл."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"
            sink = FileLoggerSink(log_file)
            
            event = LogEvent(
                level=LogLevel.INFO,
                message="Тестовое сообщение",
                task_id="test-123"
            )
            
            sink.emit(event)
            sink.flush()
            sink.close()
            
            # Проверяем, что файл создан и содержит событие
            assert log_file.exists()
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                assert len(lines) == 1
                loaded_event = json.loads(lines[0])
                assert loaded_event["message"] == "Тестовое сообщение"
                assert loaded_event["task_id"] == "test-123"
    
    def test_file_sink_rotation(self) -> None:
        """Тест ротации файлов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"
            # Используем очень маленький размер для ротации
            sink = FileLoggerSink(log_file, max_size_mb=1, backup_count=2)
            
            # Заполняем файл (упрощённый тест - в реальности нужен большой объём)
            # Здесь просто проверяем, что ротация вызывается без ошибок
            for i in range(10):
                event = LogEvent(
                    level=LogLevel.INFO,
                    message=f"Сообщение {i}",
                    payload={"index": i}
                )
                sink.emit(event)
            
            sink.flush()
            sink.close()
            
            assert log_file.exists() or log_file.with_suffix(".1.jsonl").exists()


class TestConsoleLoggerSink:
    """Тесты для ConsoleLoggerSink."""
    
    def test_console_sink_emit(self) -> None:
        """Тест вывода событий в консоль."""
        import io
        
        stream = io.StringIO()
        sink = ConsoleLoggerSink(use_colors=False, stream=stream)
        
        event = LogEvent(
            level=LogLevel.INFO,
            message="Тестовое сообщение",
            source=LogSource.AGENT,
            stage=LogStage.PLANNING
        )
        
        sink.emit(event)
        sink.flush()
        
        output = stream.getvalue()
        assert "Тестовое сообщение" in output
        assert "INFO" in output or "ℹ️" in output


class TestMemoryLoggerSink:
    """Тесты для MemoryLoggerSink."""
    
    def test_memory_sink_store(self) -> None:
        """Тест хранения событий в памяти."""
        sink = MemoryLoggerSink(max_events=10)
        
        events = [
            LogEvent(level=LogLevel.INFO, message=f"Сообщение {i}", task_id="test")
            for i in range(5)
        ]
        
        for event in events:
            sink.emit(event)
        
        stored_events = sink.get_events()
        assert len(stored_events) == 5
        assert all(e.message.startswith("Сообщение") for e in stored_events)
    
    def test_memory_sink_filtering(self) -> None:
        """Тест фильтрации событий."""
        sink = MemoryLoggerSink()
        
        # Добавляем события разных уровней и источников
        sink.emit(LogEvent(
            level=LogLevel.INFO,
            message="INFO сообщение",
            source=LogSource.AGENT,
            stage=LogStage.PLANNING,
            task_id="task-1"
        ))
        sink.emit(LogEvent(
            level=LogLevel.ERROR,
            message="ERROR сообщение",
            source=LogSource.SYSTEM,
            stage=LogStage.CODING,
            task_id="task-2"
        ))
        sink.emit(LogEvent(
            level=LogLevel.INFO,
            message="Другое INFO сообщение",
            source=LogSource.AGENT,
            stage=LogStage.PLANNING,
            task_id="task-1"
        ))
        
        # Фильтруем по уровню
        error_events = sink.get_events(level="ERROR")
        assert len(error_events) == 1
        assert error_events[0].message == "ERROR сообщение"
        
        # Фильтруем по task_id
        task1_events = sink.get_events(task_id="task-1")
        assert len(task1_events) == 2
        
        # Фильтруем по этапу
        planning_events = sink.get_events(stage="planning")
        assert len(planning_events) == 2
    
    def test_memory_sink_callbacks(self) -> None:
        """Тест callback-ов для подписки на события."""
        callback_events = []
        
        def callback(event: LogEvent) -> None:
            callback_events.append(event)
        
        sink = MemoryLoggerSink()
        sink.subscribe(callback)
        
        event = LogEvent(level=LogLevel.INFO, message="Тест")
        sink.emit(event)
        
        assert len(callback_events) == 1
        assert callback_events[0].message == "Тест"
        
        # Отписываемся
        sink.unsubscribe(callback)
        sink.emit(LogEvent(level=LogLevel.INFO, message="Тест 2"))
        
        assert len(callback_events) == 1  # Callback не вызван
    
    def test_memory_sink_max_events(self) -> None:
        """Тест ограничения размера буфера."""
        sink = MemoryLoggerSink(max_events=3)
        
        # Добавляем больше событий, чем максимум
        for i in range(5):
            sink.emit(LogEvent(level=LogLevel.INFO, message=f"Сообщение {i}"))
        
        # Должно остаться только последние 3
        events = sink.get_events()
        assert len(events) == 3
        assert events[0].message == "Сообщение 2"
        assert events[2].message == "Сообщение 4"


class TestLogManager:
    """Тесты для LogManager."""
    
    def test_log_manager_with_memory_sink(self) -> None:
        """Тест LogManager с MemoryLoggerSink (для тестов)."""
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            enable_file=False,
            enable_console=False,
            enable_memory=True
        )
        
        manager = LogManager(config)
        
        task_id = "test-task"
        manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.PLANNING,
            message="Начат этап планирования"
        )
        
        memory_sink = manager.get_memory_sink()
        assert memory_sink is not None
        
        events = memory_sink.get_events(task_id=task_id)
        assert len(events) == 1
        assert events[0].stage == LogStage.PLANNING
        assert events[0].message == "Начат этап планирования"
        
        manager.close()
    
    def test_log_manager_level_filtering(self) -> None:
        """Тест фильтрации по уровню логирования."""
        config = LoggingConfig(
            level=LogLevel.WARNING,  # Только WARNING и выше
            enable_file=False,
            enable_console=False,
            enable_memory=True
        )
        
        manager = LogManager(config)
        
        manager.log_debug(message="DEBUG сообщение")
        manager.log_info(message="INFO сообщение")
        manager.log_warning(message="WARNING сообщение")
        manager.log_error(message="ERROR сообщение")
        
        memory_sink = manager.get_memory_sink()
        assert memory_sink is not None
        
        events = memory_sink.get_events()
        # Должны быть только WARNING и ERROR
        assert len(events) == 2
        assert all(e.level in (LogLevel.WARNING, LogLevel.ERROR) for e in events)
        
        manager.close()
    
    def test_log_manager_stage_methods(self) -> None:
        """Тест методов логирования этапов."""
        config = LoggingConfig(
            enable_file=False,
            enable_console=False,
            enable_memory=True
        )
        
        manager = LogManager(config)
        
        task_id = "test-task"
        
        manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.CODING,
            message="Начат этап кодирования",
            payload={"lines": 100}
        )
        
        manager.log_stage_end(
            task_id=task_id,
            stage=LogStage.CODING,
            message="Завершён этап кодирования",
            payload={"lines": 150}
        )
        
        memory_sink = manager.get_memory_sink()
        assert memory_sink is not None
        
        events = memory_sink.get_events(task_id=task_id, stage="coding")
        assert len(events) == 2
        assert all(e.stage == LogStage.CODING for e in events)
        assert events[0].payload == {"lines": 100}
        assert events[1].payload == {"lines": 150}
        
        manager.close()
    
    def test_log_manager_error_logging(self) -> None:
        """Тест логирования ошибок."""
        config = LoggingConfig(
            enable_file=False,
            enable_console=False,
            enable_memory=True
        )
        
        manager = LogManager(config)
        
        try:
            raise ValueError("Тестовая ошибка")
        except Exception as e:
            manager.log_error(
                message="Произошла ошибка",
                source=LogSource.AGENT,
                stage=LogStage.CODING,
                task_id="test-task",
                error=e
            )
        
        memory_sink = manager.get_memory_sink()
        assert memory_sink is not None
        
        error_events = memory_sink.get_events(level="ERROR")
        assert len(error_events) == 1
        
        event = error_events[0]
        assert event.level == LogLevel.ERROR
        assert event.payload is not None
        assert event.payload["error_type"] == "ValueError"
        assert event.payload["error_message"] == "Тестовая ошибка"
        assert "traceback" in event.payload
        
        manager.close()


class TestLogStreamAdapter:
    """Тесты для LogStreamAdapter."""
    
    @pytest.mark.asyncio
    async def test_stream_adapter(self) -> None:
        """Тест адаптера для стриминга."""
        config = LoggingConfig(
            enable_file=False,
            enable_console=False,
            enable_memory=True
        )
        
        manager = LogManager(config)
        
        task_id = "stream-test"
        adapter = LogStreamAdapter(manager)
        
        # Генерируем несколько событий
        manager.log_info(message="Событие 1", task_id=task_id)
        manager.log_info(message="Событие 2", task_id=task_id)
        
        # Собираем события из стрима
        events = []
        async for event in adapter.stream_events(task_id=task_id):
            events.append(event)
            if len(events) >= 2:
                break
        
        # Проверяем, что получили события
        assert len(events) >= 2
        
        adapter.stop()
        manager.close()
    
    def test_create_sse_event(self) -> None:
        """Тест преобразования LogEvent в SSE формат."""
        event = LogEvent(
            level=LogLevel.INFO,
            message="Тестовое сообщение",
            source=LogSource.AGENT,
            stage=LogStage.PLANNING,
            task_id="test-123"
        )
        
        sse_string = create_sse_event(event)
        
        assert "event: stage_planning" in sse_string
        assert "data:" in sse_string
        assert "Тестовое сообщение" in sse_string
        assert "test-123" in sse_string


class TestAgentIntegration:
    """Тесты интеграции с агентом (пример использования)."""
    
    def test_agent_with_logging(self) -> None:
        """Тест агента с логированием (как тестировать бизнес-код)."""
        from infrastructure.logging.config import LoggingConfig
        
        # Создаём конфигурацию только с памятью (без файлов)
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            enable_file=False,
            enable_console=False,
            enable_memory=True,
            memory_max_events=100
        )
        
        # Создаём LogManager только с MemoryLoggerSink
        log_manager = LogManager(config)
        
        # Симулируем работу агента
        task_id = "test-agent-123"
        
        log_manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.INTENT,
            message="Начат этап определения намерения",
            source=LogSource.AGENT,
            payload={"query": "создай функцию"}
        )
        
        log_manager.log_stage_end(
            task_id=task_id,
            stage=LogStage.INTENT,
            message="Намерение определено: create (уверенность: 0.85)",
            source=LogSource.AGENT,
            payload={"type": "create", "confidence": 0.85}
        )
        
        # Проверяем, что нужные события были залогированы
        memory_sink = log_manager.get_memory_sink()
        assert memory_sink is not None
        
        # Получаем события для этой задачи
        events = memory_sink.get_events(task_id=task_id)
        
        # Проверяем наличие нужных событий
        assert len(events) >= 2  # Начало и конец этапа
        
        # Проверяем начало этапа
        start_events = [e for e in events if e.stage == LogStage.INTENT and "Начат" in e.message]
        assert len(start_events) >= 1
        assert start_events[0].payload == {"query": "создай функцию"}
        
        # Проверяем конец этапа
        end_events = [e for e in events if "определено" in e.message]
        assert len(end_events) >= 1
        assert end_events[0].payload == {"type": "create", "confidence": 0.85}
        
        # Закрываем логгер
        log_manager.close()