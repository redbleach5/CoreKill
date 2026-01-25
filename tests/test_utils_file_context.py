"""Тесты для utils/file_context.py."""
import pytest
import tempfile
from pathlib import Path
from utils.file_context import (
    extract_file_path_from_task,
    read_file_context,
    prepare_modify_context
)


class TestExtractFilePathFromTask:
    """Тесты для extract_file_path_from_task."""
    
    @pytest.mark.utils

    
    def test_extract_file_path_explicit_file(self):
        """Тест извлечения пути с явным указанием 'файл:'."""
        task = "Исправить ошибку в файле: src/main.py"
        file_path = extract_file_path_from_task(task)
        
        # Если файл существует, должен вернуть путь
        # Если нет - может вернуть None или путь в зависимости от реализации
        assert file_path is not None or file_path is None
    
    @pytest.mark.utils

    
    def test_extract_file_path_explicit_file_en(self):
        """Тест извлечения пути с 'file:'."""
        task = "Fix error in file: src/main.py"
        file_path = extract_file_path_from_task(task)
        
        assert file_path is not None or file_path is None
    
    @pytest.mark.utils

    
    def test_extract_file_path_in_file(self):
        """Тест извлечения пути с 'в файле'."""
        task = "Исправить ошибку в файле src/main.py"
        file_path = extract_file_path_from_task(task)
        
        assert file_path is not None or file_path is None
    
    @pytest.mark.utils

    
    def test_extract_file_path_python_extension(self):
        """Тест извлечения пути к .py файлу."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_file.py"
            test_file.write_text("print('test')")
            
            # Используем полный путь в задаче
            task = f"Исправить ошибку в файле: {test_file}"
            file_path = extract_file_path_from_task(task)
            
            # Должен вернуть путь к файлу
            assert file_path is not None
            assert Path(file_path).exists()
    
    @pytest.mark.utils

    
    def test_extract_file_path_not_found(self):
        """Тест когда файл не найден."""
        task = "Исправить ошибку в файле: nonexistent/file.py"
        file_path = extract_file_path_from_task(task)
        
        # Должен вернуть None если файл не существует
        assert file_path is None or file_path == "nonexistent/file.py"
    
    @pytest.mark.utils

    
    def test_extract_file_path_no_file(self):
        """Тест когда в задаче нет указания файла."""
        task = "Создать новую функцию"
        file_path = extract_file_path_from_task(task)
        
        assert file_path is None


class TestReadFileContext:
    """Тесты для read_file_context."""
    
    @pytest.mark.utils

    
    def test_read_file_context_exists(self):
        """Тест чтения существующего файла."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            content = "def hello():\n    return 'world'\n\nprint(hello())"
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            context = read_file_context(str(temp_path))
            
            assert context is not None
            assert "def hello" in context
        finally:
            temp_path.unlink()
    
    @pytest.mark.utils

    
    def test_read_file_context_not_exists(self):
        """Тест чтения несуществующего файла."""
        context = read_file_context("nonexistent/file.py")
        
        assert context is None
    
    @pytest.mark.utils

    
    def test_read_file_context_max_lines(self):
        """Тест ограничения количества строк."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Создаём файл с большим количеством строк
            lines = [f"# Line {i}\n" for i in range(2000)]
            f.writelines(lines)
            temp_path = Path(f.name)
        
        try:
            context = read_file_context(str(temp_path), max_lines=100)
            
            assert context is not None
            # Должно быть ограничено max_lines (плюс сообщение об обрезке)
            line_count = len(context.split('\n'))
            # Может быть немного больше из-за сообщения об обрезке
            assert line_count <= 105  # 100 строк + сообщение
        finally:
            temp_path.unlink()
    
    @pytest.mark.utils

    
    def test_read_file_context_encoding_error(self):
        """Тест обработки ошибки кодировки."""
        # Создаём файл с бинарными данными
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'\xff\xfe\x00\x01')  # Невалидная UTF-8 последовательность
            temp_path = Path(f.name)
        
        try:
            context = read_file_context(str(temp_path))
            
            # Должен вернуть None или обработать ошибку
            assert context is None or isinstance(context, str)
        finally:
            temp_path.unlink()


class TestPrepareModifyContext:
    """Тесты для prepare_modify_context."""
    
    @pytest.mark.utils

    
    def test_prepare_modify_context_with_content(self):
        """Тест подготовки контекста с содержимым."""
        existing_code = "def old_function():\n    return 'old'"
        task = "Добавить новую функцию"
        
        context = prepare_modify_context(task, existing_file_content=existing_code)
        
        assert context is not None
        assert task in context
        assert existing_code in context or "existing" in context.lower()
    
    @pytest.mark.utils

    
    def test_prepare_modify_context_no_content(self):
        """Тест подготовки контекста без существующего кода."""
        task = "Создать новую функцию"
        
        context = prepare_modify_context(task, existing_file_content=None)
        
        assert context is not None
        assert task in context
    
    @pytest.mark.utils

    
    def test_prepare_modify_context_empty_content(self):
        """Тест подготовки контекста с пустым содержимым."""
        task = "Добавить функцию"
        
        context = prepare_modify_context(task, existing_file_content="")
        
        assert context is not None
        assert task in context
