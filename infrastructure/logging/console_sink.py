"""ConsoleLoggerSink - читаемый вывод логов в консоль."""
import sys
from typing import Optional
from datetime import datetime

from infrastructure.logging.models import LogEvent, LogLevel
from infrastructure.logging.sink import LoggerSink


class ConsoleLoggerSink(LoggerSink):
    """Sink для вывода логов в консоль.
    
    Особенности:
    - Читаемый формат для локальной отладки
    - Эмодзи для разных уровней
    - Цветовой вывод (опционально)
    - Компактный формат для быстрого просмотра
    """
    
    # Эмодзи для уровней логирования
    EMOJI_MAP = {
        LogLevel.DEBUG: "🔍",
        LogLevel.INFO: "ℹ️",
        LogLevel.WARNING: "⚠️",
        LogLevel.ERROR: "❌",
    }
    
    # ANSI коды цветов (для терминалов с поддержкой)
    COLORS = {
        LogLevel.DEBUG: "\033[36m",  # Cyan
        LogLevel.INFO: "\033[32m",   # Green
        LogLevel.WARNING: "\033[33m", # Yellow
        LogLevel.ERROR: "\033[31m",   # Red
    }
    RESET = "\033[0m"
    
    def __init__(self, use_colors: bool = True, stream=None) -> None:
        """Инициализация ConsoleLoggerSink.
        
        Args:
            use_colors: Использовать ли цветной вывод
            stream: Поток для вывода (по умолчанию sys.stdout)
        """
        self.use_colors = use_colors and stream is None or hasattr(stream, 'isatty') and stream.isatty()
        self.stream = stream or sys.stdout
    
    def _format_event(self, event: LogEvent) -> str:
        """Форматирует событие для вывода в консоль.
        
        Args:
            event: Событие для форматирования
            
        Returns:
            Отформатированная строка
        """
        emoji = self.EMOJI_MAP.get(event.level, "📝")
        
        # Базовые части сообщения
        parts = [emoji]
        
        # Время (только время, не дата для компактности)
        # ИСПРАВЛЕНИЕ: Конвертируем UTC время в локальный часовой пояс для удобства
        local_time = event.timestamp.astimezone()
        time_str = local_time.strftime("%H:%M:%S")
        parts.append(f"[{time_str}]")
        
        # Уровень
        level_str = event.level.value
        if self.use_colors:
            color = self.COLORS.get(event.level, "")
            level_str = f"{color}{level_str}{self.RESET}"
        parts.append(f"{level_str}")
        
        # Источник и этап
        source_stage = []
        if event.source.value != "system":
            source_stage.append(event.source.value)
        if event.stage:
            source_stage.append(event.stage.value)
        if source_stage:
            parts.append(f"[{':'.join(source_stage)}]")
        
        # Задача и итерация (если есть)
        if event.task_id:
            task_short = event.task_id[:8] if len(event.task_id) > 8 else event.task_id
            parts.append(f"[task:{task_short}]")
        if event.iteration is not None:
            parts.append(f"[iter:{event.iteration}]")
        
        # Сообщение
        parts.append(event.message)
        
        # Payload (если есть, кратко)
        if event.payload:
            payload_str = str(event.payload)
            if len(payload_str) > 100:
                payload_str = payload_str[:97] + "..."
            parts.append(f"| {payload_str}")
        
        return " ".join(parts)
    
    def emit(self, event: LogEvent) -> None:
        """Выводит событие в консоль.
        
        Args:
            event: Событие для вывода
        """
        try:
            formatted = self._format_event(event)
            self.stream.write(formatted + "\n")
            self.stream.flush()
        except Exception as e:
            # Используем sys.stderr чтобы избежать рекурсии при логировании ошибок логирования
            sys.stderr.write(f"⚠️ ConsoleLoggerSink: ошибка вывода события: {e}\n")
    
    def flush(self) -> None:
        """Сбрасывает буфер потока."""
        try:
            self.stream.flush()
        except Exception as e:
            # Используем sys.stderr чтобы избежать рекурсии при логировании ошибок логирования
            sys.stderr.write(f"⚠️ ConsoleLoggerSink: ошибка flush: {e}\n")
    
    def close(self) -> None:
        """Закрывает sink (для консоли ничего не делаем)."""
        self.flush()