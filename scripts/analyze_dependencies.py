#!/usr/bin/env python3
"""Скрипт для статического анализа импортов и построения графа зависимостей.

Анализирует:
- Циклические зависимости
- Сиротские модули (неиспользуемые)
- Нарушение слоёв архитектуры
- Отсутствующие зависимости
"""
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import json

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("⚠️ networkx не установлен. Установите: pip install networkx matplotlib")

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("⚠️ matplotlib не установлен. Установите: pip install matplotlib")


# Определение слоёв архитектуры
ARCHITECTURE_LAYERS = {
    "frontend": 0,  # UI слой (не должен импортировать backend/agents/infrastructure)
    "backend": 1,   # API слой (может импортировать agents, infrastructure, utils, models)
    "agents": 2,    # Бизнес-логика (может импортировать infrastructure, utils, models)
    "infrastructure": 3,  # Инфраструктура (может импортировать utils, models)
    "utils": 4,     # Утилиты (базовый слой)
    "models": 4,    # Модели данных (базовый слой)
    "tests": 5,     # Тесты (могут импортировать всё)
}

# Правила импорта между слоями
ALLOWED_IMPORTS = {
    "frontend": [],  # frontend не должен импортировать Python модули
    "backend": ["agents", "infrastructure", "utils", "models"],
    "agents": ["infrastructure", "utils", "models"],
    "infrastructure": ["utils", "models"],
    "utils": [],  # utils не должен импортировать другие слои
    "models": [],  # models не должен импортировать другие слои
    "tests": ["agents", "backend", "infrastructure", "utils", "models"],
}

# Игнорируемые модули (стандартные библиотеки, внешние пакеты)
IGNORED_MODULES = {
    "typing", "collections", "dataclasses", "enum", "abc", "asyncio",
    "os", "sys", "pathlib", "json", "time", "datetime", "logging",
    "functools", "itertools", "contextlib", "threading", "multiprocessing",
    "fastapi", "pydantic", "uvicorn", "starlette", "ollama", "chromadb",
    "pytest", "unittest", "mypy", "bandit", "networkx", "matplotlib",
    "numpy", "pandas", "requests", "aiohttp", "httpx",
}


class ImportExtractor(ast.NodeVisitor):
    """Извлекает импорты из AST дерева."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, Set[str]] = defaultdict(set)
    
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module = node.module.split('.')[0]
            self.from_imports[module].update(
                alias.name for alias in (node.names or [])
            )


def get_module_layer(module_path: Path) -> Optional[str]:
    """Определяет слой модуля по пути.
    
    Args:
        module_path: Путь к модулю
        
    Returns:
        Название слоя или None
    """
    parts = module_path.parts
    
    if "frontend" in parts:
        return "frontend"
    elif "backend" in parts:
        return "backend"
    elif "agents" in parts:
        return "agents"
    elif "infrastructure" in parts:
        return "infrastructure"
    elif "utils" in parts:
        return "utils"
    elif "models" in parts:
        return "models"
    elif "tests" in parts:
        return "tests"
    
    return None


def normalize_module_name(module_name: str, current_file: Path) -> Optional[str]:
    """Нормализует имя модуля в абсолютный путь.
    
    Args:
        module_name: Имя модуля из import
        current_file: Текущий файл
        
    Returns:
        Нормализованное имя модуля или None
    """
    # Относительные импорты
    if module_name.startswith('.'):
        # Упрощённая обработка относительных импортов
        return None
    
    # Абсолютные импорты
    parts = module_name.split('.')
    root_module = parts[0]
    
    # Проверяем, является ли это локальным модулем проекта
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root / root_module / "__init__.py",
        project_root / root_module / f"{parts[1]}.py" if len(parts) > 1 else None,
        project_root / root_module / f"{parts[0]}.py",
    ]
    
    for path in possible_paths:
        if path and path.exists():
            return str(path.relative_to(project_root))
    
    # Проверяем в подпапках
    for subdir in ["agents", "backend", "infrastructure", "utils", "models"]:
        module_file = project_root / subdir / f"{root_module}.py"
        if module_file.exists():
            return str(module_file.relative_to(project_root))
    
    return None


def extract_imports(file_path: Path) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Извлекает импорты из Python файла.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Кортеж (множество импортов, словарь from_imports)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        extractor = ImportExtractor(file_path)
        extractor.visit(tree)
        
        return extractor.imports, dict(extractor.from_imports)
    except Exception as e:
        print(f"⚠️ Ошибка при парсинге {file_path}: {e}")
        return set(), {}


def find_all_python_files(root: Path) -> List[Path]:
    """Находит все Python файлы в проекте.
    
    Args:
        root: Корневая директория проекта
        
    Returns:
        Список путей к Python файлам
    """
    python_files = []
    
    for path in root.rglob("*.py"):
        # Игнорируем виртуальные окружения и кэши
        if any(part in path.parts for part in [".venv", "__pycache__", ".git", "node_modules", ".chromadb", ".chroma", "output"]):
            continue
        
        python_files.append(path)
    
    return sorted(python_files)


def build_dependency_graph(python_files: List[Path]) -> Tuple[Dict[str, Set[str]], Dict[str, str]]:
    """Строит граф зависимостей модулей.
    
    Args:
        python_files: Список Python файлов
        
    Returns:
        Кортеж (граф зависимостей, словарь слоёв)
    """
    graph: Dict[str, Set[str]] = defaultdict(set)
    module_layers: Dict[str, str] = {}
    module_to_file: Dict[str, Path] = {}
    
    # Сначала собираем все модули
    for file_path in python_files:
        module_name = str(file_path.relative_to(Path(__file__).parent.parent))
        module_layers[module_name] = get_module_layer(file_path) or "unknown"
        module_to_file[module_name] = file_path
    
    # Затем извлекаем зависимости
    for file_path in python_files:
        module_name = str(file_path.relative_to(Path(__file__).parent.parent))
        imports, from_imports = extract_imports(file_path)
        
        # Обрабатываем обычные импорты
        for imp in imports:
            if imp in IGNORED_MODULES:
                continue
            
            normalized = normalize_module_name(imp, file_path)
            if normalized and normalized in module_layers:
                graph[module_name].add(normalized)
        
        # Обрабатываем from imports
        for imp_module, _ in from_imports.items():
            if imp_module in IGNORED_MODULES:
                continue
            
            normalized = normalize_module_name(imp_module, file_path)
            if normalized and normalized in module_layers:
                graph[module_name].add(normalized)
    
    return dict(graph), module_layers


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Находит циклические зависимости в графе.
    
    Args:
        graph: Граф зависимостей
        
    Returns:
        Список циклов (каждый цикл - список модулей)
    """
    if not HAS_NETWORKX:
        # Простая реализация без networkx
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Найден цикл
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                # Игнорируем тривиальные циклы в __init__.py
                if len(cycle) > 2 or not all("__init__.py" in n for n in cycle):
                    cycles.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, set()):
                dfs(neighbor, path + [node])
            
            rec_stack.remove(node)
        
        for node in graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    # Используем networkx для более точного поиска циклов
    G = nx.DiGraph()
    for node, deps in graph.items():
        for dep in deps:
            G.add_edge(node, dep)
    
    try:
        cycles = list(nx.simple_cycles(G))
        # Фильтруем тривиальные циклы в __init__.py
        filtered_cycles = [
            cycle for cycle in cycles
            if len(cycle) > 2 or not all("__init__.py" in str(n) for n in cycle)
        ]
        return filtered_cycles
    except Exception as e:
        print(f"⚠️ Ошибка при поиске циклов: {e}")
        return []


