# Database Manager - Управление базами данных

Система управления всеми базами данных, которые возникают в процессе работы системы.

## Поддерживаемые типы БД

1. **ChromaDB** - векторная БД для RAG (память задач, кодовая база)
   - Расположение: `.chromadb/`
   - Коллекции: `task_memory`, `codebase_docs`, и другие

2. **SQLite** - реляционные БД (если используются)
   - Расположение: различные `.db`, `.sqlite`, `.sqlite3` файлы

3. **JSON файлы** - диалоги и конфигурации
   - Расположение: `output/conversations/`

4. **Кэши** - кэши индексов и других данных
   - Расположение: `.context_cache/`

## Основные функции

### 1. Обнаружение БД

Автоматически находит все БД в системе:

```python
from infrastructure.database_manager import DatabaseManager

manager = DatabaseManager()
databases = manager.discover_databases()

for db in databases:
    print(f"{db.name}: {db.type}, {db.size_bytes} bytes")
```

### 2. Резервное копирование

Создаёт полные бэкапы БД с метаданными:

```python
# Бэкап конкретной БД
backup_path = manager.backup_database("chromadb:task_memory")

# Бэкап всех БД
for db in manager.discover_databases():
    manager.backup_database(db.name)
```

Бэкапы сохраняются в `output/backups/` с метаданными в JSON.

### 3. Восстановление

Восстанавливает БД из бэкапа:

```python
from pathlib import Path

backup_path = Path("output/backups/chromadb_task_memory_20260121_120000")
manager.restore_database(backup_path)
```

Перед восстановлением автоматически создаётся бэкап текущей БД.

### 4. Очистка старых данных

Удаляет данные старше указанного количества дней:

```python
# Dry run (показывает что будет удалено)
stats = manager.cleanup_old_data("json:conversations", days=30, dry_run=True)

# Реальное удаление
stats = manager.cleanup_old_data("json:conversations", days=30, dry_run=False)
```

### 5. Статистика

Получает статистику по всем БД:

```python
stats = manager.get_statistics()

print(f"Всего БД: {stats['total_databases']}")
print(f"Общий размер: {stats['total_size_formatted']}")
print(f"Всего записей: {stats['total_records']}")
```

## CLI команды

### Список БД
```bash
python -m utils.db_cli list
```

### Статистика
```bash
python -m utils.db_cli stats
```

### Бэкап
```bash
# Конкретная БД
python -m utils.db_cli backup chromadb:task_memory

# Все БД
python -m utils.db_cli backup --all

# С указанием имени
python -m utils.db_cli backup chromadb:task_memory --name my_backup
```

### Восстановление
```bash
python -m utils.db_cli restore --backup output/backups/chromadb_task_memory_20260121_120000
```

### Очистка
```bash
# Dry run (показывает что будет удалено)
python -m utils.db_cli cleanup json:conversations --days 30

# Реальное удаление
python -m utils.db_cli cleanup json:conversations --days 30 --execute
```

## API Endpoints

### GET /api/databases/list
Список всех БД с информацией о размере и количестве записей.

### GET /api/databases/stats
Статистика по всем БД (общий размер, количество записей, разбивка по типам).

### POST /api/databases/backup
Создание бэкапа:
```json
{
  "database": "chromadb:task_memory",  // опционально, если не указано - бэкап всех
  "name": "my_backup"  // опционально
}
```

### POST /api/databases/restore
Восстановление из бэкапа:
```json
{
  "backup_path": "output/backups/chromadb_task_memory_20260121_120000",
  "target_database": "chromadb:task_memory"  // опционально
}
```

### POST /api/databases/cleanup
Очистка старых данных:
```json
{
  "database": "json:conversations",
  "days": 30,
  "execute": false  // false = dry run, true = реальное удаление
}
```

### GET /api/databases/backups
Список всех доступных бэкапов с метаданными.

## Структура бэкапов

Бэкапы сохраняются в `output/backups/` со следующей структурой:

```
output/backups/
├── chromadb_task_memory_20260121_120000/  # Директория с данными
├── chromadb_task_memory_20260121_120000.metadata.json  # Метаданные
├── sqlite_learning_20260121_120000.db
└── sqlite_learning_20260121_120000.metadata.json
```

Метаданные содержат:
- Имя БД
- Тип БД
- Путь к оригинальной БД
- Дата создания
- Размер
- Количество записей

## Рекомендации

1. **Регулярные бэкапы**: Создавайте бэкапы перед важными изменениями
2. **Очистка**: Регулярно очищайте старые диалоги (30+ дней)
3. **Мониторинг**: Следите за размером БД через `stats` команду
4. **Восстановление**: Всегда проверяйте бэкап перед восстановлением

## Ограничения

- ChromaDB: очистка по дате не реализована (нет timestamp в данных)
- SQLite: очистка требует знания структуры таблиц
- Кэши: очистка удаляет всю директорию

## Будущие улучшения

- [ ] Автоматические бэкапы по расписанию
- [ ] Сжатие бэкапов (tar.gz)
- [ ] Очистка ChromaDB по дате (требует добавления timestamp)
- [ ] Миграции БД
- [ ] Мониторинг размера с алертами
