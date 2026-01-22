"""Система управления базами данных проекта.

Управляет всеми БД, которые возникают в процессе работы:
- ChromaDB (RAG, память задач)
- SQLite (если используется)
- JSON файлы (диалоги)
- Кэши

Функции:
- Инициализация БД
- Резервное копирование
- Восстановление
- Очистка старых данных
- Мониторинг размера
"""
import os
import shutil
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib

from utils.logger import get_logger
from utils.config import get_config

logger = get_logger()


@dataclass
class DatabaseInfo:
    """Информация о базе данных."""
    name: str
    type: str  # "chromadb", "sqlite", "json", "cache"
    path: Path
    size_bytes: int
    collections: Optional[List[str]] = None  # Для ChromaDB
    last_modified: Optional[datetime] = None
    record_count: Optional[int] = None


class DatabaseManager:
    """Менеджер для управления всеми БД системы."""
    
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """Инициализация менеджера БД.
        
        Args:
            base_dir: Базовая директория проекта (по умолчанию текущая)
        """
        self.base_dir = base_dir or Path.cwd()
        self.config = get_config()
        
        # Пути к БД
        self.chromadb_dir = self.base_dir / self.config.rag_persist_directory
        self.conversations_dir = self.base_dir / "output" / "conversations"
        self.context_cache_dir = self.base_dir / self.config.context_engine_cache_directory
        self.learning_db_path = self.base_dir / "output" / "learning.db"
        
        # Директория для бэкапов
        self.backup_dir = self.base_dir / "output" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_databases(self) -> List[DatabaseInfo]:
        """Обнаруживает все БД в системе.
        
        Returns:
            Список информации о найденных БД
        """
        databases: List[DatabaseInfo] = []
        
        # ChromaDB
        if self.chromadb_dir.exists():
            chroma_dbs = self._discover_chromadb()
            databases.extend(chroma_dbs)
        
        # SQLite
        sqlite_dbs = self._discover_sqlite()
        databases.extend(sqlite_dbs)
        
        # JSON файлы (диалоги)
        json_dbs = self._discover_json_conversations()
        databases.extend(json_dbs)
        
        # Кэши
        cache_dbs = self._discover_caches()
        databases.extend(cache_dbs)
        
        return databases
    
    def _discover_chromadb(self) -> List[DatabaseInfo]:
        """Обнаруживает ChromaDB коллекции."""
        databases: List[DatabaseInfo] = []
        
        if not self.chromadb_dir.exists():
            return databases
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=str(self.chromadb_dir),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Получаем все коллекции
            collections = client.list_collections()
            
            for collection in collections:
                collection_name = collection.name
                collection_path = self.chromadb_dir / collection_name
                
                # Подсчитываем размер
                size = self._get_directory_size(collection_path) if collection_path.exists() else 0
                
                # Получаем количество записей
                try:
                    count = collection.count()
                except Exception:
                    count = None
                
                databases.append(DatabaseInfo(
                    name=f"chromadb:{collection_name}",
                    type="chromadb",
                    path=collection_path,
                    size_bytes=size,
                    collections=[collection_name],
                    record_count=count
                ))
            
            # Также добавляем общую ChromaDB директорию
            total_size = self._get_directory_size(self.chromadb_dir)
            databases.append(DatabaseInfo(
                name="chromadb:main",
                type="chromadb",
                path=self.chromadb_dir,
                size_bytes=total_size,
                collections=[c.name for c in collections] if collections else []
            ))
            
        except ImportError:
            logger.warning("ChromaDB не установлен, пропускаем")
        except Exception as e:
            logger.error(f"Ошибка обнаружения ChromaDB: {e}", error=e)
        
        return databases
    
    def _discover_sqlite(self) -> List[DatabaseInfo]:
        """Обнаруживает SQLite базы данных."""
        databases: List[DatabaseInfo] = []
        
        # Ищем все .db и .sqlite файлы
        for pattern in ["**/*.db", "**/*.sqlite", "**/*.sqlite3"]:
            for db_file in self.base_dir.glob(pattern):
                # Пропускаем тестовые и временные файлы
                if "test" in str(db_file) or "tmp" in str(db_file):
                    continue
                
                try:
                    size = db_file.stat().st_size
                    last_modified = datetime.fromtimestamp(db_file.stat().st_mtime)
                    
                    # Пытаемся получить количество записей
                    record_count = None
                    try:
                        conn = sqlite3.connect(str(db_file))
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = cursor.fetchall()
                        if tables:
                            # Считаем записи в первой таблице
                            cursor.execute(f"SELECT COUNT(*) FROM {tables[0][0]}")
                            record_count = cursor.fetchone()[0]
                        conn.close()
                    except Exception:
                        pass
                    
                    databases.append(DatabaseInfo(
                        name=f"sqlite:{db_file.stem}",
                        type="sqlite",
                        path=db_file,
                        size_bytes=size,
                        last_modified=last_modified,
                        record_count=record_count
                    ))
                except Exception as e:
                    logger.warning(f"Не удалось обработать SQLite файл {db_file}: {e}")
        
        return databases
    
    def _discover_json_conversations(self) -> List[DatabaseInfo]:
        """Обнаруживает JSON файлы диалогов."""
        databases: List[DatabaseInfo] = []
        
        if not self.conversations_dir.exists():
            return databases
        
        total_size = 0
        file_count = 0
        
        for json_file in self.conversations_dir.glob("*.json"):
            try:
                size = json_file.stat().st_size
                total_size += size
                file_count += 1
            except Exception:
                continue
        
        if file_count > 0:
            databases.append(DatabaseInfo(
                name="json:conversations",
                type="json",
                path=self.conversations_dir,
                size_bytes=total_size,
                record_count=file_count
            ))
        
        return databases
    
    def _discover_caches(self) -> List[DatabaseInfo]:
        """Обнаруживает кэши."""
        databases: List[DatabaseInfo] = []
        
        # Context cache
        if self.context_cache_dir.exists():
            size = self._get_directory_size(self.context_cache_dir)
            if size > 0:
                databases.append(DatabaseInfo(
                    name="cache:context",
                    type="cache",
                    path=self.context_cache_dir,
                    size_bytes=size
                ))
        
        return databases
    
    def _get_directory_size(self, path: Path) -> int:
        """Подсчитывает размер директории в байтах."""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        except Exception as e:
            logger.warning(f"Ошибка подсчёта размера {path}: {e}")
        return total
    
    def backup_database(self, db_name: str, backup_name: Optional[str] = None) -> Path:
        """Создаёт резервную копию БД.
        
        Args:
            db_name: Имя БД (например, "chromadb:task_memory")
            backup_name: Имя бэкапа (по умолчанию генерируется)
            
        Returns:
            Путь к созданному бэкапу
        """
        databases = self.discover_databases()
        db_info = next((db for db in databases if db.name == db_name), None)
        
        if not db_info:
            raise ValueError(f"БД {db_name} не найдена")
        
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{db_name.replace(':', '_')}_{timestamp}"
        
        backup_path = self.backup_dir / backup_name
        
        logger.info(f"📦 Создаю бэкап {db_name} -> {backup_path}")
        
        if db_info.type == "chromadb":
            # Копируем всю директорию ChromaDB
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(db_info.path, backup_path)
        elif db_info.type == "sqlite":
            # Копируем SQLite файл
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_info.path, backup_path)
        elif db_info.type == "json":
            # Копируем JSON директорию
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(db_info.path, backup_path)
        elif db_info.type == "cache":
            # Копируем кэш
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.copytree(db_info.path, backup_path)
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {db_info.type}")
        
        # Сохраняем метаданные бэкапа
        metadata = {
            "db_name": db_name,
            "db_type": db_info.type,
            "original_path": str(db_info.path),
            "backup_path": str(backup_path),
            "created_at": datetime.now().isoformat(),
            "size_bytes": db_info.size_bytes,
            "record_count": db_info.record_count
        }
        
        metadata_path = backup_path.parent / f"{backup_name}.metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Бэкап создан: {backup_path} ({self._format_size(db_info.size_bytes)})")
        return backup_path
    
    def restore_database(self, backup_path: Path, target_db_name: Optional[str] = None) -> None:
        """Восстанавливает БД из бэкапа.
        
        Args:
            backup_path: Путь к бэкапу
            target_db_name: Имя целевой БД (по умолчанию из метаданных)
        """
        # Загружаем метаданные
        metadata_path = backup_path.parent / f"{backup_path.name}.metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            db_name = target_db_name or metadata["db_name"]
            db_type = metadata["db_type"]
            original_path = Path(metadata["original_path"])
        else:
            # Пытаемся определить из имени файла
            raise ValueError("Метаданные бэкапа не найдены")
        
        logger.info(f"🔄 Восстанавливаю {db_name} из {backup_path}")
        
        # Создаём резервную копию текущей БД перед восстановлением
        if original_path.exists():
            logger.warning(f"⚠️ Текущая БД существует, создаю бэкап перед восстановлением")
            self.backup_database(db_name, f"{db_name}_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Восстанавливаем
        if db_type == "chromadb" or db_type == "json" or db_type == "cache":
            if original_path.exists():
                shutil.rmtree(original_path)
            original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(backup_path, original_path)
        elif db_type == "sqlite":
            original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, original_path)
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {db_type}")
        
        logger.info(f"✅ БД {db_name} восстановлена из {backup_path}")
    
    def cleanup_old_data(
        self,
        db_name: str,
        days: int = 30,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Очищает старые данные из БД.
        
        Args:
            db_name: Имя БД
            days: Удалить данные старше N дней
            dry_run: Только показать что будет удалено, не удалять
            
        Returns:
            Статистика очистки
        """
        databases = self.discover_databases()
        db_info = next((db for db in databases if db.name == db_name), None)
        
        if not db_info:
            raise ValueError(f"БД {db_name} не найдена")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        stats = {
            "db_name": db_name,
            "cutoff_date": cutoff_date.isoformat(),
            "dry_run": dry_run,
            "deleted_count": 0,
            "freed_bytes": 0
        }
        
        logger.info(f"🧹 Очистка {db_name} (данные старше {days} дней, dry_run={dry_run})")
        
        if db_info.type == "chromadb":
            stats.update(self._cleanup_chromadb(db_info, cutoff_date, dry_run))
        elif db_info.type == "json":
            stats.update(self._cleanup_json_conversations(db_info, cutoff_date, dry_run))
        elif db_info.type == "sqlite":
            stats.update(self._cleanup_sqlite(db_info, cutoff_date, dry_run))
        else:
            logger.warning(f"Очистка для типа {db_info.type} не реализована")
        
        if not dry_run:
            logger.info(f"✅ Очистка завершена: удалено {stats['deleted_count']} записей, освобождено {self._format_size(stats['freed_bytes'])}")
        else:
            logger.info(f"ℹ️ Dry run: будет удалено {stats['deleted_count']} записей, освободится {self._format_size(stats['freed_bytes'])}")
        
        return stats
    
    def _cleanup_chromadb(self, db_info: DatabaseInfo, cutoff_date: datetime, dry_run: bool) -> Dict[str, Any]:
        """Очищает старые данные из ChromaDB."""
        # ChromaDB не хранит timestamp по умолчанию, поэтому очистка сложнее
        # Пока просто возвращаем пустую статистику
        return {"deleted_count": 0, "freed_bytes": 0}
    
    def _cleanup_json_conversations(self, db_info: DatabaseInfo, cutoff_date: datetime, dry_run: bool) -> Dict[str, Any]:
        """Очищает старые JSON диалоги."""
        deleted_count = 0
        freed_bytes = 0
        
        for json_file in db_info.path.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                if mtime < cutoff_date:
                    size = json_file.stat().st_size
                    if not dry_run:
                        json_file.unlink()
                    deleted_count += 1
                    freed_bytes += size
            except Exception as e:
                logger.warning(f"Ошибка при обработке {json_file}: {e}")
        
        return {"deleted_count": deleted_count, "freed_bytes": freed_bytes}
    
    def _cleanup_sqlite(self, db_info: DatabaseInfo, cutoff_date: datetime, dry_run: bool) -> Dict[str, Any]:
        """Очищает старые данные из SQLite."""
        # Пока не реализовано - нужно знать структуру таблиц
        return {"deleted_count": 0, "freed_bytes": 0}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получает статистику по всем БД.
        
        Returns:
            Словарь со статистикой
        """
        databases = self.discover_databases()
        
        total_size = sum(db.size_bytes for db in databases)
        total_records = sum(db.record_count or 0 for db in databases if db.record_count)
        
        by_type: Dict[str, List[DatabaseInfo]] = {}
        for db in databases:
            by_type.setdefault(db.type, []).append(db)
        
        return {
            "total_databases": len(databases),
            "total_size_bytes": total_size,
            "total_size_formatted": self._format_size(total_size),
            "total_records": total_records,
            "by_type": {
                db_type: {
                    "count": len(dbs),
                    "total_size": sum(d.size_bytes for d in dbs),
                    "total_size_formatted": self._format_size(sum(d.size_bytes for d in dbs))
                }
                for db_type, dbs in by_type.items()
            },
            "databases": [
                {
                    "name": db.name,
                    "type": db.type,
                    "path": str(db.path),
                    "size_bytes": db.size_bytes,
                    "size_formatted": self._format_size(db.size_bytes),
                    "record_count": db.record_count,
                    "collections": db.collections
                }
                for db in databases
            ]
        }
    
    def _format_size(self, bytes: int) -> str:
        """Форматирует размер в читаемый вид."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"
