"""Pytest конфигурация и фикстуры."""
import pytest
from pathlib import Path
from typing import Generator
import tempfile
import shutil


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Создаёт временную директорию проекта для тестов."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_python_file(temp_project_dir: Path) -> Path:
    """Создаёт пример Python файла для тестов."""
    test_file = temp_project_dir / "test_file.py"
    test_file.write_text("""
def hello_world():
    \"\"\"Простая функция.\"\"\"
    print("Hello, World!")

class TestClass:
    def method(self):
        pass
""")
    return test_file


@pytest.fixture
def sample_typescript_file(temp_project_dir: Path) -> Path:
    """Создаёт пример TypeScript файла для тестов."""
    test_file = temp_project_dir / "test_component.tsx"
    test_file.write_text("""
import React from 'react';

interface Props {
    name: string;
}

export const TestComponent: React.FC<Props> = ({ name }) => {
    return <div>Hello, {name}!</div>;
};
""")
    return test_file


@pytest.fixture
def sample_html_file(temp_project_dir: Path) -> Path:
    """Создаёт пример HTML файла для тестов."""
    test_file = temp_project_dir / "test.html"
    test_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <div>Content</div>
</body>
</html>
""")
    return test_file
