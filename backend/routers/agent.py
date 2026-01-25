"""Роутер для работы с агентами через API.

Поддерживает режимы взаимодействия:
- auto: Автоматический выбор режима на основе анализа
- chat: Простой диалог с LLM без workflow
- plan: Только планирование без генерации кода
- analyze: Анализ кода/задачи
- code: Полный workflow генерации кода (TDD)
"""
import asyncio
import re
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from agents.intent import IntentAgent, IntentResult
from agents.chat import ChatAgent, get_chat_agent
from agents.conversation import get_conversation_memory, ConversationMemory
from agents.reflection import ReflectionResult
from backend.types import InteractionMode, TaskRequest, SessionSettings, StreamQueryParams, IndexProjectRequest
from utils.artifact_saver import ArtifactSaver
from utils.config import get_config
from utils.model_checker import (
    get_all_available_models,
    get_all_models_info,
    check_model_available,
    scan_available_models,
    TaskComplexity,
    ModelInfo
)
from infrastructure.model_router import ModelSelection
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.logger import get_logger
from utils.path_validator import validate_file_path, validate_directory_path
from utils.ui_delays import ui_sleep
from backend.sse_manager import SSEManager
from backend.sse_helpers import send_greeting_response
from backend.workflow_streamer import WorkflowStreamer
from backend.mode_detector import ModeDetector
from backend.messages import GREETING_MESSAGE, HELP_MESSAGE
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState
from infrastructure.model_router import get_model_router, reset_model_router
from infrastructure.workflow_nodes import (
    _is_streaming_enabled,
    intent_node,
    researcher_node,
    validator_node,
    stream_planner_node,
    stream_generator_node,
    stream_coder_node,
    stream_debugger_node,
    stream_fixer_node,
    stream_reflection_node,
    stream_critic_node
)


logger = get_logger()


router = APIRouter(prefix="/api", tags=["agents"])

# ========== ИМПОРТ ЗАВИСИМОСТЕЙ ==========

# MemoryAgent через DependencyContainer (Singleton)
from backend.dependencies import get_memory_agent as _get_memory_agent

# Импортируем handlers из отдельных модулей
from backend.routers.agent_handlers import (
    run_analyze_stream,
    run_chat_stream,
    run_workflow_stream
)

# TaskRequest импортирован из backend.types


# Старые функции удалены - теперь используются handlers из agent_handlers/
# async def run_analyze_stream(...) - перенесено в agent_handlers/analyze_handler.py
# async def run_chat_stream(...) - перенесено в agent_handlers/chat_handler.py
# async def run_workflow_stream(...) - перенесено в agent_handlers/workflow_handler.py


# ========== ENDPOINTS ==========


@router.post("/tasks")
async def create_task(request: TaskRequest) -> Dict[str, str]:
    """Создаёт задачу и возвращает task_id для SSE подключения.
    
    Args:
        request: Запрос с параметрами задачи
        
    Returns:
        Словарь с task_id
    """
    task_id = str(uuid.uuid4())
    
    # Запускаем workflow в фоне (через SSE endpoint)
    # В реальности task_id будет использоваться для получения результатов через SSE
    
    return {
        "task_id": task_id,
        "status": "created",
        "message": "Задача создана. Подключитесь к /api/stream/{task_id} для получения результатов."
    }


@router.get("/models")
async def get_models() -> Dict[str, Any]:
    """Возвращает список доступных моделей Ollama с детальной информацией.
    
    Модели отсортированы по качеству (лучшие для кода первые).
    Включает информацию о размере, специализации и рекомендациях.
    
    Returns:
        Словарь с списком моделей и их характеристиками
    """
    # Сканируем модели заново для актуальности
    models_info = get_all_models_info()
    
    # Формируем ответ с детальной информацией
    models_list = []
    for info in models_info:
        # Определяем рекомендацию по сложности
        if info.estimated_quality >= 0.7:
            recommended_for = ["complex", "medium", "simple"]
        elif info.estimated_quality >= 0.5:
            recommended_for = ["medium", "simple"]
        else:
            recommended_for = ["simple"]
        
        models_list.append({
            "name": info.name,
            "size_gb": round(info.size_gb, 2),
            "parameters": info.parameter_size,
            "family": info.family,
            "is_coder": info.is_coder,
            "is_reasoning": info.is_reasoning,  # Reasoning модель с встроенным CoT
            "quality_score": info.estimated_quality,
            "recommended_for": recommended_for
        })
    
    # Также возвращаем простой список имён для обратной совместимости
    model_names = [m["name"] for m in models_list]
    
    return {
        "models": model_names,  # Для обратной совместимости
        "models_detailed": models_list,  # Детальная информация
        "count": len(models_list),
        "recommendations": {
            "simple": _get_recommendation_for_complexity(models_info, TaskComplexity.SIMPLE),
            "medium": _get_recommendation_for_complexity(models_info, TaskComplexity.MEDIUM),
            "complex": _get_recommendation_for_complexity(models_info, TaskComplexity.COMPLEX)
        }
    }


def _get_recommendation_for_complexity(
    models: List[ModelInfo], 
    complexity: TaskComplexity
) -> Optional[str]:
    """Возвращает рекомендуемую модель для сложности."""
    min_quality = {
        TaskComplexity.SIMPLE: 0.3,
        TaskComplexity.MEDIUM: 0.55,
        TaskComplexity.COMPLEX: 0.7
    }
    
    threshold = min_quality[complexity]
    suitable = [m for m in models if m.estimated_quality >= threshold and 'embed' not in m.name.lower()]
    
    if suitable:
        # Для simple предпочитаем быстрые, для complex - качественные
        if complexity == TaskComplexity.SIMPLE:
            # Выбираем минимально подходящую (быстрее)
            return min(suitable, key=lambda m: m.estimated_quality).name
        else:
            # Выбираем лучшую по качеству
            return max(suitable, key=lambda m: m.estimated_quality).name
    
    # Если нет подходящих, возвращаем лучшую из доступных
    non_embed = [m for m in models if 'embed' not in m.name.lower()]
    if non_embed:
        return max(non_embed, key=lambda m: m.estimated_quality).name
    
    return models[0].name if models else None


