"""Конфигурация системы логирования."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from infrastructure.logging.models import LogLevel


@dataclass
class LoggingConfig:
    """Конфигурация системы логирования.
    
    Атрибуты:
        level: Минимальный уровень логирования
        enable_file: Включить ли запись в файл
        enable_console: Включить ли вывод в консоль
        enable_memory: Включить ли хранение в памяти (для UI)
        log_file: Путь к файлу логов
        max_file_size_mb: Максимальный размер файла в МБ перед ротацией
        file_backup_count: Количество резервных копий файлов
        console_colors: Использовать ли цветной вывод в консоли
        memory_max_events: Максимальное количество событий в памяти
    """
    level: LogLevel = LogLevel.INFO
    enable_file: bool = True
    enable_console: bool = True
    enable_memory: bool = False
    log_file: Path = field(default_factory=lambda: Path("logs/app.jsonl"))
    max_file_size_mb: int = 100
    file_backup_count: int = 5
    console_colors: bool = True
    memory_max_events: int = 1000
    
    @classmethod
    def for_dev(cls) -> 'LoggingConfig':
        """Создаёт конфигурацию для разработки.
        
        Returns:
            Конфигурация с включёнными консолью и файлом, уровень DEBUG
        """
        return cls(
            level=LogLevel.DEBUG,
            enable_file=True,
            enable_console=True,
            enable_memory=False,
            console_colors=True,
        )
    
    @classmethod
    def for_prod(cls) -> 'LoggingConfig':
        """Создаёт конфигурацию для продакшена.
        
        Returns:
            Конфигурация с файлом и памятью, уровень INFO
        """
        return cls(
            level=LogLevel.INFO,
            enable_file=True,
            enable_console=False,
            enable_memory=True,
            console_colors=False,
        )
    
    @classmethod
    def for_ui(cls) -> 'LoggingConfig':
        """Создаёт конфигурацию для UI (с памятью для стриминга).
        
        Returns:
            Конфигурация с включённой памятью для UI стриминга
        """
        return cls(
            level=LogLevel.INFO,
            enable_file=True,
            enable_console=False,
            enable_memory=True,
            console_colors=False,
            memory_max_events=5000,  # Больше для UI
        )