"""Абстрактный интерфейс для sink-ов логирования."""
from abc import ABC, abstractmethod
from infrastructure.logging.models import LogEvent


class LoggerSink(ABC):
    """Абстрактный базовый класс для sink-ов логирования.
    
    Sink - это место назначения для логов (файл, консоль, память и т.п.).
    Бизнес-код работает ТОЛЬКО с этим интерфейсом, не зная конкретной реализации.
    """
    
    @abstractmethod
    def emit(self, event: LogEvent) -> None:
        """Отправляет событие в sink.
        
        Args:
            event: Событие для логирования
        """
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """Сбрасывает буферы (если есть) в sink.
        
        Метод должен гарантировать, что все буферизованные события
        будут записаны в sink.
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Закрывает sink и освобождает ресурсы.
        
        После вызова этого метода sink не должен принимать новые события.
        """
        pass
    
    def __enter__(self) -> 'LoggerSink':
        """Поддержка контекстного менеджера."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Автоматическое закрытие при выходе из контекста."""
        self.close()