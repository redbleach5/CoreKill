"""API endpoints для управления базами данных."""
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from infrastructure.database_manager import DatabaseManager
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/databases", tags=["databases"])


class BackupRequest(BaseModel):
    """Запрос на создание бэкапа."""
    database: Optional[str] = None  # Если None, бэкап всех БД
    name: Optional[str] = None  # Имя бэкапа (опционально)


class RestoreRequest(BaseModel):
    """Запрос на восстановление."""
    backup_path: str
    target_database: Optional[str] = None


class CleanupRequest(BaseModel):
    """Запрос на очистку."""
    database: str
    days: int = 30
    execute: bool = False  # Если False, только dry run


@router.get("/list")
async def list_databases() -> Dict[str, Any]:
    """Получает список всех БД в системе.
    
    Returns:
        Список БД с информацией о размере и количестве записей
    """
    try:
        manager = DatabaseManager()
        databases = manager.discover_databases()
        
        return {
            "status": "success",
            "count": len(databases),
            "databases": [
                {
                    "name": db.name,
                    "type": db.type,
                    "path": str(db.path),
                    "size_bytes": db.size_bytes,
                    "size_formatted": manager._format_size(db.size_bytes),
                    "record_count": db.record_count,
                    "collections": db.collections,
                    "last_modified": db.last_modified.isoformat() if db.last_modified else None
                }
                for db in databases
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка получения списка БД: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics() -> Dict[str, Any]:
    """Получает статистику по всем БД.
    
    Returns:
        Статистика по размерам, количеству записей и т.д.
    """
    try:
        manager = DatabaseManager()
        stats = manager.get_statistics()
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backup")
async def create_backup(request: BackupRequest) -> Dict[str, Any]:
    """Создаёт резервную копию БД.
    
    Args:
        request: Параметры бэкапа
        
    Returns:
        Информация о созданном бэкапе
    """
    try:
        manager = DatabaseManager()
        
        if request.database:
            # Бэкап конкретной БД
            backup_path = manager.backup_database(request.database, request.name)
            return {
                "status": "success",
                "message": f"Бэкап {request.database} создан",
                "backup_path": str(backup_path),
                "database": request.database
            }
        else:
            # Бэкап всех БД
            databases = manager.discover_databases()
            if not databases:
                return {
                    "status": "success",
                    "message": "БД не найдены",
                    "backups": []
                }
            
            backups = []
            for db in databases:
                try:
                    backup_path = manager.backup_database(db.name)
                    backups.append({
                        "database": db.name,
                        "backup_path": str(backup_path)
                    })
                except Exception as e:
                    logger.warning(f"Ошибка бэкапа {db.name}: {e}")
                    backups.append({
                        "database": db.name,
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "message": f"Создано {len(backups)} бэкапов",
                "backups": backups
            }
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore")
async def restore_database(request: RestoreRequest) -> Dict[str, Any]:
    """Восстанавливает БД из бэкапа.
    
    Args:
        request: Параметры восстановления
        
    Returns:
        Результат восстановления
    """
    try:
        manager = DatabaseManager()
        backup_path = Path(request.backup_path)
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Бэкап не найден: {backup_path}")
        
        manager.restore_database(backup_path, request.target_database)
        
        return {
            "status": "success",
            "message": f"БД восстановлена из {backup_path}",
            "backup_path": str(backup_path),
            "target_database": request.target_database
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка восстановления БД: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_database(request: CleanupRequest) -> Dict[str, Any]:
    """Очищает старые данные из БД.
    
    Args:
        request: Параметры очистки
        
    Returns:
        Статистика очистки
    """
    try:
        manager = DatabaseManager()
        
        if not request.execute:
            logger.info(f"DRY RUN очистки {request.database}")
        
        stats = manager.cleanup_old_data(
            request.database,
            days=request.days,
            dry_run=not request.execute
        )
        
        return {
            "status": "success",
            "dry_run": not request.execute,
            "message": "Очистка завершена" if request.execute else "DRY RUN: показано что будет удалено",
            **stats
        }
    except Exception as e:
        logger.error(f"Ошибка очистки БД: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backups")
async def list_backups() -> Dict[str, Any]:
    """Получает список всех бэкапов.
    
    Returns:
        Список бэкапов с метаданными
    """
    try:
        manager = DatabaseManager()
        backups = []
        
        if not manager.backup_dir.exists():
            return {
                "status": "success",
                "backups": []
            }
        
        # Ищем все директории и файлы в backup_dir
        for item in manager.backup_dir.iterdir():
            if item.is_dir() or item.suffix in [".db", ".sqlite", ".sqlite3"]:
                # Проверяем наличие метаданных
                metadata_path = manager.backup_dir / f"{item.name}.metadata.json"
                if metadata_path.exists():
                    try:
                        import json
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        backups.append({
                            "name": item.name,
                            "path": str(item),
                            "size_bytes": item.stat().st_size if item.is_file() else sum(f.stat().st_size for f in item.rglob("*") if f.is_file()),
                            "created_at": metadata.get("created_at"),
                            "database": metadata.get("db_name"),
                            "database_type": metadata.get("db_type")
                        })
                    except Exception as e:
                        logger.warning(f"Ошибка чтения метаданных {metadata_path}: {e}")
        
        # Сортируем по дате создания (новые первыми)
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "status": "success",
            "count": len(backups),
            "backups": backups
        }
    except Exception as e:
        logger.error(f"Ошибка получения списка бэкапов: {e}", error=e)
        raise HTTPException(status_code=500, detail=str(e))
