#!/usr/bin/env python3
"""Скрипт для проверки логики Autonomous Improver.

Проверяет:
1. Определение типа проекта
2. Выбор адаптера
3. Обнаружение файлов
4. Фильтрацию файлов
5. Приоритизацию
6. Передачу структуры в модели
7. Запуск простой задачи анализа
"""
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.autonomous_improver import get_autonomous_improver
from infrastructure.autonomous_improver.project_profile import ProjectProfile
from utils.logger import get_logger

logger = get_logger()


def print_section(title: str):
    """Печатает заголовок секции."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(label: str, value: Any, status: str = "✅"):
    """Печатает результат проверки."""
    print(f"{status} {label}: {value}")


def check_project_detection(improver) -> Dict[str, Any]:
    """Проверяет определение типа проекта."""
    print_section("1. Определение типа проекта")
    
    profile = improver.profile
    
    print_result("Язык проекта", profile.language)
    print_result("Домен", profile.domain.value if hasattr(profile.domain, 'value') else profile.domain)
    print_result("Фреймворк", profile.framework.value if hasattr(profile.framework, 'value') else profile.framework)
    
    # Проверяем логику определения
    project_path = Path(improver.project_path)
    python_files = list(project_path.rglob("*.py"))
    ts_files = list(project_path.rglob("*.ts")) + list(project_path.rglob("*.tsx"))
    js_files = list(project_path.rglob("*.js")) + list(project_path.rglob("*.jsx"))
    
    print_result("Найдено .py файлов", len(python_files))
    print_result("Найдено .ts/.tsx файлов", len(ts_files))
    print_result("Найдено .js/.jsx файлов", len(js_files))
    
    # Ожидаемый тип
    if python_files and (ts_files or js_files):
        expected_language = "mixed"
    elif ts_files or js_files:
        expected_language = "typescript" if ts_files else "javascript"
    else:
        expected_language = "python"
    
    if profile.language == expected_language:
        print_result("Определение языка", "КОРРЕКТНО", "✅")
    else:
        print_result("Определение языка", f"ОШИБКА: ожидалось {expected_language}, получено {profile.language}", "❌")
    
    return {
        "language": profile.language,
        "domain": profile.domain.value if hasattr(profile.domain, 'value') else profile.domain,
        "framework": profile.framework.value if hasattr(profile.framework, 'value') else profile.framework,
        "python_files": len(python_files),
        "ts_files": len(ts_files),
        "js_files": len(js_files)
    }


def check_adapter_selection(improver) -> Dict[str, Any]:
    """Проверяет выбор адаптера."""
    print_section("2. Выбор адаптера")
    
    adapter = improver.adapter
    profile = improver.profile
    
    print_result("Выбранный адаптер", adapter.language)
    print_result("Поддерживаемые расширения", adapter.file_extensions)
    
    # Проверяем корректность выбора
    if profile.language == "python":
        expected_adapter = "python"
    elif profile.language in ["typescript", "javascript"]:
        expected_adapter = "frontend"
    elif profile.language == "mixed":
        expected_adapter = "mixed"
    else:
        expected_adapter = "python"  # Fallback
    
    if adapter.language == expected_adapter:
        print_result("Выбор адаптера", "КОРРЕКТНО", "✅")
    else:
        print_result("Выбор адаптера", f"ОШИБКА: ожидалось {expected_adapter}, получено {adapter.language}", "❌")
    
    return {
        "adapter_language": adapter.language,
        "file_extensions": adapter.file_extensions,
        "expected": expected_adapter
    }


def check_file_discovery(improver) -> Dict[str, Any]:
    """Проверяет обнаружение файлов."""
    print_section("3. Обнаружение файлов")
    
    project_path = Path(improver.project_path)
    all_files = improver.adapter.discover_files(project_path)
    
    print_result("Всего найдено файлов", len(all_files))
    
    # Группируем по расширениям
    extensions = {}
    for f in all_files:
        ext = f.suffix.lower()
        extensions[ext] = extensions.get(ext, 0) + 1
    
    print("\nРаспределение по расширениям:")
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext}: {count} файлов")
    
    # Проверяем, что найдены правильные типы файлов
    expected_extensions = set(improver.adapter.file_extensions)
    found_extensions = set(extensions.keys())
    
    # Проверяем, что найдены файлы ожидаемых типов
    if found_extensions.intersection(expected_extensions):
        print_result("Найдены файлы ожидаемых типов", "ДА", "✅")
    else:
        print_result("Найдены файлы ожидаемых типов", "НЕТ", "❌")
    
    return {
        "total_files": len(all_files),
        "extensions": extensions,
        "found_extensions": list(found_extensions),
        "expected_extensions": list(expected_extensions)
    }


def check_file_filtering(improver) -> Dict[str, Any]:
    """Проверяет фильтрацию файлов."""
    print_section("4. Фильтрация файлов")
    
    project_path = Path(improver.project_path)
    all_files = improver.adapter.discover_files(project_path)
    profile = improver.profile
    
    print_result("Исключённые директории", profile.excluded_directories)
    print_result("Исключённые паттерны", profile.excluded_file_patterns)
    
    # Фильтруем файлы
    files_to_analyze = [
        f for f in all_files
        if profile.should_analyze_file(str(f))
    ]
    
    excluded_files = [
        f for f in all_files
        if not profile.should_analyze_file(str(f))
    ]
    
    print_result("Файлов для анализа", len(files_to_analyze))
    print_result("Исключённых файлов", len(excluded_files))
    
    # Показываем примеры исключённых файлов
    if excluded_files:
        print("\nПримеры исключённых файлов (первые 5):")
        for f in excluded_files[:5]:
            print(f"  ❌ {f}")
    
    # Проверяем, что исключённые директории действительно исключены
    excluded_dirs_in_files = []
    for excluded_dir in profile.excluded_directories:
        for f in files_to_analyze:
            if excluded_dir in str(f):
                excluded_dirs_in_files.append(str(f))
                break
    
    if excluded_dirs_in_files:
        print_result("Проверка исключений", f"ОШИБКА: найдены файлы из исключённых директорий: {excluded_dirs_in_files[:3]}", "❌")
    else:
        print_result("Проверка исключений", "КОРРЕКТНО", "✅")
    
    return {
        "total_files": len(all_files),
        "files_to_analyze": len(files_to_analyze),
        "excluded_files": len(excluded_files),
        "excluded_dirs": profile.excluded_directories
    }


def check_file_prioritization(improver) -> Dict[str, Any]:
    """Проверяет приоритизацию файлов."""
    print_section("5. Приоритизация файлов")
    
    project_path = Path(improver.project_path)
    all_files = improver.adapter.discover_files(project_path)
    profile = improver.profile
    
    # Фильтруем файлы
    files_to_analyze = [
        f for f in all_files
        if profile.should_analyze_file(str(f))
    ]
    
    if not files_to_analyze:
        print_result("Файлов для приоритизации", "НЕТ", "⚠️")
        return {"prioritized": [], "total": 0}
    
    # Берём первые 20 файлов для приоритизации (чтобы не долго)
    candidate_files = files_to_analyze[:20]
    
    print_result("Файлов для приоритизации", len(candidate_files))
    
    # Приоритизируем
    prioritized = improver._prioritize_files(candidate_files)
    
    print("\nТоп-10 приоритетных файлов:")
    for i, f in enumerate(prioritized[:10], 1):
        priority = profile.get_file_priority(str(f))
        print(f"  {i}. {f.name} (приоритет: {priority})")
    
    # Проверяем, что приоритизация работает
    if len(prioritized) == len(candidate_files):
        print_result("Приоритизация", "КОРРЕКТНО", "✅")
    else:
        print_result("Приоритизация", f"ОШИБКА: потеряны файлы ({len(prioritized)} из {len(candidate_files)})", "❌")
    
    return {
        "prioritized": [str(f) for f in prioritized[:10]],
        "total": len(prioritized)
    }


def check_structure_analysis(improver) -> Dict[str, Any]:
    """Проверяет анализ структуры файлов."""
    print_section("6. Анализ структуры файлов")
    
    project_path = Path(improver.project_path)
    all_files = improver.adapter.discover_files(project_path)
    profile = improver.profile
    
    # Фильтруем файлы
    files_to_analyze = [
        f for f in all_files
        if profile.should_analyze_file(str(f))
    ]
    
    if not files_to_analyze:
        print_result("Файлов для анализа структуры", "НЕТ", "⚠️")
        return {"analyzed": 0}
    
    # Анализируем первые 3 файла
    analyzed_count = 0
    for f in files_to_analyze[:3]:
        try:
            structure = improver.adapter.analyze_structure(f)
            if structure:
                analyzed_count += 1
                context = improver.adapter.build_context(f, structure)
                print(f"\n📄 {f.name}:")
                print(f"   Структура: {'✅' if structure else '❌'}")
                if context:
                    # Показываем первые 3 строки контекста
                    context_lines = context.split('\n')[:3]
                    for line in context_lines:
                        print(f"   {line}")
            else:
                print(f"\n📄 {f.name}: структура не определена")
        except Exception as e:
            print(f"\n📄 {f.name}: ошибка анализа - {e}")
    
    print_result("Проанализировано файлов", f"{analyzed_count} из {min(3, len(files_to_analyze))}")
    
    return {"analyzed": analyzed_count}


async def check_prompt_building(improver) -> Dict[str, Any]:
    """Проверяет построение промптов."""
    print_section("7. Построение промптов")
    
    project_path = Path(improver.project_path)
    all_files = improver.adapter.discover_files(project_path)
    profile = improver.profile
    
    # Фильтруем файлы
    files_to_analyze = [
        f for f in all_files
        if profile.should_analyze_file(str(f))
    ]
    
    if not files_to_analyze:
        print_result("Файлов для построения промпта", "НЕТ", "⚠️")
        return {"prompts": 0}
    
    # Берём первый файл
    test_file = files_to_analyze[0]
    
    try:
        # Анализируем структуру
        structure = improver.adapter.analyze_structure(test_file)
        context = improver.adapter.build_context(test_file, structure)
        code_sample = improver.adapter.extract_code_sample(test_file, structure, max_chars=500)
        
        # Строим промпт
        from infrastructure.autonomous_improver.prompt_builder import PromptBuilder
        prompt = PromptBuilder.build(
            adapter=improver.adapter,
            profile=profile,
            context=context,
            code_sample=code_sample,
            web_context="",
            file_path=test_file
        )
        
        print_result("Промпт построен", "ДА", "✅")
        print(f"\nДлина промпта: {len(prompt)} символов")
        
        # Проверяем наличие ключевых элементов
        checks = {
            "Базовый промпт": "Ты — опытный senior разработчик" in prompt,
            "Языковые правила": any(lang in prompt for lang in ["Python", "TypeScript", "JavaScript"]),
            "Доменные правила": any(domain in prompt for domain in ["Frontend", "Backend"]),
            "Контекст файла": context[:50] in prompt if context else False,
            "Код для анализа": code_sample[:50] in prompt if code_sample else False,
            "Формат JSON": '"suggestions"' in prompt
        }
        
        print("\nПроверка элементов промпта:")
        for check_name, check_result in checks.items():
            status = "✅" if check_result else "❌"
            print(f"  {status} {check_name}: {'ДА' if check_result else 'НЕТ'}")
        
        all_checks_passed = all(checks.values())
        print_result("Все проверки промпта", "ПРОЙДЕНЫ" if all_checks_passed else "ОШИБКИ", "✅" if all_checks_passed else "❌")
        
        return {
            "prompts": 1,
            "prompt_length": len(prompt),
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks)
        }
        
    except Exception as e:
        print_result("Построение промпта", f"ОШИБКА: {e}", "❌")
        return {"prompts": 0, "error": str(e)}


async def run_simple_analysis(improver) -> Dict[str, Any]:
    """Запускает простую задачу анализа."""
    print_section("8. Запуск простой задачи анализа")
    
    print("Запускаю анализ проекта (максимум 5 файлов)...")
    
    # Временно уменьшаем количество файлов для быстрого теста
    original_max_files = improver.max_files_per_cycle
    improver.max_files_per_cycle = 5
    
    try:
        # Запускаем анализ
        analysis = await improver.analyze_project_async()
        
        print_result("Проанализировано файлов", analysis.analyzed_files)
        print_result("Найдено предложений", len(analysis.suggestions))
        print_result("Время анализа", f"{analysis.metrics.get('analysis_time_seconds', 0):.1f} сек")
        
        # Показываем примеры предложений
        if analysis.suggestions:
            print("\nПримеры предложений (первые 3):")
            for i, suggestion in enumerate(analysis.suggestions[:3], 1):
                print(f"\n  {i}. {suggestion.file_path}")
                print(f"     Тип: {suggestion.type.value}")
                print(f"     Описание: {suggestion.description[:60]}...")
                print(f"     Уверенность: {suggestion.confidence:.2f}")
                print(f"     Приоритет: {suggestion.priority}")
        
        return {
            "analyzed_files": analysis.analyzed_files,
            "suggestions": len(analysis.suggestions),
            "time_seconds": analysis.metrics.get('analysis_time_seconds', 0)
        }
        
    except Exception as e:
        print_result("Анализ", f"ОШИБКА: {e}", "❌")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        # Восстанавливаем оригинальное значение
        improver.max_files_per_cycle = original_max_files


async def main():
    """Основная функция."""
    print("\n" + "=" * 80)
    print("  ТЕСТ ЛОГИКИ AUTONOMOUS IMPROVER")
    print("=" * 80)
    
    try:
        # Получаем экземпляр
        print("\n🔧 Инициализация Autonomous Improver...")
        improver = get_autonomous_improver()
        
        print_result("Проект", str(improver.project_path))
        print_result("Модель", improver.model)
        print_result("Мин. уверенность", improver.min_confidence)
        
        # Запускаем проверки
        results = {}
        
        results["project_detection"] = check_project_detection(improver)
        results["adapter_selection"] = check_adapter_selection(improver)
        results["file_discovery"] = check_file_discovery(improver)
        results["file_filtering"] = check_file_filtering(improver)
        results["file_prioritization"] = check_file_prioritization(improver)
        results["structure_analysis"] = check_structure_analysis(improver)
        results["prompt_building"] = await check_prompt_building(improver)
        results["simple_analysis"] = await run_simple_analysis(improver)
        
        # Итоги
        print_section("ИТОГИ ПРОВЕРКИ")
        
        total_checks = 0
        passed_checks = 0
        
        # Подсчитываем проверки
        if results.get("project_detection"):
            total_checks += 1
            if results["project_detection"].get("language"):
                passed_checks += 1
        
        if results.get("adapter_selection"):
            total_checks += 1
            if results["adapter_selection"].get("adapter_language"):
                passed_checks += 1
        
        if results.get("file_discovery"):
            total_checks += 1
            if results["file_discovery"].get("total_files", 0) > 0:
                passed_checks += 1
        
        if results.get("file_filtering"):
            total_checks += 1
            if results["file_filtering"].get("files_to_analyze", 0) > 0:
                passed_checks += 1
        
        if results.get("file_prioritization"):
            total_checks += 1
            if results["file_prioritization"].get("total", 0) > 0:
                passed_checks += 1
        
        if results.get("structure_analysis"):
            total_checks += 1
            if results["structure_analysis"].get("analyzed", 0) > 0:
                passed_checks += 1
        
        if results.get("prompt_building"):
            total_checks += 1
            if results["prompt_building"].get("prompts", 0) > 0:
                passed_checks += 1
        
        if results.get("simple_analysis"):
            total_checks += 1
            if "error" not in results["simple_analysis"]:
                passed_checks += 1
        
        print_result("Пройдено проверок", f"{passed_checks} из {total_checks}")
        
        if passed_checks == total_checks:
            print_result("Общий результат", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ", "✅")
            return 0
        else:
            print_result("Общий результат", f"НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ", "⚠️")
            return 1
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
