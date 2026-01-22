"""AST анализатор для структурного анализа Python кода.

Принцип: AST не галлюцинирует — 100% точность для структурного анализа.

Применение:
- Подсчёт функций/классов
- Граф зависимостей (imports)
- Метрики кода (LOC, complexity)
- Структура проекта

НЕ применять для:
- Понимание intent пользователя (LLM)
- Генерация нового кода (LLM)
- Объяснение что делает код (LLM)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger()


@dataclass
class FunctionInfo:
    """Информация о функции."""
    name: str
    lineno: int
    end_lineno: int
    args: list[str]
    returns: str | None
    docstring: str | None
    is_async: bool
    decorators: list[str]
    complexity: int = 1  # Cyclomatic complexity


@dataclass
class ClassInfo:
    """Информация о классе."""
    name: str
    lineno: int
    end_lineno: int
    bases: list[str]
    methods: list[FunctionInfo]
    docstring: str | None
    decorators: list[str]


@dataclass
class ImportInfo:
    """Информация об импорте."""
    module: str
    names: list[str]  # Что импортируется (или ['*'])
    alias: str | None
    lineno: int
    is_from: bool  # from X import Y vs import X


@dataclass
class CodeMetrics:
    """Метрики кода файла."""
    file_path: str
    lines_of_code: int
    blank_lines: int
    comment_lines: int
    functions_count: int
    classes_count: int
    imports_count: int
    avg_function_complexity: float
    max_function_complexity: int
    
    def to_dict(self) -> dict[str, Any]:
        """Преобразует в словарь."""
        return {
            "file_path": self.file_path,
            "loc": self.lines_of_code,
            "blank_lines": self.blank_lines,
            "comment_lines": self.comment_lines,
            "functions": self.functions_count,
            "classes": self.classes_count,
            "imports": self.imports_count,
            "avg_complexity": round(self.avg_function_complexity, 2),
            "max_complexity": self.max_function_complexity
        }


@dataclass
class FileAnalysis:
    """Полный анализ файла."""
    file_path: str
    functions: list[FunctionInfo]
    classes: list[ClassInfo]
    imports: list[ImportInfo]
    metrics: CodeMetrics
    module_docstring: str | None
    
    def get_all_function_names(self) -> list[str]:
        """Возвращает имена всех функций."""
        names = [f.name for f in self.functions]
        for cls in self.classes:
            names.extend(f"{cls.name}.{m.name}" for m in cls.methods)
        return names
    
    def get_all_class_names(self) -> list[str]:
        """Возвращает имена всех классов."""
        return [c.name for c in self.classes]
    
    def get_imported_modules(self) -> list[str]:
        """Возвращает список импортированных модулей."""
        return [i.module for i in self.imports]


@dataclass
class DependencyNode:
    """Узел в графе зависимостей."""
    module_path: str
    imports: list[str]  # Модули которые импортирует
    imported_by: list[str] = field(default_factory=list)  # Кто импортирует этот модуль
    importance: float = 0.0  # Вычисленная важность


class ASTAnalyzer:
    """Анализатор Python кода через AST.
    
    Использует стандартный модуль ast Python для точного
    структурного анализа без LLM.
    """
    
    def analyze_code(self, code: str, file_path: str = "<string>") -> FileAnalysis | None:
        """Анализирует Python код.
        
        Args:
            code: Исходный код Python
            file_path: Путь к файлу (для отчётов)
            
        Returns:
            FileAnalysis или None если парсинг не удался
        """
        try:
            tree = ast.parse(code)
            return self._analyze_tree(tree, code, file_path)
        except SyntaxError as e:
            logger.debug(f"Синтаксическая ошибка в {file_path}: {e}")
            return None
    
    def analyze_file(self, file_path: str | Path) -> FileAnalysis | None:
        """Анализирует Python файл.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            FileAnalysis или None если файл не удалось прочитать/парсить
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"Файл не найден: {file_path}")
            return None
        
        if path.suffix != ".py":
            logger.debug(f"Пропускаю не-Python файл: {file_path}")
            return None
        
        try:
            code = path.read_text(encoding="utf-8")
            return self.analyze_code(code, str(path))
        except Exception as e:
            logger.warning(f"Ошибка чтения {file_path}: {e}")
            return None
    
    def _analyze_tree(
        self,
        tree: ast.Module,
        code: str,
        file_path: str
    ) -> FileAnalysis:
        """Анализирует AST дерево."""
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        imports: list[ImportInfo] = []
        
        # Извлекаем docstring модуля
        module_docstring = ast.get_docstring(tree)
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._extract_function(node))
            elif isinstance(node, ast.ClassDef):
                classes.append(self._extract_class(node))
            elif isinstance(node, ast.Import):
                imports.extend(self._extract_import(node))
            elif isinstance(node, ast.ImportFrom):
                imports.append(self._extract_import_from(node))
        
        # Вычисляем метрики
        metrics = self._calculate_metrics(code, functions, classes, imports, file_path)
        
        return FileAnalysis(
            file_path=file_path,
            functions=functions,
            classes=classes,
            imports=imports,
            metrics=metrics,
            module_docstring=module_docstring
        )
    
    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> FunctionInfo:
        """Извлекает информацию о функции."""
        # Аргументы
        args = [arg.arg for arg in node.args.args]
        
        # Возвращаемый тип
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)
        
        # Декораторы
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        # Cyclomatic complexity
        complexity = self._calculate_complexity(node)
        
        return FunctionInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            args=args,
            returns=returns,
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            complexity=complexity
        )
    
    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        """Извлекает информацию о классе."""
        # Базовые классы
        bases = [ast.unparse(base) for base in node.bases]
        
        # Методы
        methods: list[FunctionInfo] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function(item))
        
        # Декораторы
        decorators = [ast.unparse(d) for d in node.decorator_list]
        
        return ClassInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            bases=bases,
            methods=methods,
            docstring=ast.get_docstring(node),
            decorators=decorators
        )
    
    def _extract_import(self, node: ast.Import) -> list[ImportInfo]:
        """Извлекает информацию из import statement."""
        imports: list[ImportInfo] = []
        
        for alias in node.names:
            imports.append(ImportInfo(
                module=alias.name,
                names=[],
                alias=alias.asname,
                lineno=node.lineno,
                is_from=False
            ))
        
        return imports
    
    def _extract_import_from(self, node: ast.ImportFrom) -> ImportInfo:
        """Извлекает информацию из from X import Y statement."""
        module = node.module or ""
        names = [alias.name for alias in node.names]
        
        return ImportInfo(
            module=module,
            names=names,
            alias=None,
            lineno=node.lineno,
            is_from=True
        )
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Вычисляет cyclomatic complexity функции.
        
        Complexity = 1 + количество точек ветвления
        (if, for, while, except, and, or, elif, with)
        """
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or добавляют ветвление
                complexity += len(child.values) - 1
            elif isinstance(child, ast.With):
                complexity += 1
            elif isinstance(child, ast.comprehension):
                # List/dict/set comprehensions
                if child.ifs:
                    complexity += len(child.ifs)
        
        return complexity
    
    def _calculate_metrics(
        self,
        code: str,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        imports: list[ImportInfo],
        file_path: str
    ) -> CodeMetrics:
        """Вычисляет метрики кода."""
        lines = code.split('\n')
        
        loc = 0
        blank = 0
        comments = 0
        
        in_multiline_string = False
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                blank += 1
                continue
            
            # Простая эвристика для комментариев
            if stripped.startswith('#'):
                comments += 1
            elif stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    comments += 1
                else:
                    in_multiline_string = not in_multiline_string
                    comments += 1
            elif in_multiline_string:
                comments += 1
            else:
                loc += 1
        
        # Complexity метрики
        all_functions = list(functions)
        for cls in classes:
            all_functions.extend(cls.methods)
        
        if all_functions:
            complexities = [f.complexity for f in all_functions]
            avg_complexity = sum(complexities) / len(complexities)
            max_complexity = max(complexities)
        else:
            avg_complexity = 0.0
            max_complexity = 0
        
        return CodeMetrics(
            file_path=file_path,
            lines_of_code=loc,
            blank_lines=blank,
            comment_lines=comments,
            functions_count=len(functions),
            classes_count=len(classes),
            imports_count=len(imports),
            avg_function_complexity=avg_complexity,
            max_function_complexity=max_complexity
        )


class DependencyGraph:
    """Граф зависимостей между модулями проекта."""
    
    def __init__(self):
        """Инициализирует пустой граф."""
        self._nodes: dict[str, DependencyNode] = {}
    
    def add_module(self, module_path: str, imports: list[str]) -> None:
        """Добавляет модуль и его зависимости.
        
        Args:
            module_path: Путь к модулю
            imports: Список импортируемых модулей
        """
        if module_path not in self._nodes:
            self._nodes[module_path] = DependencyNode(
                module_path=module_path,
                imports=imports
            )
        else:
            self._nodes[module_path].imports = imports
        
        # Обновляем imported_by для зависимостей
        for imp in imports:
            if imp not in self._nodes:
                self._nodes[imp] = DependencyNode(
                    module_path=imp,
                    imports=[]
                )
            if module_path not in self._nodes[imp].imported_by:
                self._nodes[imp].imported_by.append(module_path)
    
    def get_dependencies(self, module_path: str) -> list[str]:
        """Возвращает модули которые импортирует данный модуль."""
        node = self._nodes.get(module_path)
        return node.imports if node else []
    
    def get_dependents(self, module_path: str) -> list[str]:
        """Возвращает модули которые зависят от данного."""
        node = self._nodes.get(module_path)
        return node.imported_by if node else []
    
    def calculate_importance(self) -> None:
        """Вычисляет важность модулей (PageRank-подобный алгоритм).
        
        Модули которые импортируются чаще — важнее.
        """
        # Простая эвристика: важность = количество зависимых модулей
        for node in self._nodes.values():
            direct_importance = len(node.imported_by)
            
            # Добавляем важность от транзитивных зависимостей (1 уровень)
            transitive_importance: float = 0.0
            for dependent in node.imported_by:
                dep_node = self._nodes.get(dependent)
                if dep_node:
                    transitive_importance += len(dep_node.imported_by) * 0.5
            
            node.importance = direct_importance + transitive_importance
    
    def get_most_important(self, n: int = 10) -> list[tuple[str, float]]:
        """Возвращает N самых важных модулей.
        
        Args:
            n: Количество модулей
            
        Returns:
            Список (module_path, importance)
        """
        self.calculate_importance()
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda x: x.importance,
            reverse=True
        )
        return [(node.module_path, node.importance) for node in sorted_nodes[:n]]
    
    def get_stats(self) -> dict[str, Any]:
        """Возвращает статистику графа."""
        if not self._nodes:
            return {"modules": 0, "edges": 0}
        
        total_edges = sum(len(n.imports) for n in self._nodes.values())
        
        return {
            "modules": len(self._nodes),
            "edges": total_edges,
            "avg_imports": total_edges / len(self._nodes) if self._nodes else 0
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Сериализует граф в словарь."""
        return {
            module: {
                "imports": node.imports,
                "imported_by": node.imported_by,
                "importance": round(node.importance, 2)
            }
            for module, node in self._nodes.items()
        }


