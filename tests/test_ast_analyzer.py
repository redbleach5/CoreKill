"""Тесты для AST Analyzer (Phase 6)."""
import pytest
from pathlib import Path

from infrastructure.ast_analyzer import (
    FunctionInfo,
    ClassInfo,
    ImportInfo,
    CodeMetrics,
    FileAnalysis,
    ASTAnalyzer,
    DependencyGraph,
    DependencyNode,
    ProjectAnalyzer,
    analyze_code_structure,
)


class TestFunctionInfo:
    """Тесты для FunctionInfo dataclass."""
    
    def test_function_info_creation(self):
        """Проверяет создание FunctionInfo."""
        info = FunctionInfo(
            name="test_func",
            lineno=10,
            end_lineno=20,
            args=["x", "y"],
            returns="int",
            docstring="Test function",
            is_async=False,
            decorators=["staticmethod"],
            complexity=3
        )
        
        assert info.name == "test_func"
        assert info.lineno == 10
        assert info.args == ["x", "y"]
        assert info.returns == "int"
        assert info.complexity == 3


class TestClassInfo:
    """Тесты для ClassInfo dataclass."""
    
    def test_class_info_creation(self):
        """Проверяет создание ClassInfo."""
        method = FunctionInfo(
            name="method",
            lineno=15,
            end_lineno=20,
            args=["self"],
            returns=None,
            docstring=None,
            is_async=False,
            decorators=[],
            complexity=1
        )
        
        info = ClassInfo(
            name="TestClass",
            lineno=10,
            end_lineno=30,
            bases=["BaseClass"],
            methods=[method],
            docstring="Test class",
            decorators=["dataclass"]
        )
        
        assert info.name == "TestClass"
        assert info.bases == ["BaseClass"]
        assert len(info.methods) == 1


class TestImportInfo:
    """Тесты для ImportInfo dataclass."""
    
    def test_import_info_regular(self):
        """Проверяет обычный import."""
        info = ImportInfo(
            module="os",
            names=[],
            alias=None,
            lineno=1,
            is_from=False
        )
        
        assert info.module == "os"
        assert info.is_from is False
    
    def test_import_info_from(self):
        """Проверяет from X import Y."""
        info = ImportInfo(
            module="pathlib",
            names=["Path", "PurePath"],
            alias=None,
            lineno=2,
            is_from=True
        )
        
        assert info.module == "pathlib"
        assert info.names == ["Path", "PurePath"]
        assert info.is_from is True


class TestCodeMetrics:
    """Тесты для CodeMetrics dataclass."""
    
    def test_metrics_to_dict(self):
        """Проверяет сериализацию."""
        metrics = CodeMetrics(
            file_path="test.py",
            lines_of_code=100,
            blank_lines=20,
            comment_lines=10,
            functions_count=5,
            classes_count=2,
            imports_count=8,
            avg_function_complexity=2.5,
            max_function_complexity=5
        )
        
        d = metrics.to_dict()
        
        assert d["loc"] == 100
        assert d["functions"] == 5
        assert d["avg_complexity"] == 2.5


class TestASTAnalyzer:
    """Тесты для ASTAnalyzer."""
    
    def test_analyze_simple_function(self):
        """Проверяет анализ простой функции."""
        code = '''
def hello(name: str) -> str:
    """Says hello."""
    return f"Hello, {name}"
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert len(result.functions) == 1
        assert result.functions[0].name == "hello"
        assert result.functions[0].args == ["name"]
        assert result.functions[0].returns == "str"
        assert result.functions[0].docstring == "Says hello."
    
    def test_analyze_async_function(self):
        """Проверяет анализ async функции."""
        code = '''
async def fetch_data(url: str) -> dict:
    """Fetches data."""
    pass
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert len(result.functions) == 1
        assert result.functions[0].is_async is True
    
    def test_analyze_class(self):
        """Проверяет анализ класса."""
        code = '''
class MyClass(BaseClass):
    """My class."""
    
    def __init__(self, value: int):
        self.value = value
    
    def get_value(self) -> int:
        return self.value
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert len(result.classes) == 1
        assert result.classes[0].name == "MyClass"
        assert result.classes[0].bases == ["BaseClass"]
        assert len(result.classes[0].methods) == 2
    
    def test_analyze_imports(self):
        """Проверяет анализ импортов."""
        code = '''
import os
import sys
from pathlib import Path
from typing import List, Optional
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert len(result.imports) == 4
        
        # Проверяем обычные импорты
        os_import = next(i for i in result.imports if i.module == "os")
        assert os_import.is_from is False
        
        # Проверяем from импорты
        pathlib_import = next(i for i in result.imports if i.module == "pathlib")
        assert pathlib_import.is_from is True
        assert "Path" in pathlib_import.names
    
    def test_analyze_syntax_error(self):
        """Проверяет обработку синтаксической ошибки."""
        code = "def broken(:"
        
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is None
    
    def test_calculate_complexity_simple(self):
        """Проверяет расчёт complexity для простой функции."""
        code = '''
def simple():
    return 42
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert result.functions[0].complexity == 1
    
    def test_calculate_complexity_with_branches(self):
        """Проверяет расчёт complexity для функции с ветвлениями."""
        code = '''