@router.post("/models/refresh")
async def refresh_models() -> Dict[str, Any]:
    """Принудительно обновляет список моделей Ollama.
    
    Используйте после добавления/удаления моделей через ollama pull/rm.
    
    Returns:
        Обновлённый список моделей
    """
    reset_model_router()
    return await get_models()


@router.get("/browse-folder")
async def browse_folder(start_path: Optional[str] = None) -> Dict[str, Any]:
    """Открывает системный диалог выбора папки.
    
    Использует нативные средства ОС:
    - macOS: osascript (AppleScript)
    - Windows: PowerShell
    - Linux: zenity или kdialog
    
    Args:
        start_path: Начальная директория для диалога (опционально)
        
    Returns:
        Словарь с выбранным путём или cancelled если отменено
    """
    import asyncio
    import os
    import platform
    import subprocess
    
    def _open_folder_dialog_native(initial_dir: Optional[str] = None) -> Optional[str]:
        """Открывает нативный диалог выбора папки."""
        system = platform.system()
        initial = initial_dir if initial_dir and os.path.isdir(initial_dir) else os.path.expanduser("~")
        
        try:
            if system == "Darwin":  # macOS
                # AppleScript для нативного диалога
                script = f'''
                    set defaultFolder to POSIX file "{initial}"
                    try
                        set selectedFolder to choose folder with prompt "Выберите папку проекта" default location defaultFolder
                        return POSIX path of selectedFolder
                    on error
                        return ""
                    end try
                '''
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 минут на выбор
                )
                path = result.stdout.strip()
                # Убираем trailing slash если есть
                return path.rstrip("/") if path else None
                
            elif system == "Windows":
                # PowerShell для Windows
                script = f'''
                    Add-Type -AssemblyName System.Windows.Forms
                    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
                    $dialog.Description = "Выберите папку проекта"
                    $dialog.SelectedPath = "{initial}"
                    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                        Write-Output $dialog.SelectedPath
                    }}
                '''
                result = subprocess.run(
                    ["powershell", "-Command", script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                path = result.stdout.strip()
                return path if path else None
                
            else:  # Linux
                # Пробуем zenity (GNOME), потом kdialog (KDE)
                for cmd in [
                    ["zenity", "--file-selection", "--directory", f"--filename={initial}/", "--title=Выберите папку проекта"],
                    ["kdialog", "--getexistingdirectory", initial, "--title", "Выберите папку проекта"]
                ]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            return result.stdout.strip()
                    except FileNotFoundError:
                        continue
                        
                logger.warning("⚠️ Не найден zenity или kdialog для выбора папки")
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning("⏱️ Таймаут диалога выбора папки")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка диалога выбора папки: {e}", error=e)
            return None
    
    # Запускаем диалог в отдельном потоке
    selected_path = await asyncio.to_thread(_open_folder_dialog_native, start_path)
    
    if selected_path:
        logger.info(f"📂 Выбрана папка: {selected_path}")
        return {
            "path": selected_path,
            "name": os.path.basename(selected_path),
            "exists": os.path.isdir(selected_path)
        }
    else:
        return {
            "path": None,
            "cancelled": True
        }


@router.get("/project-files")
async def get_project_files(
    path: str,
    extensions: Optional[str] = None,
    max_depth: int = 5,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Возвращает структуру файлов проекта.
    
    Args:
        path: Путь к корневой папке проекта
        extensions: Расширения файлов через запятую (опционально)
        max_depth: Максимальная глубина сканирования
        project_path: Корень проекта для ограничения доступа (опционально)
        
    Returns:
        Древовидная структура файлов и папок
    """
    import os
    
    # Валидируем путь и проверяем, что он в пределах проекта
    # ИСПРАВЛЕНИЕ: Если project_path не указан, разрешаем доступ к любой директории
    # Это позволяет открывать проекты вне текущего workspace
    try:
        if project_path:
            validated_path = validate_directory_path(path, project_path=project_path)
            path = str(validated_path)
        else:
            # Если project_path не указан, просто проверяем что путь существует
            import os
            resolved_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.isdir(resolved_path):
                return {"error": "Путь не существует", "path": path}
            path = resolved_path
    except HTTPException as e:
        # ИСПРАВЛЕНИЕ: Возвращаем более понятное сообщение об ошибке вместо 403
        if e.status_code == 403:
            return {
                "error": "Доступ запрещён: директория находится вне проекта. Укажите project_path для доступа к этой директории.",
                "path": path,
                "status": 403
            }
        raise  # Пробрасываем другие HTTPException
    except Exception as e:
        logger.debug(f"⚠️ Ошибка валидации пути в select_folder: {e}")
        return {"error": f"Ошибка валидации пути: {str(e)}", "path": path}
    
    if not os.path.isdir(path):
        return {"error": "Путь не существует", "path": path}
    
    IGNORED_DIRS = {
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', 
        '.venv', 'venv', 'env', '.idea', '.vscode', 'dist', 'build',
        '.next', '.nuxt', 'coverage', '.pytest_cache', '.mypy_cache',
        '__pypackages__', '.tox', '.eggs', '.cache'
    }
    
    IGNORED_FILES = {'.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes'}
    
    allowed_ext: set[str] | None = None
    if extensions:
        allowed_ext = {(e.strip() if e.strip().startswith('.') else f'.{e.strip()}').lower() 
                       for e in extensions.split(',')}
    
    def scan_dir(dir_path: str, depth: int = 0) -> Dict[str, Any]:
        """Рекурсивно сканирует директорию и возвращает структуру дерева."""
        result: Dict[str, Any] = {
            "name": os.path.basename(dir_path) or dir_path,
            "path": dir_path,
            "type": "directory",
            "children": []
        }
        
        if depth >= max_depth:
            result["truncated"] = True
            return result
        
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            result["error"] = "Нет доступа"
            return result
        
        dirs, files = [], []
        
        for entry in entries:
            entry_path = os.path.join(dir_path, entry)
            
            if os.path.isdir(entry_path):
                if entry not in IGNORED_DIRS and not entry.startswith('.'):
                    child = scan_dir(entry_path, depth + 1)
                    if child.get("children") or child.get("truncated"):
                        dirs.append(child)
            else:
                if entry not in IGNORED_FILES and not entry.startswith('.'):
                    ext = os.path.splitext(entry)[1].lower()
                    if allowed_ext is None or ext in allowed_ext:
                        files.append({
                            "name": entry,
                            "path": entry_path,
                            "type": "file",
                            "extension": ext,
                            "size": os.path.getsize(entry_path)
                        })
        
        result["children"] = dirs + files
        return result
    
    tree = scan_dir(path)
    
    def count_items(node: Dict[str, Any]) -> tuple[int, int]:
        """Подсчитывает количество файлов и директорий в дереве."""
        if node["type"] == "file":
            return 1, 0
        files, dirs = 0, 1
        for child in node.get("children", []):
            f, d = count_items(child)
            files += f
            dirs += d
        return files, dirs
    
    total_files, total_dirs = count_items(tree)
    
    return {
        "tree": tree,
        "stats": {
            "total_files": total_files,
            "total_directories": total_dirs - 1,
            "root_path": path
        }
    }


@router.get("/file-content")
async def get_file_content(
    path: str,
    project_path: Optional[str] = None
) -> Dict[str, Any]:
    """Читает содержимое файла.
    
    Args:
        path: Полный путь к файлу
        project_path: Корень проекта для ограничения доступа (опционально)
        
    Returns:
        Содержимое файла
    """
    import os
    
    # Валидируем путь и проверяем, что он в пределах проекта
    try:
        validated_path = validate_file_path(path, project_path=project_path)
        path = str(validated_path)
    except HTTPException:
        raise  # Пробрасываем HTTPException от валидатора
    except Exception as e:
        logger.debug(f"⚠️ Ошибка валидации пути в get_file: {e}")
        return {"error": f"Ошибка валидации пути: {str(e)}", "path": path}
    
    if not os.path.isfile(path):
        return {"error": "Файл не найден", "path": path}
    
    try:
        # Ограничиваем размер файла (макс 1MB)
        size = os.path.getsize(path)
        if size > 1024 * 1024:
            return {"error": "Файл слишком большой (>1MB)", "path": path, "size": size}
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return {
            "path": path,
            "name": os.path.basename(path),
            "content": content,
            "size": size
        }
    except Exception as e:
        logger.debug(f"⚠️ Ошибка чтения файла {path}: {e}")
        return {"error": str(e), "path": path}


@router.post("/index")
async def index_project(request: IndexProjectRequest) -> Dict[str, Any]:
    """Индексирует кодовую базу проекта для последующего поиска.
    
    Используется для индексации проекта перед анализом или генерацией кода.
    
    Args:
        request: Запрос с путём к проекту и расширениями файлов
    
    Returns:
        Статус индексации с количеством проиндексированных файлов
    """
    from infrastructure.context_engine import ContextEngine
    from pathlib import Path
    import asyncio
    
    project_path = request.project_path.strip()
    file_extensions = request.file_extensions or [".py"]
    
    project_path_obj = Path(project_path)
    if not project_path_obj.exists() or not project_path_obj.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Проект не найден или не является директорией: {project_path}"
        )
    
    # Нормализуем расширения (добавляем точку если отсутствует)
    normalized_extensions = []
    for ext in file_extensions:
        ext = ext.strip()
        if not ext.startswith('.'):
            ext = f'.{ext}'
        normalized_extensions.append(ext)
    
    try:
        # Создаём ContextEngine и индексируем проект
        context_engine = ContextEngine()
        
        # Индексация выполняется синхронно, запускаем в отдельном потоке
        index_result = await asyncio.to_thread(
            context_engine.index_project,
            project_path=project_path,
            extensions=normalized_extensions if normalized_extensions else None
        )
        
        # Подсчитываем количество файлов и чанков
        total_files = len(index_result)
        total_chunks = sum(len(chunks) for chunks in index_result.values())
        
        logger.info(f"✅ Проиндексирован проект {project_path}: {total_files} файлов, {total_chunks} чанков")
        
        return {
            "status": "success",
            "project_path": project_path,
            "indexed_files": total_files,
            "total_chunks": total_chunks,
            "extensions": normalized_extensions
        }
    except ValueError as e:
        logger.error(f"❌ Ошибка валидации при индексации: {e}", error=e)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка индексации проекта: {e}", error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка индексации проекта: {str(e)}"
        )


@router.get("/metrics/stages")
async def get_stage_metrics() -> Dict[str, Any]:
    """Возвращает метрики производительности по этапам workflow.
    
    Включает:
    - Результаты бенчмарка (скорость генерации, множитель)
    - Статистику по каждому этапу (среднее время, медиана, кол-во замеров)
    - Адаптивные оценки времени для текущего железа
    
    Returns:
        Словарь с метриками
    """
    from infrastructure.performance_metrics import get_performance_metrics
    
    metrics = get_performance_metrics()
    return metrics.get_metrics_summary()


@router.post("/metrics/benchmark")
async def run_benchmark(model: Optional[str] = None) -> Dict[str, Any]:
    """Запускает бенчмарк производительности LLM.
    
    Тестирует скорость генерации и обновляет коэффициент производительности.
    Результаты сохраняются и используются для адаптивных оценок времени.
    
    Args:
        model: Модель для тестирования (опционально, по умолчанию текущая)
        
    Returns:
        Результаты бенчмарка
    """
    from infrastructure.performance_metrics import get_performance_metrics
    
    metrics = get_performance_metrics()
    benchmark = await metrics.run_benchmark(model)
    
    return {
        "benchmark": benchmark.to_dict(),
        "message": f"Бенчмарк завершён: {benchmark.tokens_per_second:.1f} токенов/сек"
    }


def get_stream_params(
    task: str = Query(..., min_length=1, description="Текст задачи"),
    mode: str = Query(default="auto", description="Режим взаимодействия (auto, chat, code)"),
    model: str = Query(default="", description="Модель Ollama (пусто = авто-выбор)"),
    temperature: float = Query(default=0.25, ge=0.1, le=0.7, description="Температура генерации"),
    disable_web_search: bool = Query(default=False, description="Отключить веб-поиск"),
    max_iterations: int = Query(default=3, ge=1, le=5, description="Максимальное количество итераций"),
    conversation_id: Optional[str] = Query(default=None, description="ID диалога для сохранения контекста"),
    project_path: Optional[str] = Query(default=None, description="Путь к проекту для индексации кодовой базы"),
    file_extensions: Optional[str] = Query(default=None, description="Расширения файлов через запятую (например: .py,.js)")
) -> StreamQueryParams:
    """Зависимость для валидации query параметров /api/stream.
    
    Преобразует query параметры в валидированную Pydantic модель.
    """
    # Валидация mode
    try:
        mode_enum = InteractionMode(mode.lower())
        mode_value = mode_enum.value
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый режим: {mode}. Допустимые значения: auto, chat, code, plan, analyze"
        )
    
    return StreamQueryParams(
        task=task,
        mode=mode_value,
        model=model,
        temperature=temperature,
        disable_web_search=disable_web_search,
        max_iterations=max_iterations,
        conversation_id=conversation_id,
        project_path=project_path,
        file_extensions=file_extensions
    )


@router.get("/stream")
async def stream_task_results(
    params: StreamQueryParams = Depends(get_stream_params)
):
    """SSE endpoint для стриминга результатов выполнения задачи.
    
    Поддерживает режимы взаимодействия:
    - auto: Автоматический выбор режима
    - chat: Простой диалог без workflow
    - code: Полный workflow генерации кода
    
    Args:
        task: Текст задачи
        mode: Режим взаимодействия (auto, chat, code)
        model: Модель Ollama
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций
        conversation_id: ID диалога для сохранения контекста
        project_path: Путь к проекту для индексации кодовой базы (опционально)
        file_extensions: Расширения файлов через запятую, например ".py,.js" (опционально)
        
    Returns:
        StreamingResponse с SSE событиями
    """
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    
    # ИСПРАВЛЕНИЕ: Проверяем доступность Ollama и его загрузку перед запуском задачи
    from utils.model_checker import check_ollama_api_available
    from infrastructure.agent_resource_manager import get_resource_manager
    
    # Проверяем доступность Ollama
    if not check_ollama_api_available():
        logger.error("❌ Ollama недоступен, невозможно выполнить задачу")
        raise HTTPException(
            status_code=503,
            detail="Ollama сервис недоступен. Проверьте что Ollama запущен и доступен."
        )
    
    # Проверяем загрузку системы (количество активных агентов)
    try:
        resource_manager = await get_resource_manager()
        stats = resource_manager.get_stats()
        active_agents = stats.get("active_agents", 0)
        max_concurrent = stats.get("max_concurrent", 5)
        
        available_slots = stats.get("available_slots", max_concurrent)
        
        # Если система перегружена (более 80% загрузки), предупреждаем
        if active_agents >= max_concurrent * 0.8:
            logger.warning(
                f"⚠️ Высокая загрузка системы: {active_agents}/{max_concurrent} активных агентов "
                f"(доступно слотов: {available_slots}). Запрос будет обработан, но может быть задержка."
            )
        else:
            logger.debug(
                f"✅ Загрузка системы нормальная: {active_agents}/{max_concurrent} активных агентов "
                f"(доступно слотов: {available_slots})"
            )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось проверить загрузку системы: {e}")
    
    # Извлекаем параметры из валидированной модели
    task = params.task
    mode = params.mode.value if isinstance(params.mode, InteractionMode) else params.mode
    model = params.model
    temperature = params.temperature
    disable_web_search = params.disable_web_search
    max_iterations = params.max_iterations
    conversation_id = params.conversation_id
    project_path = params.project_path
    file_extensions = params.file_extensions
    
    # Парсим file_extensions из строки в список
    parsed_extensions: Optional[List[str]] = None
    if file_extensions:
        parsed_extensions = [ext.strip() for ext in file_extensions.split(",") if ext.strip()]
    
    async def generate() -> AsyncGenerator[str, None]:
        """Генератор SSE событий для потоковой обработки задачи."""
        # Получаем конфигурацию для использования в функции
        config = get_config()
        
        try:
            event_count = 0
            selected_mode = mode
            detected_intent_type: Optional[str] = None
            detected_complexity: Optional[TaskComplexity] = None
            
            # Используем ModeDetector для определения режима
            mode_detector = ModeDetector()
            selected_mode, detected_intent_type, detected_complexity = mode_detector.detect(
                task=task,
                user_mode=mode,
                detected_intent_type=detected_intent_type,
                detected_complexity=detected_complexity
            )
            
            logger.info(f"🎯 Выбран режим: {selected_mode} (запрошен: {mode})")
            
            # Запускаем фоновую консультацию FastAdvisor (если включена)
            advisor_task = None
            advisor_queue = None
            if config.fast_advisor_enabled:
                try:
                    from infrastructure.fast_advisor import get_fast_advisor, AdvisorRequest, AdvisorPriority
                    # SSEManager уже импортирован глобально в начале файла (строка 35)
                    
                    advisor = get_fast_advisor()
                    
                    # Формируем запрос для консультации
                    advisor_request = AdvisorRequest(
                        query=task,
                        context=f"Режим: {selected_mode}, Сложность: {detected_complexity.value if detected_complexity else 'unknown'}",
                        priority=AdvisorPriority.MEDIUM,
                        timeout_seconds=config.fast_advisor_timeout
                    )
                    
                    # Очередь для передачи советов в основной генератор
                    advisor_queue: asyncio.Queue = asyncio.Queue()
                    
                    # Callback для отправки совета через SSE
                    async def send_advisor_suggestion(response):
                        """Отправляет совет от FastAdvisor через очередь событий."""
                        try:
                            event = await SSEManager.stream_advisor_suggestion(
                                advice=response.advice,
                                confidence=response.confidence,
                                priority=response.priority.value,
                                model_used=response.model_used,
                                response_time_ms=response.response_time_ms,
                                metadata=response.metadata
                            )
                            # Добавляем в очередь для отправки через основной генератор
                            await advisor_queue.put(event)
                            logger.info(f"💡 FastAdvisor совет: {response.advice[:100]}... (уверенность: {response.confidence:.2f})")
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка отправки совета FastAdvisor: {e}")
                    
                    # Запускаем консультацию в фоне (не блокирует основной процесс)
                    advisor_task = asyncio.create_task(
                        advisor.consult_async(advisor_request, callback=send_advisor_suggestion)
                    )
                    logger.info("🚀 FastAdvisor консультация запущена в фоне")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось запустить FastAdvisor: {e}")
            else:
                advisor_queue = None
            
            # Выбираем обработчик в зависимости от режима
            if selected_mode == "chat":
                stream_func = run_chat_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    conversation_id=conversation_id,
                    task_complexity=detected_complexity,
                    intent_type=detected_intent_type,
                    disable_web_search=disable_web_search
                )
            elif detected_intent_type == "analyze" or selected_mode == "analyze":
                # Режим анализа проекта — собираем контекст и генерируем отчёт
                stream_func = run_analyze_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    project_path=project_path,
                    file_extensions=parsed_extensions,
                    conversation_id=conversation_id
                )
            else:  # code или другой режим с workflow
                # Теперь workflow граф сам выбирает стриминговые узлы на основе флага
                # Поэтому всегда используем run_workflow_stream (граф сам решит)
                logger.info("🔄 Используем унифицированный workflow граф (стриминг определяется автоматически)")
                stream_func = run_workflow_stream(
                    task=task,
                    model=model,
                    temperature=temperature,
                    disable_web_search=disable_web_search,
                    max_iterations=max_iterations,
                    project_path=project_path,
                    file_extensions=parsed_extensions
                )
            
            async for event in stream_func:
                event_count += 1
                # ОПТИМИЗАЦИЯ: Логируем только периодически (каждые 10 событий) для уменьшения объема логов
                if event_count % 10 == 0:
                    logger.debug(f"📤 [generate] Отправлено событий: {event_count}, текущее: длина {len(event)}")
                
                yield event
                # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга thinking блоков
                # await asyncio.sleep(0.01)
                
                # Проверяем и отправляем советы FastAdvisor если есть (не блокируя основной поток)
                if advisor_queue is not None:
                    try:
                        while not advisor_queue.empty():
                            advisor_event = advisor_queue.get_nowait()
                            event_count += 1
                            logger.info(f"💡 [generate] Отправляю совет FastAdvisor #{event_count}")
                            yield advisor_event
                    except asyncio.QueueEmpty:
                        pass
            
            # Отправляем оставшиеся советы FastAdvisor после завершения основного потока
            if advisor_queue is not None:
                try:
                    while not advisor_queue.empty():
                        advisor_event = advisor_queue.get_nowait()
                        event_count += 1
                        # ОПТИМИЗАЦИЯ: Логируем только на DEBUG уровне
                        logger.debug(f"💡 [generate] Отправляю оставшийся совет FastAdvisor #{event_count}")
                        yield advisor_event
                except asyncio.QueueEmpty:
                    pass
            
            # Ждём завершения фоновой консультации FastAdvisor (если была запущена)
            if advisor_task and not advisor_task.done():
                try:
                    await asyncio.wait_for(advisor_task, timeout=1.0)  # Даём 1 секунду на завершение
                except asyncio.TimeoutError:
                    logger.debug("⏱️ FastAdvisor консультация ещё не завершена, продолжаем")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка в FastAdvisor задаче: {e}")
            
            logger.info(f"✅ [generate] Всего отправлено событий: {event_count}")
            # ОПТИМИЗАЦИЯ: Убрана критическая задержка - завершение должно быть мгновенным
            # await ui_sleep("critical")
            logger.info("✅ [generate] Генератор завершен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в generate(): {e}", error=e)
            error_event = await SSEManager.stream_error(
                stage="workflow",
                error_message=f"Ошибка выполнения: {str(e)}"
            )
            yield error_event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "*"
        }
    )


@router.get("/improvements")
async def get_improvement_suggestions(
    min_confidence: float = 1.0
) -> Dict[str, Any]:
    """Возвращает накопленные предложения по улучшению проекта от Autonomous Improver.
    
    Args:
        min_confidence: Минимальная уверенность (0.0-1.0, по умолчанию 1.0 = только 100%)
        
    Returns:
        Словарь с предложениями
    """
    try:
        from infrastructure.autonomous_improver import get_autonomous_improver
        
        improver = get_autonomous_improver()
        suggestions = improver.get_suggestions(min_confidence=min_confidence)
        
        return {
            "suggestions": [
                {
                    "type": s.type.value,
                    "file_path": s.file_path,
                    "description": s.description,
                    "suggestion": s.suggestion,
                    "confidence": s.confidence,
                    "priority": s.priority,
                    "reasoning": s.reasoning,
                    "estimated_impact": s.estimated_impact,
                    "code_example": s.code_example,
                    "metadata": s.metadata
                }
                for s in suggestions
            ],
            "count": len(suggestions),
            "min_confidence": min_confidence
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения предложений: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/improvements/metrics")
async def get_improvement_metrics() -> Dict[str, Any]:
    """Возвращает метрики эффективности Autonomous Improver.
    
    Returns:
        Словарь с метриками работы модуля
    """
    try:
        from infrastructure.autonomous_improver import get_autonomous_improver
        
        improver = get_autonomous_improver()
        metrics = improver.get_metrics()
        
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения метрик: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/improvements/clear")
async def clear_improvement_suggestions() -> Dict[str, str]:
    """Очищает накопленные предложения по улучшению проекта."""
    try:
        from infrastructure.autonomous_improver import get_autonomous_improver
        
        improver = get_autonomous_improver()
        improver.clear_suggestions()
        
        return {"status": "success", "message": "Предложения очищены"}
    except Exception as e:
        logger.error(f"❌ Ошибка очистки предложений: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


class FeedbackRequest(BaseModel):
    """Запрос на сохранение feedback."""
    task: str = Field(..., description="Текст задачи")
    task_id: Optional[str] = Field(None, description="ID задачи (если есть)")
    feedback: str = Field(..., description="Тип feedback: positive или negative")


@router.post("/feedback")
async def save_feedback(request: FeedbackRequest) -> Dict[str, str]:
    """Сохраняет feedback пользователя для задачи.
    
    Args:
        request: Запрос с задачей и типом feedback
        
    Returns:
        Статус сохранения
    """
    memory_agent = _get_memory_agent()
    
    if request.feedback not in ["positive", "negative"]:
        raise HTTPException(status_code=400, detail="feedback должен быть 'positive' или 'negative'")
    
    # Создаём фиктивный ReflectionResult для сохранения feedback
    # В реальности лучше хранить task_id и обновлять существующую запись
    fake_reflection = ReflectionResult(
        planning_score=0.0,
        research_score=0.0,
        testing_score=0.0,
        coding_score=0.0,
        overall_score=1.0 if request.feedback == "positive" else 0.0,
        analysis=f"Feedback пользователя: {request.feedback}",
        improvements="",
        should_retry=False
    )
    
    memory_agent.save_task_experience(
        task=request.task,
        intent_type="unknown",  # Не знаем intent для feedback
        reflection_result=fake_reflection,
        feedback=request.feedback,
        code="",  # Нет кода для feedback
        plan=""  # Нет плана для feedback
    )
    
    return {
        "status": "success",
        "message": f"Feedback '{request.feedback}' сохранён"
    }


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Возвращает текущие настройки системы.
    
    Returns:
        Словарь с настройками
    """
    config = get_config()
    
    return {
        "interaction": {
            "default_mode": config.interaction_default_mode,
            "auto_confirm": config.interaction_auto_confirm,
            "show_thinking": config.interaction_show_thinking,
            "max_context_messages": config.interaction_max_context_messages,
            "persist_conversations": config.interaction_persist_conversations,
            "chat_model": config.chat_model,
            "chat_model_fallback": config.chat_model_fallback
        },
        "llm": {
            "default_model": config.default_model,
            "temperature": config.temperature,
            "tokens_chat": config.llm_tokens_chat,
            "tokens_code": config.llm_tokens_code
        },
        "quality": {
            "threshold": config.quality_threshold,
            "confidence_threshold": config.confidence_threshold
        },
        "web_search": {
            "enabled": config.enable_web,
            "timeout": config.web_search_timeout
        },
        "modes": [
            {"id": "auto", "name": "Авто", "description": "Автоматический выбор режима"},
            {"id": "chat", "name": "Диалог", "description": "Простое общение без генерации кода"},
            {"id": "code", "name": "Генерация", "description": "Полный workflow с тестами и кодом"}
        ]
    }


def _get_conversation_title(messages: list) -> str:
    """Генерирует заголовок диалога из первого сообщения пользователя.
    
    Args:
        messages: Список сообщений диалога
        
    Returns:
        Заголовок диалога (до 50 символов)
    """
    # Ищем первое сообщение пользователя
    for msg in messages:
        if msg.role == "user":
            text = msg.content.strip()
            # Убираем markdown разметку
            text = re.sub(r'[#*_`~\[\]()>]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            # Обрезаем до 50 символов
            if len(text) > 50:
                return text[:47] + '...'
            return text if text else 'Новый диалог'
    return 'Новый диалог'


@router.get("/conversations")
async def list_conversations() -> Dict[str, Any]:
    """Возвращает список диалогов.
    
    Returns:
        Список диалогов с метаданными
    """
    conv_memory = get_conversation_memory()
    
    conversations = []
    for conv_id, conv in conv_memory.conversations.items():
        # Заголовок — первое сообщение пользователя
        title = _get_conversation_title(conv.messages)
        
        # Preview — последнее сообщение (для поиска)
        preview = ""
        if conv.messages:
            last_msg = conv.messages[-1].content[:100]
            # Убираем markdown из preview тоже
            preview = re.sub(r'[#*_`~\[\]()>]', '', last_msg)
            preview = re.sub(r'\s+', ' ', preview).strip()
        
        conversations.append({
            "id": conv_id,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": len(conv.messages),
            "has_summary": conv.summary is not None,
            "preview": preview,
            "title": title  # Новое поле — заголовок диалога
        })
    
    # Сортируем по дате обновления (новые первые)
    conversations.sort(key=lambda x: str(x["updated_at"]), reverse=True)  # type: ignore[arg-type]  # conversations содержит dict с ключом "updated_at", str() гарантирует строку для сортировки
    
    return {
        "conversations": conversations,
        "total": len(conversations)
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Возвращает детали диалога.
    
    Args:
        conversation_id: ID диалога
        
    Returns:
        Данные диалога с сообщениями
    """
    conv_memory = get_conversation_memory()
    
    if conversation_id not in conv_memory.conversations:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    conv = conv_memory.conversations[conversation_id]
    
    return {
        "id": conv.id,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "summary": conv.summary,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata
            }
            for msg in conv.messages
        ]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict[str, str]:
    """Удаляет диалог.
    
    Args:
        conversation_id: ID диалога
        
    Returns:
        Статус удаления
    """
    conv_memory = get_conversation_memory()
    
    if not conv_memory.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    
    return {
        "status": "success",
        "message": f"Диалог {conversation_id} удалён"
    }


@router.post("/conversations/new")
async def create_conversation() -> Dict[str, str]:
    """Создаёт новый диалог.
    
    Returns:
        ID нового диалога
    """
    conv_memory = get_conversation_memory()
    conv = conv_memory.get_or_create_conversation()
    
    return {
        "conversation_id": conv.id,
        "status": "created"
    }


# ========== TASK PERSISTENCE ENDPOINTS ==========

from infrastructure.task_checkpointer import get_task_checkpointer, TaskMetadata


@router.get("/tasks/active")
async def get_active_tasks() -> Dict[str, Any]:
    """Возвращает список активных (незавершенных) задач.
    
    Используется frontend для восстановления после обновления страницы.
    
    Returns:
        Список активных задач с метаданными
    """
    config = get_config()
    
    if not config.persistence_enabled:
        return {
            "tasks": [],
            "total": 0,
            "persistence_enabled": False
        }
    
    checkpointer = get_task_checkpointer()
    active_tasks = checkpointer.list_active_tasks()
    
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_text": t.task_text,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "last_stage": t.last_stage,
                "status": t.status,
                "iteration": t.iteration,
                "model": t.model
            }
            for t in active_tasks
        ],
        "total": len(active_tasks),
        "persistence_enabled": True
    }


@router.get("/tasks/history")
async def get_task_history(limit: int = 20) -> Dict[str, Any]:
    """Возвращает историю всех задач.
    
    Args:
        limit: Максимальное количество задач
        
    Returns:
        Список всех задач с метаданными
    """
    config = get_config()
    
    if not config.persistence_enabled:
        return {
            "tasks": [],
            "total": 0,
            "persistence_enabled": False
        }
    
    checkpointer = get_task_checkpointer()
    all_tasks = checkpointer.list_all_tasks()[:limit]
    
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_text": t.task_text,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "last_stage": t.last_stage,
                "status": t.status,
                "iteration": t.iteration,
                "model": t.model
            }
            for t in all_tasks
        ],
        "total": len(all_tasks),
        "persistence_enabled": True
    }


@router.get("/tasks/{task_id}")
async def get_task_details(task_id: str) -> Dict[str, Any]:
    """Возвращает детали задачи включая сохраненное состояние.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Детали задачи с результатами
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    result = checkpointer.load_checkpoint(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    state, metadata = result
    
    return {
        "task_id": metadata.task_id,
        "task_text": metadata.task_text,
        "created_at": metadata.created_at,
        "updated_at": metadata.updated_at,
        "last_stage": metadata.last_stage,
        "status": metadata.status,
        "iteration": metadata.iteration,
        "model": metadata.model,
        "results": {
            "intent": state.get("intent_result"),
            "plan": state.get("plan", ""),
            "context": state.get("context", "")[:500] + "..." if len(state.get("context", "")) > 500 else state.get("context", ""),
            "tests": state.get("tests", ""),
            "code": state.get("code", ""),
            "validation": state.get("validation_results", {}),
        }
    }


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """Возобновляет выполнение приостановленной задачи.
    
    Args:
        task_id: ID задачи для возобновления
        
    Returns:
        StreamingResponse с SSE событиями продолжения workflow
    """
    from fastapi.responses import StreamingResponse
    
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    result = checkpointer.load_checkpoint(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    state, metadata = result
    
    # Проверяем что задачу можно возобновить
    if metadata.status == "completed":
        raise HTTPException(status_code=400, detail="Задача уже завершена")
    
    async def generate() -> AsyncGenerator[str, None]:
        """Генератор SSE событий для возобновления задачи."""
        try:
            # Определяем следующий этап на основе last_stage
            stage_order = [
                "intent", "planner", "researcher", "test_generator",
                "coder", "validator", "debugger", "fixer", "reflection", "critic"
            ]
            
            last_stage = metadata.last_stage
            
            # Находим индекс последнего завершенного этапа
            if last_stage in stage_order:
                last_index = stage_order.index(last_stage)
            else:
                last_index = -1
            
            # Отправляем событие о возобновлении
            yield await SSEManager.stream_stage_start(
                stage="resume",
                message=f"Возобновление с этапа: {last_stage}"
            )
            # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
            # await asyncio.sleep(0.05)
            
            # Отправляем сохраненные результаты
            if state.get("intent_result"):
                intent_data = state["intent_result"]
                if isinstance(intent_data, dict):
                    yield await SSEManager.stream_stage_end(
                        stage="intent",
                        message=f"Намерение: {intent_data.get('type', 'unknown')}",
                        result=intent_data
                    )
                await ui_sleep()
            
            if state.get("plan"):
                yield await SSEManager.stream_stage_end(
                    stage="planning",
                    message="План восстановлен",
                    result={"plan_length": len(state["plan"])}
                )
                await ui_sleep()
            
            if state.get("context"):
                yield await SSEManager.stream_stage_end(
                    stage="research",
                    message="Контекст восстановлен",
                    result={"context_length": len(state["context"])}
                )
                # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
                # await ui_sleep()
            
            if state.get("tests"):
                yield await SSEManager.stream_stage_end(
                    stage="testing",
                    message="Тесты восстановлены",
                    result={"tests_length": len(state["tests"])}
                )
                # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
                # await ui_sleep()
            
            if state.get("code"):
                yield await SSEManager.stream_stage_end(
                    stage="coding",
                    message="Код восстановлен",
                    result={"code_length": len(state["code"]), "code": state["code"]}
                )
                # Отправляем код как chunk для IDE
                yield await SSEManager.stream_code_chunk(
                    chunk=state["code"],
                    is_final=True,
                    metadata={"stage": "resume"}
                )
                # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
                # await ui_sleep()
            
            if state.get("validation_results"):
                yield await SSEManager.stream_stage_end(
                    stage="validation",
                    message="Валидация восстановлена",
                    result=state["validation_results"]
                )
                # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
                # await ui_sleep()
            
            # Определяем нужно ли продолжать workflow
            validation = state.get("validation_results", {})
            all_passed = validation.get("all_passed", False)
            iteration = state.get("iteration", 0)
            max_iterations = state.get("max_iterations", 3)
            
            # Если задача не завершена, продолжаем workflow
            if last_index < len(stage_order) - 1:
                # Продолжаем workflow с загруженным state
                # Извлекаем параметры из state
                task = state.get("task", "")
                model = state.get("model", "")
                temperature = state.get("temperature", 0.25)
                disable_web_search = state.get("disable_web_search", False)
                max_iterations = state.get("max_iterations", 3)
                project_path = state.get("project_path")
                file_extensions = state.get("file_extensions")
                
                # Создаём граф
                graph = create_workflow_graph()
                
                # Создаём очередь для SSE событий
                sse_queue: asyncio.Queue = asyncio.Queue()
                
                # Создаём WorkflowStreamer
                streamer = WorkflowStreamer(
                    task=task,
                    task_id=task_id,
                    sse_queue=sse_queue,
                    initial_state=state
                )
                
                # Запускаем граф с загруженным state
                # Граф сам определит, какие ноды нужно выполнить на основе условных переходов
                async for event in graph.astream(state):
                    # Обрабатываем события графа
                    for node_name, node_state in event.items():
                        # Используем WorkflowStreamer для обработки нодов
                        should_stop = False
                        async for sse_event in streamer.handle_node(
                            node_name=node_name,
                            node_state=node_state,
                            greeting_message=GREETING_MESSAGE,
                            help_message=HELP_MESSAGE
                        ):
                            if sse_event == "__STOP_WORKFLOW__":
                                should_stop = True
                                break
                            yield sse_event
                        
                        if should_stop:
                            break
                    
                    if should_stop:
                        break
            else:
                # Задача уже завершена, отправляем финальный результат
                reflection = state.get("reflection_result")
                if isinstance(reflection, dict):
                    metrics = {
                        "planning": reflection.get("planning_score", 0.0),
                        "research": reflection.get("research_score", 0.0),
                        "testing": reflection.get("testing_score", 0.0),
                        "coding": reflection.get("coding_score", 0.0),
                        "overall": reflection.get("overall_score", 0.0)
                    }
                else:
                    metrics = {
                        "planning": 0.0,
                        "research": 0.0,
                        "testing": 0.0,
                        "coding": 0.0,
                        "overall": 0.0
                    }
                
                intent_data = state.get("intent_result", {})
                if isinstance(intent_data, dict):
                    intent_for_result = {
                        "type": intent_data.get("type", "unknown"),
                        "confidence": intent_data.get("confidence", 0.0),
                        "description": intent_data.get("description", "")
                    }
                else:
                    intent_for_result = {"type": "unknown", "confidence": 0.0, "description": ""}
                
                yield await SSEManager.stream_final_result(
                    task_id=task_id,
                    results={
                        "task": state.get("task", ""),
                        "intent": intent_for_result,
                        "plan": state.get("plan", ""),
                        "context": state.get("context", ""),
                        "tests": state.get("tests", ""),
                        "code": state.get("code", ""),
                        "validation": validation,
                        "resumed": True,
                        "last_stage": last_stage
                    },
                    metrics=metrics
                )
            
            # ОПТИМИЗАЦИЯ: Убрана критическая задержка - завершение должно быть мгновенным
            # await ui_sleep("critical")
            logger.info(f"✅ Задача {task_id[:8]}... возобновлена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка возобновления задачи: {e}", error=e)
            yield await SSEManager.stream_error(
                stage="resume",
                error_message=f"Ошибка возобновления: {str(e)}"
            )
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "http://localhost:5173",
            "Access-Control-Allow-Credentials": "true"
        }
    )


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> Dict[str, str]:
    """Удаляет checkpoint задачи.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Статус удаления
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    
    if not checkpointer.delete_checkpoint(task_id):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    return {
        "status": "success",
        "message": f"Задача {task_id} удалена"
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """Отменяет/приостанавливает задачу.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Статус отмены
    """
    config = get_config()
    
    if not config.persistence_enabled:
        raise HTTPException(status_code=400, detail="Persistence отключена")
    
    checkpointer = get_task_checkpointer()
    checkpointer.mark_paused(task_id)
    
    return {
        "status": "success",
        "message": f"Задача {task_id} приостановлена"
    }
