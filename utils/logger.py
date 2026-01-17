"""Совместимый интерфейс для системы логирования.

Использует новую систему логирования (infrastructure/logging) 
с сохранением обратной совместимости со старым API.
"""
import logging
from typing import Optional
from pathlib import Path

from infrastructure.logging import LogManager, LoggingConfig
from infrastructure.logging.models import LogLevel, LogSource


# Глобальный LogManager (singleton)
_default_log_manager: Optional[LogManager] = None


def _get_log_manager() -> LogManager:
    """Получает глобальный LogManager.
    
    Автоматически определяет окружение и настраивает конфигурацию:
    - Если переменная окружения UI_MODE=1, использует for_ui()
    - Иначе использует for_dev()
    
    Returns:
        Глобальный экземпляр LogManager
    """
    global _default_log_manager
    if _default_log_manager is None:
        import os
        
        # Проверяем, запущены ли мы в UI режиме
        ui_mode = os.getenv('UI_MODE', '0') == '1'
        
        if ui_mode:
            # Для UI используем конфигурацию с памятью для стриминга
            config = LoggingConfig.for_ui()
        else:
            # Для CLI/обычного использования - конфигурация для разработки
            config = LoggingConfig.for_dev()
        
        # Убеждаемся, что файл логов настроен правильно
        if config.enable_file:
            # Создаём директорию для логов если её нет
            log_dir = config.log_file.parent
            log_dir.mkdir(parents=True, exist_ok=True)
        
        _default_log_manager = LogManager(config)
    return _default_log_manager


