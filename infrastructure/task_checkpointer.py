"""Система checkpoint для сохранения состояния задач.

Позволяет сохранять и восстанавливать состояние workflow после падения backend
или обновления страницы frontend.
"""
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

from infrastructure.workflow_state import AgentState
from utils.logger import get_logger


logger = get_logger()


@dataclass
class TaskMetadata:
    """Метаданные задачи для checkpoint."""
    task_id: str
    task_text: str
    created_at: str
    updated_at: str
    last_stage: str
    status: str  # "running", "paused", "completed", "failed"
    iteration: int
    model: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskMetadata":
        return cls(**data)


class TaskCheckpointer:
    """Менеджер checkpoint для сохранения состояния задач в JSON-файлы.
    
    Структура хранения:
    .task_checkpoints/
      {task_id}/
        metadata.json     # TaskMetadata
        state.json        # AgentState (сериализованный)
    """
    
    def __init__(
        self, 
        checkpoint_dir: str = ".task_checkpoints",
        max_age_hours: int = 24
    ) -> None:
        """Инициализация TaskCheckpointer.
        
        Args:
            checkpoint_dir: Директория для хранения checkpoint
            max_age_hours: Максимальный возраст checkpoint в часах (старые удаляются)
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_age_hours = max_age_hours
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Очистка старых checkpoint при инициализации
        self._cleanup_old_checkpoints()
    
    def _get_task_dir(self, task_id: str) -> Path:
        """Возвращает директорию для конкретной задачи."""
        return self.checkpoint_dir / task_id
    
    def _serialize_state(self, state: AgentState) -> dict[str, Any]:
        """Сериализует AgentState в JSON-совместимый dict.
        
        Преобразует dataclass объекты в словари.
        Защита от циклических ссылок.
        """
        result: dict[str, Any] = {}
        seen: set = set()  # Общее множество для всего state
        
        for key, value in state.items():
            if value is None:
                result[key] = None
            elif hasattr(value, "__dict__"):
                # Dataclass или объект с атрибутами
                result[key] = self._serialize_object(value, seen)
            elif isinstance(value, (list, tuple)):
                result[key] = [self._serialize_object(item, seen) for item in value]
            elif isinstance(value, dict):
                result[key] = {k: self._serialize_object(v, seen) for k, v in value.items()}
            else:
                result[key] = value
        
        return result
    
    def _serialize_object(self, obj: Any, _seen: set | None = None) -> Any:
        """Рекурсивно сериализует объект с защитой от циклических ссылок.
        
        Args:
            obj: Объект для сериализации
            _seen: Множество уже обработанных id объектов (для защиты от циклов)
        """
        from enum import Enum
        
        # Инициализируем множество обработанных объектов
        if _seen is None:
            _seen = set()
        
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # Enum — сериализуем значение
        if isinstance(obj, Enum):
            return obj.value
        
        # Проверка на циклические ссылки
        obj_id = id(obj)
        if obj_id in _seen:
            return "<circular reference>"
        
        # Добавляем в множество обработанных (только для сложных объектов)
        if hasattr(obj, "__dict__") or isinstance(obj, (dict, list, tuple)):
            _seen.add(obj_id)
        
        try:
            if hasattr(obj, "__dict__"):
                # Для dataclass и подобных
                return {k: self._serialize_object(v, _seen) for k, v in vars(obj).items()}
            if isinstance(obj, dict):
                return {k: self._serialize_object(v, _seen) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [self._serialize_object(item, _seen) for item in obj]
            # Fallback для неизвестных типов
            return str(obj)
        except RecursionError:
            return "<recursion limit>"
    
    def _serialize_state_minimal(self, state: AgentState) -> dict[str, Any]:
        """Минимальная сериализация — только простые поля для восстановления.
        
        Используется как fallback если полная сериализация не работает.
        Сохраняет достаточно данных чтобы пользователь мог продолжить задачу.
        """
        # Только строки/числа/bool — гарантированно сериализуемые
        safe_fields = [
            "task", "task_id", "max_iterations", "disable_web_search",
            "model", "temperature", "interaction_mode", "conversation_id",
            "project_path", "file_extensions", "plan", "context", 
            "tests", "code", "iteration", "file_path", "file_context"
        ]
        
        result: dict[str, Any] = {"_minimal_checkpoint": True}
        
        for field in safe_fields:
            value = state.get(field)
            if value is None:
                result[field] = None
            elif isinstance(value, (str, int, float, bool)):
                result[field] = value
            elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                result[field] = value
            else:
                # Пробуем преобразовать в строку
                try:
                    result[field] = str(value)[:10000]  # Лимит длины
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка сериализации поля {field}: {e}")
                    result[field] = None
        
        return result
    
    def _deserialize_state(self, data: dict[str, Any]) -> AgentState:
        """Десериализует JSON в AgentState.
        
        Note: Некоторые объекты (IntentResult, DebugResult и т.д.) 
        остаются словарями — это нормально, workflow_nodes обрабатывает оба варианта.
        """
        # Создаем базовый AgentState с дефолтными значениями
        state: AgentState = {
            "task": data.get("task", ""),
            "max_iterations": data.get("max_iterations", 3),
            "disable_web_search": data.get("disable_web_search", False),
            "model": data.get("model"),
            "temperature": data.get("temperature", 0.25),
            "interaction_mode": data.get("interaction_mode", "code"),
            "conversation_id": data.get("conversation_id"),
            "conversation_history": data.get("conversation_history"),
            "chat_response": data.get("chat_response"),
            "project_path": data.get("project_path"),
            "file_extensions": data.get("file_extensions"),
            "intent_result": data.get("intent_result"),
            "plan": data.get("plan", ""),
            "context": data.get("context", ""),
            "tests": data.get("tests", ""),
            "code": data.get("code", ""),
            "validation_results": data.get("validation_results", {}),
            "debug_result": data.get("debug_result"),
            "reflection_result": data.get("reflection_result"),
            "critic_report": data.get("critic_report"),
            "iteration": data.get("iteration", 0),
            "task_id": data.get("task_id", ""),
            "enable_sse": data.get("enable_sse", True),
            "file_path": data.get("file_path"),
            "file_context": data.get("file_context"),
        }
        
        return state
    
    def save_checkpoint(
        self, 
        task_id: str, 
        state: AgentState, 
        stage: str,
        status: str = "running"
    ) -> None:
        """Сохраняет checkpoint после выполнения этапа.
        
        Args:
            task_id: ID задачи
            state: Текущее состояние AgentState
            stage: Название завершенного этапа
            status: Статус задачи (running, paused, completed, failed)
        """
        task_dir = self._get_task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now().isoformat()
        
        # Загружаем существующие метаданные или создаем новые
        metadata_path = task_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                created_at = existing.get("created_at", now)
        else:
            created_at = now
        
        # Сохраняем метаданные
        metadata = TaskMetadata(
            task_id=task_id,
            task_text=state.get("task", "")[:200],  # Ограничиваем длину
            created_at=created_at,
            updated_at=now,
            last_stage=stage,
            status=status,
            iteration=state.get("iteration", 0),
            model=state.get("model")
        )
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Сохраняем состояние с fallback на минимальные данные
        state_path = task_dir / "state.json"
        
        try:
            serialized = self._serialize_state(state)
        except Exception as serialize_error:
            # Fallback: сохраняем минимум для восстановления
            logger.warning(f"⚠️ Fallback сериализация: {serialize_error}")
            serialized = self._serialize_state_minimal(state)
        
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Checkpoint сохранён: task={task_id[:8]}..., stage={stage}, status={status}")
    
    def load_checkpoint(self, task_id: str) -> tuple[AgentState, TaskMetadata] | None:
        """Загружает checkpoint для задачи.
        
        Args:
            task_id: ID задачи
            
        Returns:
            Tuple (AgentState, TaskMetadata) или None если checkpoint не найден
        """
        task_dir = self._get_task_dir(task_id)
        metadata_path = task_dir / "metadata.json"
        state_path = task_dir / "state.json"
        
        if not metadata_path.exists() or not state_path.exists():
            logger.warning(f"⚠️ Checkpoint не найден: {task_id}")
            return None
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)
            metadata = TaskMetadata.from_dict(metadata_dict)
            
            with open(state_path, "r", encoding="utf-8") as f:
                state_dict = json.load(f)
            state = self._deserialize_state(state_dict)
            
            logger.info(f"📂 Checkpoint загружен: task={task_id[:8]}..., last_stage={metadata.last_stage}")
            return state, metadata
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки checkpoint: {e}", error=e)
            return None
    
    def list_active_tasks(self) -> list[TaskMetadata]:
        """Возвращает список незавершенных задач.
        
        Returns:
            Список TaskMetadata для задач со статусом running или paused
        """
        active_tasks: list[TaskMetadata] = []
        
        if not self.checkpoint_dir.exists():
            return active_tasks
        
        for task_dir in self.checkpoint_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            metadata_path = task_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata_dict = json.load(f)
                metadata = TaskMetadata.from_dict(metadata_dict)
                
                # Включаем только активные задачи
                if metadata.status in ("running", "paused"):
                    active_tasks.append(metadata)
                    
            except Exception as e:
                logger.warning(f"⚠️ Не удалось прочитать metadata для {task_dir.name}: {e}")
                continue
        
        # Сортируем по времени обновления (новые первые)
        active_tasks.sort(key=lambda x: x.updated_at, reverse=True)
        
        return active_tasks
    
    def list_all_tasks(self) -> list[TaskMetadata]:
        """Возвращает список всех задач (включая завершенные).
        
        Returns:
            Список TaskMetadata
        """
        all_tasks: list[TaskMetadata] = []
        
        if not self.checkpoint_dir.exists():
            return all_tasks
        
        for task_dir in self.checkpoint_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            metadata_path = task_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata_dict = json.load(f)
                all_tasks.append(TaskMetadata.from_dict(metadata_dict))
            except Exception as e:
                logger.debug(f"⚠️ Ошибка загрузки метаданных задачи из {metadata_path}: {e}")
                continue
        
        all_tasks.sort(key=lambda x: x.updated_at, reverse=True)
        return all_tasks
    
    def mark_completed(self, task_id: str) -> None:
        """Помечает задачу как завершенную.
        
        Args:
            task_id: ID задачи
        """
        task_dir = self._get_task_dir(task_id)
        metadata_path = task_dir / "metadata.json"
        
        if not metadata_path.exists():
            return
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)
            
            metadata_dict["status"] = "completed"
            metadata_dict["updated_at"] = datetime.now().isoformat()
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Задача помечена как завершенная: {task_id[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить статус задачи: {e}")
    
    def mark_failed(self, task_id: str, error: str = "") -> None:
        """Помечает задачу как проваленную.
        
        Args:
            task_id: ID задачи
            error: Сообщение об ошибке
        """
        task_dir = self._get_task_dir(task_id)
        metadata_path = task_dir / "metadata.json"
        
        if not metadata_path.exists():
            return
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)
            
            metadata_dict["status"] = "failed"
            metadata_dict["updated_at"] = datetime.now().isoformat()
            if error:
                metadata_dict["error"] = error[:500]  # Ограничиваем длину
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"❌ Задача помечена как проваленная: {task_id[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить статус задачи: {e}")
    
    def mark_paused(self, task_id: str) -> None:
        """Помечает задачу как приостановленную (для возобновления).
        
        Args:
            task_id: ID задачи
        """
        task_dir = self._get_task_dir(task_id)
        metadata_path = task_dir / "metadata.json"
        
        if not metadata_path.exists():
            return
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_dict = json.load(f)
            
            metadata_dict["status"] = "paused"
            metadata_dict["updated_at"] = datetime.now().isoformat()
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"⏸️ Задача приостановлена: {task_id[:8]}...")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить статус задачи: {e}")
    
    def delete_checkpoint(self, task_id: str) -> bool:
        """Удаляет checkpoint задачи.
        
        Args:
            task_id: ID задачи
            
        Returns:
            True если удалено успешно, False если не найдено
        """
        task_dir = self._get_task_dir(task_id)
        
        if not task_dir.exists():
            return False
        
        try:
            shutil.rmtree(task_dir)
            logger.info(f"🗑️ Checkpoint удалён: {task_id[:8]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления checkpoint: {e}", error=e)
            return False
    
    def _cleanup_old_checkpoints(self) -> None:
        """Удаляет checkpoint старше max_age_hours."""
        if not self.checkpoint_dir.exists():
            return
        
        cutoff = datetime.now() - timedelta(hours=self.max_age_hours)
        removed_count = 0
        
        for task_dir in self.checkpoint_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            metadata_path = task_dir / "metadata.json"
            if not metadata_path.exists():
                # Удаляем директорию без метаданных
                try:
                    shutil.rmtree(task_dir)
                    removed_count += 1
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка удаления старого checkpoint {task_dir}: {e}")
                continue
            
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata_dict = json.load(f)
                
                updated_at = datetime.fromisoformat(metadata_dict.get("updated_at", ""))
                
                # Удаляем старые завершенные/проваленные задачи
                if updated_at < cutoff and metadata_dict.get("status") in ("completed", "failed"):
                    shutil.rmtree(task_dir)
                    removed_count += 1
                    
            except Exception as e:
                logger.debug(f"⚠️ Ошибка удаления старого checkpoint {task_dir}: {e}")
                continue
        
        if removed_count > 0:
            logger.info(f"🧹 Очищено старых checkpoint: {removed_count}")


# Глобальный экземпляр (Singleton)
_checkpointer: TaskCheckpointer | None = None


def get_task_checkpointer() -> TaskCheckpointer:
    """Возвращает глобальный TaskCheckpointer (Singleton).
    
    Returns:
        Экземпляр TaskCheckpointer
    """
    global _checkpointer
    
    if _checkpointer is None:
        from utils.config import get_config
        config = get_config()
        
        checkpoint_dir = getattr(config, "persistence_checkpoint_directory", ".task_checkpoints")
        max_age = getattr(config, "persistence_max_checkpoint_age_hours", 24)
        
        _checkpointer = TaskCheckpointer(
            checkpoint_dir=checkpoint_dir,
            max_age_hours=max_age
        )
    
    return _checkpointer


def reset_task_checkpointer() -> None:
    """Сбрасывает глобальный TaskCheckpointer (для тестов)."""
    global _checkpointer
    _checkpointer = None