def complex_func(x):
    if x > 0:
        if x > 10:
            return "big"
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        # 1 (base) + 3 (if, if, elif) = 4
        assert result.functions[0].complexity >= 4
    
    def test_calculate_complexity_with_loops(self):
        """Проверяет расчёт complexity для функции с циклами."""
        code = '''
def loop_func(items):
    for item in items:
        while item > 0:
            item -= 1
    return items
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        # 1 (base) + 1 (for) + 1 (while) = 3
        assert result.functions[0].complexity == 3
    
    def test_file_analysis_helpers(self):
        """Проверяет helper методы FileAnalysis."""
        code = '''
import os

def func1(): pass
def func2(): pass

class MyClass:
    def method1(self): pass
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code, "test.py")
        
        assert result is not None
        
        # Все имена функций
        all_funcs = result.get_all_function_names()
        assert "func1" in all_funcs
        assert "func2" in all_funcs
        assert "MyClass.method1" in all_funcs
        
        # Все классы
        all_classes = result.get_all_class_names()
        assert "MyClass" in all_classes
        
        # Импортированные модули
        imports = result.get_imported_modules()
        assert "os" in imports


class TestDependencyGraph:
    """Тесты для DependencyGraph."""
    
    def test_add_module(self):
        """Проверяет добавление модуля."""
        graph = DependencyGraph()
        graph.add_module("main.py", ["utils", "config"])
        
        deps = graph.get_dependencies("main.py")
        assert "utils" in deps
        assert "config" in deps
    
    def test_get_dependents(self):
        """Проверяет получение зависимых модулей."""
        graph = DependencyGraph()
        graph.add_module("main.py", ["utils"])
        graph.add_module("app.py", ["utils"])
        
        dependents = graph.get_dependents("utils")
        assert "main.py" in dependents
        assert "app.py" in dependents
    
    def test_calculate_importance(self):
        """Проверяет расчёт важности модулей."""
        graph = DependencyGraph()
        graph.add_module("main.py", ["utils", "config"])
        graph.add_module("app.py", ["utils"])
        graph.add_module("test.py", ["utils", "main.py"])
        
        most_important = graph.get_most_important(3)
        
        # utils импортируется чаще всего
        assert most_important[0][0] == "utils"
    
    def test_get_stats(self):
        """Проверяет статистику графа."""
        graph = DependencyGraph()
        graph.add_module("a.py", ["b", "c"])
        graph.add_module("b.py", ["c"])
        
        stats = graph.get_stats()
        
        # a.py, b.py, b (created as dep of a), c (created as dep)
        assert stats["modules"] >= 3
        assert stats["edges"] == 3  # a->b, a->c, b->c
    
    def test_to_dict(self):
        """Проверяет сериализацию графа."""
        graph = DependencyGraph()
        graph.add_module("main.py", ["utils"])
        
        d = graph.to_dict()
        
        assert "main.py" in d
        assert "utils" in d["main.py"]["imports"]


class TestProjectAnalyzer:
    """Тесты для ProjectAnalyzer."""
    
    def test_project_analyzer_init(self):
        """Проверяет инициализацию."""
        analyzer = ProjectAnalyzer()
        
        assert analyzer._analyzer is not None
        assert analyzer._graph is not None


class TestAnalyzeCodeStructure:
    """Тесты для утилиты analyze_code_structure."""
    
    def test_analyze_valid_code(self):
        """Проверяет анализ валидного кода."""
        code = '''
import os
from typing import List

def process(items: List[str]) -> int:
    """Process items."""
    return len(items)

class Handler:
    pass
'''
        result = analyze_code_structure(code)
        
        assert result is not None
        assert "process" in result["functions"]
        assert "Handler" in result["classes"]
        assert "os" in result["imports"]
    
    def test_analyze_invalid_code(self):
        """Проверяет анализ невалидного кода."""
        code = "def broken(:"
        
        result = analyze_code_structure(code)
        
        assert result is None
    
    def test_analyze_metrics(self):
        """Проверяет метрики в результате."""
        code = '''
def func1(): pass
def func2(): pass
'''
        result = analyze_code_structure(code)
        
        assert result is not None
        assert result["metrics"]["functions"] == 2


class TestDecoratorExtraction:
    """Тесты для извлечения декораторов."""
    
    def test_function_decorators(self):
        """Проверяет извлечение декораторов функции."""
        code = '''
@staticmethod
@cache
def cached_func():
    pass
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert "staticmethod" in result.functions[0].decorators
        assert "cache" in result.functions[0].decorators
    
    def test_class_decorators(self):
        """Проверяет извлечение декораторов класса."""
        code = '''
@dataclass
class MyData:
    value: int
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert "dataclass" in result.classes[0].decorators


class TestModuleDocstring:
    """Тесты для docstring модуля."""
    
    def test_module_docstring(self):
        """Проверяет извлечение docstring модуля."""
        code = '''"""This is a module."""

def func():
    pass
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert result.module_docstring == "This is a module."
    
    def test_no_module_docstring(self):
        """Проверяет отсутствие docstring модуля."""
        code = '''
def func():
    pass
'''
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(code)
        
        assert result is not None
        assert result.module_docstring is None