class ProjectAnalyzer:
    """Анализатор проекта через AST."""
    
    def __init__(self):
        """Инициализирует анализатор."""
        self._analyzer = ASTAnalyzer()
        self._graph = DependencyGraph()
        self._analyses: dict[str, FileAnalysis] = {}
    
    def analyze_project(
        self,
        project_path: str | Path,
        extensions: list[str] | None = None
    ) -> dict[str, Any]:
        """Анализирует весь проект.
        
        Args:
            project_path: Путь к проекту
            extensions: Расширения файлов (по умолчанию [".py"])
            
        Returns:
            Словарь с результатами анализа
        """
        if extensions is None:
            extensions = [".py"]
        
        project = Path(project_path)
        skip_patterns = ['.venv', '__pycache__', '.git', 'node_modules', '.tox']
        
        logger.info(f"📊 Анализирую проект: {project_path}")
        
        files_analyzed = 0
        total_loc = 0
        total_functions = 0
        total_classes = 0
        
        for ext in extensions:
            for file_path in project.rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in skip_patterns):
                    continue
                
                analysis = self._analyzer.analyze_file(file_path)
                if analysis:
                    relative_path = str(file_path.relative_to(project))
                    self._analyses[relative_path] = analysis
                    
                    # Добавляем в граф зависимостей
                    imports = analysis.get_imported_modules()
                    self._graph.add_module(relative_path, imports)
                    
                    # Собираем метрики
                    files_analyzed += 1
                    total_loc += analysis.metrics.lines_of_code
                    total_functions += analysis.metrics.functions_count
                    total_classes += analysis.metrics.classes_count
        
        # Вычисляем важность модулей
        self._graph.calculate_importance()
        
        logger.info(
            f"✅ Проанализировано {files_analyzed} файлов, "
            f"{total_loc} LOC, {total_functions} функций, {total_classes} классов"
        )
        
        return {
            "files_analyzed": files_analyzed,
            "total_loc": total_loc,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "dependency_graph": self._graph.get_stats(),
            "most_important_modules": self._graph.get_most_important(10)
        }
    
    def get_file_analysis(self, file_path: str) -> FileAnalysis | None:
        """Возвращает анализ конкретного файла."""
        return self._analyses.get(file_path)
    
    def get_dependency_graph(self) -> DependencyGraph:
        """Возвращает граф зависимостей."""
        return self._graph
    
    def format_structure_report(self) -> str:
        """Форматирует отчёт о структуре проекта."""
        lines = ["# Структура проекта\n"]
        
        for path, analysis in sorted(self._analyses.items()):
            lines.append(f"\n## {path}")
            lines.append(f"LOC: {analysis.metrics.lines_of_code}, "
                        f"Functions: {analysis.metrics.functions_count}, "
                        f"Classes: {analysis.metrics.classes_count}")
            
            if analysis.functions:
                lines.append("\n### Функции:")
                for f in analysis.functions:
                    async_prefix = "async " if f.is_async else ""
                    returns = f" -> {f.returns}" if f.returns else ""
                    lines.append(f"- {async_prefix}{f.name}({', '.join(f.args)}){returns}")
            
            if analysis.classes:
                lines.append("\n### Классы:")
                for c in analysis.classes:
                    bases = f"({', '.join(c.bases)})" if c.bases else ""
                    lines.append(f"- {c.name}{bases}")
                    for m in c.methods:
                        lines.append(f"  - {m.name}()")
        
        return "\n".join(lines)


def analyze_code_structure(code: str, file_path: str = "<string>") -> dict[str, Any] | None:
    """Утилита для быстрого анализа кода.
    
    Args:
        code: Python код
        file_path: Путь к файлу
        
    Returns:
        Словарь с результатами или None
    """
    analyzer = ASTAnalyzer()
    result = analyzer.analyze_code(code, file_path)
    
    if result is None:
        return None
    
    return {
        "functions": result.get_all_function_names(),
        "classes": result.get_all_class_names(),
        "imports": result.get_imported_modules(),
        "metrics": result.metrics.to_dict()
    }
