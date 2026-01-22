#!/usr/bin/env python3
"""CLI для управления базами данных системы."""
import sys
import argparse
from pathlib import Path
from typing import Optional

from infrastructure.database_manager import DatabaseManager
from utils.logger import get_logger

logger = get_logger()


def cmd_list(args: argparse.Namespace) -> None:
    """Команда: список всех БД."""
    manager = DatabaseManager()
    databases = manager.discover_databases()
    
    if not databases:
        print("📭 Базы данных не найдены")
        return
    
    print("\n📊 Найденные базы данных:\n")
    print(f"{'Имя':<30} {'Тип':<15} {'Размер':<15} {'Записей':<10} {'Путь'}")
    print("-" * 100)
    
    for db in databases:
        size_str = manager._format_size(db.size_bytes)
        count_str = str(db.record_count) if db.record_count else "-"
        print(f"{db.name:<30} {db.type:<15} {size_str:<15} {count_str:<10} {db.path}")
    
    print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Команда: статистика по всем БД."""
    manager = DatabaseManager()
    stats = manager.get_statistics()
    
    print("\n📈 Статистика баз данных:\n")
    print(f"Всего БД: {stats['total_databases']}")
    print(f"Общий размер: {stats['total_size_formatted']}")
    print(f"Всего записей: {stats['total_records']:,}" if stats['total_records'] else "Всего записей: -")
    
    print("\nПо типам:")
    for db_type, type_stats in stats['by_type'].items():
        print(f"  {db_type}: {type_stats['count']} БД, {type_stats['total_size_formatted']}")
    
    print()


def cmd_backup(args: argparse.Namespace) -> None:
    """Команда: создание бэкапа."""
    manager = DatabaseManager()
    
    if args.all:
        # Бэкап всех БД
        databases = manager.discover_databases()
        if not databases:
            print("📭 Базы данных не найдены")
            return
        
        print(f"\n📦 Создаю бэкапы всех БД ({len(databases)} шт.)...\n")
        
        for db in databases:
            try:
                backup_path = manager.backup_database(db.name)
                print(f"✅ {db.name}: {backup_path}")
            except Exception as e:
                print(f"❌ {db.name}: ошибка - {e}")
        
        print(f"\n✅ Все бэкапы сохранены в: {manager.backup_dir}")
    else:
        # Бэкап конкретной БД
        if not args.database:
            print("❌ Укажите имя БД или используйте --all")
            return
        
        try:
            backup_path = manager.backup_database(args.database, args.name)
            print(f"\n✅ Бэкап создан: {backup_path}")
        except Exception as e:
            print(f"❌ Ошибка создания бэкапа: {e}")
            sys.exit(1)


def cmd_restore(args: argparse.Namespace) -> None:
    """Команда: восстановление из бэкапа."""
    manager = DatabaseManager()
    
    if not args.backup:
        print("❌ Укажите путь к бэкапу")
        sys.exit(1)
    
    backup_path = Path(args.backup)
    if not backup_path.exists():
        print(f"❌ Бэкап не найден: {backup_path}")
        sys.exit(1)
    
    try:
        manager.restore_database(backup_path, args.database)
        print(f"\n✅ БД восстановлена из {backup_path}")
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        sys.exit(1)


def cmd_cleanup(args: argparse.Namespace) -> None:
    """Команда: очистка старых данных."""
    manager = DatabaseManager()
    
    if not args.database:
        print("❌ Укажите имя БД")
        sys.exit(1)
    
    dry_run = not args.execute
    
    if dry_run:
        print(f"\n🧹 DRY RUN: Показываю что будет удалено из {args.database} (старше {args.days} дней)\n")
    else:
        print(f"\n🧹 Очищаю {args.database} (данные старше {args.days} дней)\n")
    
    try:
        stats = manager.cleanup_old_data(args.database, days=args.days, dry_run=dry_run)
        
        print(f"Удалено записей: {stats['deleted_count']}")
        print(f"Освобождено: {manager._format_size(stats['freed_bytes'])}")
        
        if dry_run:
            print("\n⚠️ Это был DRY RUN. Для реального удаления используйте --execute")
    except Exception as e:
        print(f"❌ Ошибка очистки: {e}")
        sys.exit(1)


def main() -> None:
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Управление базами данных системы",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Список всех БД
  python -m utils.db_cli list
  
  # Статистика
  python -m utils.db_cli stats
  
  # Бэкап конкретной БД
  python -m utils.db_cli backup chromadb:task_memory
  
  # Бэкап всех БД
  python -m utils.db_cli backup --all
  
  # Восстановление
  python -m utils.db_cli restore --backup output/backups/chromadb_task_memory_20260121_120000
  
  # Очистка (dry run)
  python -m utils.db_cli cleanup json:conversations --days 30
  
  # Очистка (реальное удаление)
  python -m utils.db_cli cleanup json:conversations --days 30 --execute
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # list
    subparsers.add_parser("list", help="Список всех БД")
    
    # stats
    subparsers.add_parser("stats", help="Статистика по всем БД")
    
    # backup
    backup_parser = subparsers.add_parser("backup", help="Создание бэкапа")
    backup_parser.add_argument("database", nargs="?", help="Имя БД (например, chromadb:task_memory)")
    backup_parser.add_argument("--name", help="Имя бэкапа (по умолчанию генерируется)")
    backup_parser.add_argument("--all", action="store_true", help="Бэкап всех БД")
    
    # restore
    restore_parser = subparsers.add_parser("restore", help="Восстановление из бэкапа")
    restore_parser.add_argument("--backup", required=True, help="Путь к бэкапу")
    restore_parser.add_argument("--database", help="Имя целевой БД (по умолчанию из метаданных)")
    
    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Очистка старых данных")
    cleanup_parser.add_argument("database", help="Имя БД")
    cleanup_parser.add_argument("--days", type=int, default=30, help="Удалить данные старше N дней (по умолчанию 30)")
    cleanup_parser.add_argument("--execute", action="store_true", help="Реально удалить (по умолчанию dry run)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Выполняем команду
    commands = {
        "list": cmd_list,
        "stats": cmd_stats,
        "backup": cmd_backup,
        "restore": cmd_restore,
        "cleanup": cmd_cleanup
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
