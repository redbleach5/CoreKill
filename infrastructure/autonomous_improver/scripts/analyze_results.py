"""Анализ результатов теста Autonomous Improver.

Оценивает качество предложений и сравнивает их с реальными улучшениями.

Примеры использования:
    ```bash
    # Анализ результатов теста
    python3 infrastructure/autonomous_improver/scripts/analyze_results.py test_improver_results.json
    
    # Или из корня проекта
    python3 infrastructure/autonomous_improver/scripts/analyze_results.py test_improver_results.json
    ```

Выводит:
    - Общую статистику (количество предложений, средняя уверенность)
    - Распределение по типам улучшений
    - Распределение по приоритетам
    - ТОП-10 файлов с наибольшим количеством предложений
    - ТОП-5 лучших предложений (приоритет + уверенность)

Зависимости:
    - json: для чтения результатов
    - pathlib: для работы с путями
    - collections: для подсчёта

Связанные скрипты:
    - infrastructure/autonomous_improver/scripts/test.py: генерирует результаты
    - run_improver.sh: запускает тест и анализ

Примечания:
    - Результаты сохраняются в JSON формате
    - Анализ помогает определить наиболее ценные предложения
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter

# Добавляем корневую директорию проекта в путь
# Скрипт находится в infrastructure/autonomous_improver/scripts/
# Нужно подняться на 3 уровня вверх до корня проекта
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def analyze_results(results_path: Path) -> None:
    """Анализирует результаты теста.
    
    Args:
        results_path: Путь к файлу с результатами
    """
    if not results_path.exists():
        print(f"❌ Файл не найден: {results_path}")
        return
    
    data = json.loads(results_path.read_text(encoding="utf-8"))
    metrics = data["metrics"]
    suggestions = data["suggestions"]
    
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ AUTONOMOUS IMPROVER")
    print("=" * 80)
    
    # Общая статистика
    print(f"\n📈 Общая статистика:")
    print(f"  - Всего предложений: {len(suggestions)}")
    print(f"  - С высокой уверенностью (>=1.0): {metrics.get('high_confidence_count', 0)}")
    print(f"  - Средняя уверенность: {sum(s['confidence'] for s in suggestions) / len(suggestions):.2f}" if suggestions else "  - Средняя уверенность: N/A")
    
    # По типам
    if metrics.get("suggestions_by_type"):
        print(f"\n📋 Распределение по типам:")
        for type_name, count in sorted(
            metrics["suggestions_by_type"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            percentage = (count / len(suggestions) * 100) if suggestions else 0
            print(f"  - {type_name}: {count} ({percentage:.1f}%)")
    
    # По приоритетам
    if metrics.get("suggestions_by_priority"):
        print(f"\n🎯 Распределение по приоритетам:")
        for priority in sorted(metrics["suggestions_by_priority"].keys(), reverse=True):
            count = metrics["suggestions_by_priority"][priority]
            percentage = (count / len(suggestions) * 100) if suggestions else 0
            bar = "█" * (count // max(1, len(suggestions) // 20))
            print(f"  - Приоритет {priority}: {count} ({percentage:.1f}%) {bar}")
    
    # По файлам
    files_counter = Counter(s["file_path"] for s in suggestions)
    if files_counter:
        print(f"\n📁 ТОП-10 файлов с наибольшим количеством предложений:")
        for file_path, count in files_counter.most_common(10):
            print(f"  - {file_path}: {count} предложений")
    
    # Качество предложений
    print(f"\n✅ Качество предложений:")
    high_priority = [s for s in suggestions if s.get("priority", 0) >= 7]
    print(f"  - Высокий приоритет (>=7): {len(high_priority)}")
    
    high_confidence = [s for s in suggestions if s.get("confidence", 0) >= 0.9]
    print(f"  - Высокая уверенность (>=0.9): {len(high_confidence)}")
    
    high_both = [s for s in suggestions if s.get("priority", 0) >= 7 and s.get("confidence", 0) >= 0.9]
    print(f"  - Высокий приоритет И уверенность: {len(high_both)}")
    
    # Примеры лучших предложений
    if suggestions:
        print(f"\n🏆 ТОП-5 предложений (приоритет + уверенность):")
        sorted_suggestions = sorted(
            suggestions,
            key=lambda s: (s.get("priority", 0), s.get("confidence", 0)),
            reverse=True
        )[:5]
        
        for i, s in enumerate(sorted_suggestions, 1):
            print(f"\n  {i}. {s['file_path']}")
            print(f"     Тип: {s.get('type', 'unknown')}")
            print(f"     Приоритет: {s.get('priority', 0)} | Уверенность: {s.get('confidence', 0):.2f}")
            print(f"     Описание: {s.get('description', '')[:80]}...")
            print(f"     Предложение: {s.get('suggestion', '')[:80]}...")
            if s.get("reasoning"):
                print(f"     Обоснование: {s['reasoning'][:80]}...")
    
    print("\n" + "=" * 80)
    print("💡 Рекомендации:")
    print("  1. Проверьте предложения с высоким приоритетом (>=7)")
    print("  2. Обратите внимание на файлы с множеством предложений")
    print("  3. Рассмотрите предложения с уверенностью >=0.9")
    print("  4. Примените улучшения постепенно, тестируя каждое")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Анализ результатов теста Autonomous Improver")
    parser.add_argument(
        "results_file",
        type=str,
        help="Путь к файлу с результатами (test_improver_results.json)"
    )
    
    args = parser.parse_args()
    
    analyze_results(Path(args.results_file))