def find_orphan_modules(graph: Dict[str, Set[str]], module_layers: Dict[str, str]) -> List[str]:
    """Находит модули, которые никто не использует (сиротские).
    
    Args:
        graph: Граф зависимостей
        module_layers: Словарь слоёв модулей
        
    Returns:
        Список сиротских модулей
    """
    # Собираем все модули, на которые есть ссылки
    referenced = set()
    for deps in graph.values():
        referenced.update(deps)
    
    # Находим модули, которые нигде не используются
    all_modules = set(module_layers.keys())
    orphans = all_modules - referenced
    
    # Исключаем точки входа (main.py, cli.py, run.py), тесты и __init__.py
    entry_points = {"main.py", "cli.py", "run.py"}
    orphans = {
        mod for mod in orphans
        if not any(ep in mod for ep in entry_points)
        and "tests" not in mod
        and "__init__.py" not in mod
    }
    
    return sorted(orphans)


def check_layer_violations(graph: Dict[str, Set[str]], module_layers: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """Проверяет нарушения слоёв архитектуры.
    
    Args:
        graph: Граф зависимостей
        module_layers: Словарь слоёв модулей
        
    Returns:
        Список нарушений (модуль, зависимость, правило)
    """
    violations = []
    
    for module, deps in graph.items():
        # Игнорируем __init__.py файлы
        if "__init__.py" in module:
            continue
        
        module_layer = module_layers.get(module, "unknown")
        
        if module_layer not in ALLOWED_IMPORTS:
            continue
        
        allowed = ALLOWED_IMPORTS[module_layer]
        
        for dep in deps:
            # Игнорируем __init__.py файлы
            if "__init__.py" in dep:
                continue
            
            dep_layer = module_layers.get(dep, "unknown")
            
            # Проверяем, разрешён ли импорт
            if dep_layer not in allowed and dep_layer != "unknown":
                violations.append((
                    module,
                    dep,
                    f"{module_layer} не должен импортировать {dep_layer}"
                ))
    
    return violations


def check_missing_dependencies(graph: Dict[str, Set[str]], python_files: List[Path]) -> List[Tuple[str, str]]:
    """Проверяет отсутствующие зависимости.
    
    Args:
        graph: Граф зависимостей
        python_files: Список Python файлов
        
    Returns:
        Список отсутствующих зависимостей (модуль, зависимость)
    """
    missing = []
    all_modules = {str(f.relative_to(Path(__file__).parent.parent)) for f in python_files}
    
    for module, deps in graph.items():
        for dep in deps:
            if dep not in all_modules:
                # Проверяем, существует ли файл
                dep_path = Path(__file__).parent.parent / dep
                if not dep_path.exists():
                    missing.append((module, dep))
    
    return missing


def visualize_graph(graph: Dict[str, Set[str]], module_layers: Dict[str, str], output_file: str = "dependency_graph.png") -> None:
    """Визуализирует граф зависимостей.
    
    Args:
        graph: Граф зависимостей
        module_layers: Словарь слоёв модулей
        output_file: Путь к выходному файлу
    """
    if not HAS_NETWORKX or not HAS_MATPLOTLIB:
        print("⚠️ Визуализация недоступна (требуется networkx и matplotlib)")
        return
    
    G = nx.DiGraph()
    
    # Добавляем узлы и рёбра
    for node, deps in graph.items():
        G.add_node(node, layer=module_layers.get(node, "unknown"))
        for dep in deps:
            G.add_edge(node, dep)
    
    # Раскраска по слоям
    layer_colors = {
        "frontend": "red",
        "backend": "blue",
        "agents": "green",
        "infrastructure": "orange",
        "utils": "purple",
        "models": "pink",
        "tests": "gray",
        "unknown": "black"
    }
    
    node_colors = [layer_colors.get(module_layers.get(node, "unknown"), "black") for node in G.nodes()]
    
    # Создаём визуализацию
    plt.figure(figsize=(20, 20))
    pos = nx.spring_layout(G, k=2, iterations=50)
    
    nx.draw(
        G, pos,
        with_labels=False,
        node_color=node_colors,
        node_size=100,
        arrows=True,
        arrowsize=10,
        edge_color='gray',
        alpha=0.6
    )
    
    # Добавляем подписи
    labels = {node: Path(node).name for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=6)
    
    plt.title("Граф зависимостей модулей", size=16)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Граф сохранён в {output_file}")


def main():
    """Основная функция анализа."""
    project_root = Path(__file__).parent.parent
    
    print("🔍 Поиск Python файлов...")
    python_files = find_all_python_files(project_root)
    print(f"✅ Найдено {len(python_files)} Python файлов")
    
    print("\n📊 Построение графа зависимостей...")
    graph, module_layers = build_dependency_graph(python_files)
    print(f"✅ Граф построен: {len(graph)} модулей, {sum(len(deps) for deps in graph.values())} зависимостей")
    
    print("\n🔄 Поиск циклических зависимостей...")
    cycles = find_cycles(graph)
    if cycles:
        print(f"❌ Найдено {len(cycles)} циклов:")
        for i, cycle in enumerate(cycles[:10], 1):  # Показываем первые 10
            print(f"  {i}. {' -> '.join(Path(c).name for c in cycle)} -> ...")
        if len(cycles) > 10:
            print(f"  ... и ещё {len(cycles) - 10} циклов")
    else:
        print("✅ Циклических зависимостей не найдено")
    
    print("\n👻 Поиск сиротских модулей...")
    orphans = find_orphan_modules(graph, module_layers)
    if orphans:
        print(f"⚠️ Найдено {len(orphans)} сиротских модулей:")
        for orphan in orphans[:20]:  # Показываем первые 20
            print(f"  - {orphan}")
        if len(orphans) > 20:
            print(f"  ... и ещё {len(orphans) - 20} модулей")
    else:
        print("✅ Сиротских модулей не найдено")
    
    print("\n🚫 Проверка нарушений слоёв архитектуры...")
    violations = check_layer_violations(graph, module_layers)
    if violations:
        print(f"❌ Найдено {len(violations)} нарушений:")
        for module, dep, rule in violations[:20]:  # Показываем первые 20
            print(f"  - {Path(module).name} -> {Path(dep).name}: {rule}")
        if len(violations) > 20:
            print(f"  ... и ещё {len(violations) - 20} нарушений")
    else:
        print("✅ Нарушений слоёв архитектуры не найдено")
    
    print("\n❓ Проверка отсутствующих зависимостей...")
    missing = check_missing_dependencies(graph, python_files)
    if missing:
        print(f"⚠️ Найдено {len(missing)} отсутствующих зависимостей:")
        for module, dep in missing[:20]:  # Показываем первые 20
            print(f"  - {Path(module).name} -> {dep}")
        if len(missing) > 20:
            print(f"  ... и ещё {len(missing) - 20} зависимостей")
    else:
        print("✅ Отсутствующих зависимостей не найдено")
    
    # Сохраняем результаты в JSON
    results = {
        "total_modules": len(module_layers),
        "total_dependencies": sum(len(deps) for deps in graph.values()),
        "cycles": cycles[:50],  # Ограничиваем для JSON
        "orphans": orphans,
        "violations": violations,
        "missing": missing,
    }
    
    output_json = project_root / "dependency_analysis.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Результаты сохранены в {output_json}")
    
    # Визуализация
    if HAS_NETWORKX and HAS_MATPLOTLIB:
        print("\n📈 Создание визуализации графа...")
        visualize_graph(graph, module_layers, str(project_root / "dependency_graph.png"))
    
    print("\n✅ Анализ завершён!")


if __name__ == "__main__":
    main()
