"""Тестовый скрипт для проверки Autonomous Improver.

Запускает Autonomous Improver на указанное время и собирает метрики:
- Количество найденных улучшений
- Качество предложений (уверенность, приоритет)
- Производительность (время анализа, использование ресурсов)
- Распределение по типам улучшений

Примеры использования:
    ```bash
    # Запуск на 4 часа (по умолчанию)
    python3 infrastructure/autonomous_improver/scripts/test.py
    
    # Запуск на указанное время
    python3 infrastructure/autonomous_improver/scripts/test.py --duration 8.0
    
    # Через shell скрипт
    ./infrastructure/autonomous_improver/scripts/run.sh 4.0
    ./run_improver.sh 4.0
    ```

Параметры:
    --duration: Длительность теста в часах (по умолчанию 4.0)

Результаты:
    - Логи модуля: logs/autonomous_improver.log
    - Логи теста: logs/autonomous_improver_test.log
    - Результаты: test_improver_results.json

Зависимости:
    - infrastructure.autonomous_improver: основной модуль
    - utils.config: конфигурация
    - asyncio: асинхронное выполнение

Связанные скрипты:
    - infrastructure/autonomous_improver/scripts/analyze_results.py: анализ результатов
    - infrastructure/autonomous_improver/scripts/run.sh: запуск через shell

Примечания:
    - Работает в фоновом режиме
    - Собирает метрики каждые N секунд
    - Сохраняет результаты в JSON для последующего анализа
    - Оптимизирован для работы на слабом железе
"""
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
import sys

# Добавляем корневую директорию проекта в путь
# Скрипт находится в infrastructure/autonomous_improver/scripts/
# Нужно подняться на 3 уровня вверх до корня проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.autonomous_improver import (
    get_autonomous_improver,
    AutonomousImprover,
    ImprovementSuggestion,
    ImprovementType
)
from utils.config import get_config
import logging

# Настраиваем отдельный логгер для теста
# Логи пишутся в logs/autonomous_improver_test.log (в корне проекта)
_log_file = project_root / "logs" / "autonomous_improver_test.log"
_log_file.parent.mkdir(parents=True, exist_ok=True)

# Создаём отдельный логгер с файловым хендлером
logger = logging.getLogger("autonomous_improver_test")
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Убираем существующие хендлеры