class LoggerAdapter:
    """Адаптер для совместимости со стандартным logging.Logger.
    
    Эмулирует интерфейс logging.Logger, но использует новую систему логирования.
    """
    
    def __init__(self, name: str = "cursor_killer") -> None:
        """Инициализация адаптера.
        
        Args:
            name: Имя логгера (используется для совместимости, но не влияет на новую систему)
        """
        self.name = name
        self.level = logging.INFO  # По умолчанию INFO
        
        # Маппинг уровней logging на LogLevel
        self._level_map = {
            logging.DEBUG: LogLevel.DEBUG,
            logging.INFO: LogLevel.INFO,
            logging.WARNING: LogLevel.WARNING,
            logging.ERROR: LogLevel.ERROR,
            logging.CRITICAL: LogLevel.ERROR,  # CRITICAL -> ERROR
        }
    
    def setLevel(self, level: int) -> None:
        """Устанавливает уровень логирования (для совместимости).
        
        Args:
            level: Уровень из logging (DEBUG, INFO, WARNING, ERROR)
        """
        self.level = level
        # Обновляем уровень в LogManager
        log_manager = _get_log_manager()
        log_level = self._level_map.get(level, LogLevel.INFO)
        log_manager.config.level = log_level
    
    def isEnabledFor(self, level: int) -> bool:
        """Проверяет, включён ли данный уровень логирования.
        
        Args:
            level: Уровень для проверки
            
        Returns:
            True если уровень включён
        """
        return level >= self.level
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Логирует INFO сообщение.
        
        Args:
            msg: Сообщение для логирования
            *args: Аргументы для форматирования (не используется, совместимость)
            **kwargs: Дополнительные параметры (stage, task_id, payload и т.п.)
        """
        if self.isEnabledFor(logging.INFO):
            log_manager = _get_log_manager()
            
            # Извлекаем дополнительные параметры из kwargs
            source = kwargs.pop('source', LogSource.SYSTEM)
            stage = kwargs.pop('stage', None)
            task_id = kwargs.pop('task_id', None)
            iteration = kwargs.pop('iteration', None)
            payload = kwargs.pop('payload', None)
            
            log_manager.log_info(
                message=str(msg),
                source=source,
                stage=stage,
                payload=payload,
                task_id=task_id,
                iteration=iteration
            )
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Логирует DEBUG сообщение.
        
        Args:
            msg: Сообщение для логирования
            *args: Аргументы для форматирования (не используется, совместимость)
            **kwargs: Дополнительные параметры
        """
        if self.isEnabledFor(logging.DEBUG):
            log_manager = _get_log_manager()
            
            source = kwargs.pop('source', LogSource.SYSTEM)
            stage = kwargs.pop('stage', None)
            task_id = kwargs.pop('task_id', None)
            iteration = kwargs.pop('iteration', None)
            payload = kwargs.pop('payload', None)
            
            log_manager.log_debug(
                message=str(msg),
                source=source,
                stage=stage,
                payload=payload,
                task_id=task_id,
                iteration=iteration
            )
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Логирует WARNING сообщение.
        
        Args:
            msg: Сообщение для логирования
            *args: Аргументы для форматирования (не используется, совместимость)
            **kwargs: Дополнительные параметры
        """
        if self.isEnabledFor(logging.WARNING):
            log_manager = _get_log_manager()
            
            source = kwargs.pop('source', LogSource.SYSTEM)
            stage = kwargs.pop('stage', None)
            task_id = kwargs.pop('task_id', None)
            iteration = kwargs.pop('iteration', None)
            payload = kwargs.pop('payload', None)
            
            log_manager.log_warning(
                message=str(msg),
                source=source,
                stage=stage,
                payload=payload,
                task_id=task_id,
                iteration=iteration
            )
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Логирует ERROR сообщение.
        
        Args:
            msg: Сообщение для логирования
            *args: Аргументы для форматирования (не используется, совместимость)
            **kwargs: Дополнительные параметры (error для исключения)
        """
        if self.isEnabledFor(logging.ERROR):
            log_manager = _get_log_manager()
            
            source = kwargs.pop('source', LogSource.SYSTEM)
            stage = kwargs.pop('stage', None)
            task_id = kwargs.pop('task_id', None)
            iteration = kwargs.pop('iteration', None)
            payload = kwargs.pop('payload', None)
            error = kwargs.pop('error', None)
            
            log_manager.log_error(
                message=str(msg),
                source=source,
                stage=stage,
                payload=payload,
                task_id=task_id,
                iteration=iteration,
                error=error
            )
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Логирует CRITICAL сообщение (маппится на ERROR).
        
        Args:
            msg: Сообщение для логирования
            *args: Аргументы для форматирования (не используется, совместимость)
            **kwargs: Дополнительные параметры
        """
        self.error(msg, *args, **kwargs)


def setup_logger(
    name: str = "cursor_killer",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console_output: bool = True
) -> LoggerAdapter:
    """Настраивает и возвращает логгер с русским выводом.
    
    Совместимая функция со старым API, но использует новую систему логирования.
    
    Args:
        name: Имя логгера (используется для совместимости)
        level: Уровень логирования (по умолчанию INFO)
        log_file: Опциональный путь к файлу для записи логов
        console_output: Выводить ли логи в консоль
        
    Returns:
        LoggerAdapter совместимый со стандартным logging.Logger
    """
    global _default_log_manager
    
    # Если LogManager уже существует, обновляем только уровень
    if _default_log_manager is not None:
        logger = LoggerAdapter(name=name)
        logger.setLevel(level)
        return logger
    
    # Создаём новую конфигурацию
    import os
    ui_mode = os.getenv('UI_MODE', '0') == '1'
    
    if ui_mode:
        config = LoggingConfig.for_ui()
    else:
        config = LoggingConfig.for_dev()
    
    # Маппинг уровней
    level_map = {
        logging.DEBUG: LogLevel.DEBUG,
        logging.INFO: LogLevel.INFO,
        logging.WARNING: LogLevel.WARNING,
        logging.ERROR: LogLevel.ERROR,
    }
    config.level = level_map.get(level, LogLevel.INFO)
    
    # Настраиваем файл и консоль
    config.enable_console = console_output
    if log_file:
        config.enable_file = True
        config.log_file = Path(log_file)
    else:
        # Если файл не указан, но хотим логирование, используем стандартный путь
        if not config.enable_file:
            config.log_file = Path("logs/app.jsonl")
    
    # Создаём LogManager с новой конфигурацией
    _default_log_manager = LogManager(config)
    
    # Возвращаем адаптер
    logger = LoggerAdapter(name=name)
    logger.setLevel(level)
    
    return logger


def get_logger() -> LoggerAdapter:
    """Возвращает глобальный логгер по умолчанию.
    
    Returns:
        LoggerAdapter совместимый со стандартным logging.Logger
    """
    return LoggerAdapter()


def get_log_manager() -> LogManager:
    """Возвращает глобальный LogManager (для прямого использования новой системы).
    
    Returns:
        Глобальный экземпляр LogManager
    """
    return _get_log_manager()