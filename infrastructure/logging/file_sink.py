"""FileLoggerSink - запись логов в JSONL файлы с ротацией."""
import json
import sys
import threading
from pathlib import Path
from typing import Optional, TextIO
from datetime import datetime

from infrastructure.logging.models import LogEvent
from infrastructure.logging.sink import LoggerSink


class FileLoggerSink(LoggerSink):
    """Sink для записи логов в JSONL файл.
    
    Особенности:
    - Запись в формате JSONL (одно событие на строку)
    - Ротация файлов при достижении размера
    - Потокобезопасная запись
    - Безопасная запись с гарантией целостности
    """
    
    def __init__(
        self,
        log_file: Path,
        max_size_mb: int = 100,
        backup_count: int = 5,
        encoding: str = "utf-8"
    ) -> None:
        """Инициализация FileLoggerSink.
        
        Args:
            log_file: Путь к файлу логов
            max_size_mb: Максимальный размер файла в МБ перед ротацией
            backup_count: Количество резервных копий
            encoding: Кодировка файла
        """
        self.log_file = Path(log_file)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.backup_count = backup_count
        self.encoding = encoding
        self._lock = threading.Lock()
        
        # Создаём директорию если её нет
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Открываем файл для добавления
        self._file_handle: Optional[TextIO] = None
        self._open_file()
    
    def _open_file(self) -> None:
        """Открывает файл для записи."""
        try:
            self._file_handle = open(
                self.log_file,
                mode="a",
                encoding=self.encoding,
                buffering=1  # Строковая буферизация для безопасности
            )
        except Exception as e:
            # Если не можем открыть файл, это критическая ошибка
            # Но не падаем, чтобы не сломать приложение
            # Используем sys.stderr так как это инфраструктурный слой
            # и сама система логирования ещё не работает
            sys.stderr.write(f"❌ FileLoggerSink: ошибка открытия файла {self.log_file}: {e}\n")
            self._file_handle = None
    
    def _rotate_if_needed(self) -> None:
        """Выполняет ротацию файла если необходимо."""
        if self._file_handle is None:
            return
        
        try:
            current_size = self.log_file.stat().st_size
            if current_size >= self.max_size_bytes:
                self._rotate_file()
        except Exception as e:
            # Игнорируем ошибки ротации, чтобы не прерывать логирование
            sys.stderr.write(f"⚠️ FileLoggerSink: ошибка проверки размера файла: {e}\n")
    
    def _rotate_file(self) -> None:
        """Выполняет ротацию файла."""
        if self._file_handle is None:
            return
        
        try:
            self._file_handle.close()
            
            # Удаляем самые старые копии
            if self.backup_count > 0:
                oldest_backup = self.log_file.with_suffix(
                    f".{self.backup_count}.jsonl"
                )
                if oldest_backup.exists():
                    oldest_backup.unlink()
            
            # Сдвигаем существующие копии
            for i in range(self.backup_count - 1, 0, -1):
                old_backup = self.log_file.with_suffix(f".{i}.jsonl")
                new_backup = self.log_file.with_suffix(f".{i + 1}.jsonl")
                if old_backup.exists():
                    old_backup.rename(new_backup)
            
            # Переименовываем текущий файл
            first_backup = self.log_file.with_suffix(".1.jsonl")
            if self.log_file.exists():
                self.log_file.rename(first_backup)
            
            # Открываем новый файл
            self._open_file()
        except Exception as e:
            # При ошибке ротации пытаемся продолжить работу
            # Используем sys.stderr так как это инфраструктурный слой
            sys.stderr.write(f"⚠️ Ошибка ротации логов: {e}\n")
            self._open_file()
    
    def emit(self, event: LogEvent) -> None:
        """Записывает событие в файл.
        
        Args:
            event: Событие для записи
        """
        if self._file_handle is None:
            return
        
        with self._lock:
            try:
                # Проверяем необходимость ротации
                self._rotate_if_needed()
                
                # Сериализуем событие в JSON
                event_dict = event.to_dict()
                json_line = json.dumps(event_dict, ensure_ascii=False) + "\n"
                
                # Записываем в файл
                self._file_handle.write(json_line)
                
            except Exception as e:
                # Не падаем при ошибках записи
                # Используем sys.stderr так как это инфраструктурный слой
                sys.stderr.write(f"⚠️ Ошибка записи в файл логов: {e}\n")
    
    def flush(self) -> None:
        """Сбрасывает буфер файла."""
        with self._lock:
            if self._file_handle is not None:
                try:
                    self._file_handle.flush()
                except Exception as e:
                    sys.stderr.write(f"⚠️ FileLoggerSink: ошибка flush: {e}\n")
    
    def close(self) -> None:
        """Закрывает файл."""
        with self._lock:
            if self._file_handle is not None:
                try:
                    self._file_handle.flush()
                    self._file_handle.close()
                except Exception as e:
                    sys.stderr.write(f"⚠️ FileLoggerSink: ошибка закрытия файла: {e}\n")
                finally:
                    self._file_handle = None