# Файловый хендлер
file_handler = logging.FileHandler(_log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Консольный хендлер
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    'ℹ️ [%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.propagate = False  # Не передаём события в корневой логгер


@dataclass
class TestMetrics:
    """Метрики тестирования."""
    start_time: datetime
    end_time: Optional[datetime] = None
    total_cycles: int = 0
    total_files_analyzed: int = 0
    total_suggestions: int = 0
    suggestions_by_type: Dict[str, int] = field(default_factory=dict)
    suggestions_by_priority: Dict[int, int] = field(default_factory=dict)
    high_confidence_suggestions: int = 0
    avg_confidence: float = 0.0
    avg_analysis_time: float = 0.0
    errors_count: int = 0


class AutonomousImproverTester:
    """Тестер для Autonomous Improver."""
    
    def __init__(self, test_duration_hours: float = 4.0):
        """Инициализация тестера.
        
        Args:
            test_duration_hours: Длительность теста в часах
        """
        self.test_duration = timedelta(hours=test_duration_hours)
        self.metrics = TestMetrics(start_time=datetime.now())
        self.suggestions_history: List[ImprovementSuggestion] = []
        self.analysis_times: List[float] = []
        
    async def run_test(self) -> TestMetrics:
        """Запускает тест Autonomous Improver.
        
        Returns:
            TestMetrics с результатами теста
        """
        logger.info(f"🧪 Начинаю тест Autonomous Improver на {self.test_duration.total_seconds() / 3600:.1f} часов")
        
        # Получаем улучшатель
        improver = get_autonomous_improver()
        
        # Запускаем
        improver.start()
        logger.info("✅ Autonomous Improver запущен")
        
        # Мониторим в течение тестового периода
        end_time = datetime.now() + self.test_duration
        cycle_count = 0
        
        try:
            while datetime.now() < end_time:
                try:
                    # Ждём немного перед проверкой
                    await asyncio.sleep(60)  # Проверяем каждую минуту
                except asyncio.CancelledError:
                    logger.info("🛑 Тест отменён")
                    break
                
                # Получаем текущие предложения
                current_suggestions = improver.get_suggestions(min_confidence=0.0)
                
                # Обновляем метрики
                # Сравниваем по file_path + description для уникальности
                existing_keys = {
                    (s.file_path, s.description) for s in self.suggestions_history
                }
                new_suggestions = [
                    s for s in current_suggestions
                    if (s.file_path, s.description) not in existing_keys
                ]
                
                if new_suggestions:
                    logger.info(f"💡 Найдено {len(new_suggestions)} новых предложений")
                    self.suggestions_history.extend(new_suggestions)
                    self._update_metrics(new_suggestions)
                
                # Обновляем метрику проанализированных файлов
                # Подсчитываем уникальные файлы из всех предложений
                unique_files = {s.file_path for s in self.suggestions_history}
                self.metrics.total_files_analyzed = len(unique_files)
                
                cycle_count += 1
                self.metrics.total_cycles = cycle_count
                
                # Логируем прогресс
                elapsed = datetime.now() - self.metrics.start_time
                remaining = end_time - datetime.now()
                logger.info(
                    f"⏱️ Прогресс: {elapsed.total_seconds() / 3600:.1f}ч / "
                    f"{self.test_duration.total_seconds() / 3600:.1f}ч "
                    f"(осталось: {remaining.total_seconds() / 3600:.1f}ч) | "
                    f"Предложений: {len(self.suggestions_history)}"
                )
        
        except KeyboardInterrupt:
            logger.info("🛑 Тест прерван пользователем (Ctrl+C)")
        except asyncio.CancelledError:
            logger.info("🛑 Тест отменён")
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка в тесте: {e}", error=e)
        finally:
            # Останавливаем улучшатель
            try:
                improver.stop()
                logger.info("🛑 Autonomous Improver остановлен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при остановке Autonomous Improver: {e}")
            
            # Финальные метрики
            self.metrics.end_time = datetime.now()
            self._finalize_metrics()
        
        return self.metrics
    
    def _update_metrics(self, suggestions: List[ImprovementSuggestion]) -> None:
        """Обновляет метрики на основе новых предложений."""
        self.metrics.total_suggestions += len(suggestions)
        
        for suggestion in suggestions:
            # По типам
            type_key = suggestion.type.value
            self.metrics.suggestions_by_type[type_key] = \
                self.metrics.suggestions_by_type.get(type_key, 0) + 1
            
            # По приоритетам
            priority = suggestion.priority
            self.metrics.suggestions_by_priority[priority] = \
                self.metrics.suggestions_by_priority.get(priority, 0) + 1
            
            # Высокая уверенность
            # Используем min_confidence из config вместо фиксированного 1.0
            from utils.config import get_config
            config = get_config()
            min_conf = config.autonomous_improver_min_confidence
            if suggestion.confidence >= min_conf:
                self.metrics.high_confidence_suggestions += 1
    
    def _finalize_metrics(self) -> None:
        """Финализирует метрики."""
        if self.suggestions_history:
            self.metrics.avg_confidence = sum(
                s.confidence for s in self.suggestions_history
            ) / len(self.suggestions_history)
        
        if self.analysis_times:
            self.metrics.avg_analysis_time = sum(self.analysis_times) / len(self.analysis_times)
        
        # Финальный подсчёт уникальных файлов
        unique_files = {s.file_path for s in self.suggestions_history}
        self.metrics.total_files_analyzed = len(unique_files)
    
    def save_results(self, output_path: Path) -> None:
        """Сохраняет результаты теста.
        
        Args:
            output_path: Путь для сохранения результатов
        """
        results = {
            "metrics": asdict(self.metrics),
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
                for s in self.suggestions_history
            ]
        }
        
        output_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8"
        )
        logger.info(f"💾 Результаты сохранены в {output_path}")
    
    def print_summary(self) -> None:
        """Выводит сводку результатов."""
        duration = (
            (self.metrics.end_time or datetime.now()) - self.metrics.start_time
        )
        
        print("\n" + "=" * 80)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТА AUTONOMOUS IMPROVER")
        print("=" * 80)
        print(f"\n⏱️ Длительность: {duration.total_seconds() / 3600:.2f} часов")
        print(f"🔄 Циклов анализа: {self.metrics.total_cycles}")
        print(f"📁 Файлов проанализировано: {self.metrics.total_files_analyzed}")
        print(f"💡 Всего предложений: {self.metrics.total_suggestions}")
        from utils.config import get_config
        config = get_config()
        min_conf = config.autonomous_improver_min_confidence
        print(f"✅ Предложений с высокой уверенностью (>={min_conf}): {self.metrics.high_confidence_suggestions}")
        print(f"📊 Средняя уверенность: {self.metrics.avg_confidence:.2f}")
        
        if self.metrics.suggestions_by_type:
            print(f"\n📋 По типам:")
            for type_name, count in sorted(
                self.metrics.suggestions_by_type.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  - {type_name}: {count}")
        
        if self.metrics.suggestions_by_priority:
            print(f"\n🎯 По приоритетам:")
            for priority in sorted(self.metrics.suggestions_by_priority.keys(), reverse=True):
                count = self.metrics.suggestions_by_priority[priority]
                print(f"  - Приоритет {priority}: {count}")
        
        if self.suggestions_history:
            print(f"\n🏆 ТОП-10 предложений по приоритету:")
            top_suggestions = sorted(
                self.suggestions_history,
                key=lambda s: (s.priority, s.confidence),
                reverse=True
            )[:10]
            
            for i, suggestion in enumerate(top_suggestions, 1):
                print(f"\n  {i}. {suggestion.file_path}")
                print(f"     Тип: {suggestion.type.value}")
                print(f"     Приоритет: {suggestion.priority} | Уверенность: {suggestion.confidence:.2f}")
                print(f"     Описание: {suggestion.description[:100]}...")
                print(f"     Предложение: {suggestion.suggestion[:100]}...")
        
        print("\n" + "=" * 80)


async def main():
    """Главная функция теста."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Тест Autonomous Improver")
    parser.add_argument(
        "--duration",
        type=float,
        default=4.0,
        help="Длительность теста в часах (по умолчанию 4)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test_improver_results.json",
        help="Путь для сохранения результатов"
    )
    
    args = parser.parse_args()
    
    # Проверяем конфигурацию
    config = get_config()
    if not config.autonomous_improver_enabled:
        print("⚠️ Autonomous Improver отключен в config.toml")
        print("   Установите [autonomous_improver] enabled = true")
        return
    
    print(f"🧪 Запуск теста Autonomous Improver на {args.duration} часов")
    print(f"📁 Проект: {config.autonomous_improver_project_path or 'текущая директория'}")
    print(f"🤖 Модель: {config.autonomous_improver_model or 'автовыбор'}")
    print(f"🎯 Минимальная уверенность: {config.autonomous_improver_min_confidence}")
    print(f"📊 Файлов за цикл: {config.autonomous_improver_max_files_per_cycle}")
    print(f"⏱️ Интервал циклов: {config.autonomous_improver_cycle_interval}с")
    print()
    
    # Создаём тестер
    tester = AutonomousImproverTester(test_duration_hours=args.duration)
    output_path = Path(args.output)
    
    try:
        # Запускаем тест
        metrics = await tester.run_test()
        
        # Сохраняем результаты
        tester.save_results(output_path)
        
        # Выводим сводку
        tester.print_summary()
        
        print(f"\n✅ Тест завершён. Результаты сохранены в {output_path}")
        
    except KeyboardInterrupt:
        print("\n🛑 Тест прерван пользователем (Ctrl+C)")
        # Сохраняем результаты даже при прерывании
        try:
            tester.save_results(output_path)
            tester.print_summary()
            print(f"\n💾 Результаты сохранены в {output_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить результаты: {e}")
    except asyncio.CancelledError:
        print("\n🛑 Тест отменён")
        # Сохраняем результаты
        try:
            tester.save_results(output_path)
            tester.print_summary()
            print(f"\n💾 Результаты сохранены в {output_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить результаты: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}", error=e)
        print(f"\n❌ Ошибка теста: {e}")
        # Пытаемся сохранить результаты даже при ошибке
        try:
            tester.save_results(output_path)
            tester.print_summary()
            print(f"💾 Частичные результаты сохранены в {output_path}")
        except Exception as save_error:
            logger.warning(f"⚠️ Не удалось сохранить результаты: {save_error}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Подавляем traceback при Ctrl+C
        print("\n🛑 Тест остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
