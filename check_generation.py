#!/usr/bin/env python3
"""Связующий скрипт для проверки генерации тестов и кода."""
import sys
from agents.intent import IntentAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from utils.validation import validate_code
from utils.logger import setup_logger


logger = setup_logger(level=20)  # INFO уровень


def create_simple_plan(task: str, intent_type: str) -> str:
    """Создаёт простой план на основе задачи и намерения.
    
    Args:
        task: Текст задачи
        intent_type: Тип намерения
        
    Returns:
        Простой план в виде строки
    """
    return f"""
Задача: {task}
Тип: {intent_type}

План:
1. Проанализировать требования задачи
2. Определить необходимые функции/классы
3. Реализовать функционал согласно требованиям
4. Убедиться что код соответствует лучшим практикам Python
"""


def main() -> None:
    """Основная функция скрипта."""
    logger.info("=" * 70)
    logger.info("🚀 Запуск проверки генерации тестов и кода")
    logger.info("=" * 70)
    
    # Получаем задачу
    if len(sys.argv) > 1:
        user_task = " ".join(sys.argv[1:])
    else:
        user_task = input("\n📝 Введите задачу: ").strip()
    
    if not user_task:
        logger.error("❌ Пустой запрос, выход")
        return
    
    print(f"\n{'=' * 70}")
    print(f"Задача: {user_task}")
    print(f"{'=' * 70}\n")
    
    # Шаг 1: Определение намерения
    logger.info("📋 Шаг 1: Определение намерения...")
    intent_agent = IntentAgent()
    intent_result = intent_agent.determine_intent(user_task)
    
    print(f"\n✅ Намерение: {intent_result.type}")
    print(f"   Уверенность: {intent_result.confidence:.2f}")
    print(f"   Описание: {intent_result.description}")
    
    # Шаг 2: Сбор контекста
    logger.info("\n📚 Шаг 2: Сбор контекста...")
    researcher_agent = ResearcherAgent()
    context = researcher_agent.research(user_task)
    
    context_preview = context[:200] + "..." if len(context) > 200 else context
    print(f"\n✅ Контекст собран (размер: {len(context)} символов)")
    if context:
        print(f"   Предпросмотр: {context_preview}")
    else:
        print("   Контекст не найден")
    
    # Шаг 3: Создание плана
    logger.info("\n📝 Шаг 3: Создание плана...")
    plan = create_simple_plan(user_task, intent_result.type)
    print(f"   План создан (размер: {len(plan)} символов)")
    
    # Шаг 4: Генерация тестов
    logger.info("\n🧪 Шаг 4: Генерация pytest тестов...")
    test_generator = TestGeneratorAgent()
    tests = test_generator.generate_tests(
        plan=plan,
        context=context,
        intent_type=intent_result.type
    )
    
    if not tests:
        logger.error("❌ Не удалось сгенерировать тесты. Выход.")
        return
    
    print(f"✅ Тесты сгенерированы (размер: {len(tests)} символов)")
    print(f"\n--- Начало тестов ---\n{tests[:500]}\n--- Конец тестов ---")
    
    # Шаг 5: Генерация кода
    logger.info("\n💻 Шаг 5: Генерация кода...")
    coder_agent = CoderAgent()
    code = coder_agent.generate_code(
        plan=plan,
        tests=tests,
        context=context,
        intent_type=intent_result.type
    )
    
    if not code:
        logger.error("❌ Не удалось сгенерировать код. Выход.")
        return
    
    print(f"✅ Код сгенерирован (размер: {len(code)} символов)")
    print(f"\n--- Начало кода ---\n{code[:500]}\n--- Конец кода ---")
    
    # Шаг 6: Валидация
    logger.info("\n🔍 Шаг 6: Валидация кода...")
    validation_results = validate_code(code_str=code, test_str=tests)
    
    print(f"\n{'=' * 70}")
    print("📊 Результаты валидации:")
    print(f"{'=' * 70}")
    
    # pytest
    if tests:
        pytest_status = "✅ ПРОЙДЕН" if validation_results["pytest"]["success"] else "❌ НЕ ПРОЙДЕН"
        print(f"pytest: {pytest_status}")
        if not validation_results["pytest"]["success"]:
            print(f"   Ошибки: {validation_results['pytest']['output'][:300]}")
    else:
        print("pytest: ⏭️ ПРОПУЩЕН (нет тестов)")
    
    # mypy
    mypy_status = "✅ ПРОЙДЕН" if validation_results["mypy"]["success"] else "❌ НЕ ПРОЙДЕН"
    print(f"mypy: {mypy_status}")
    if not validation_results["mypy"]["success"]:
        print(f"   Ошибки: {validation_results['mypy']['errors'][:300]}")
    
    # bandit
    bandit_status = "✅ ПРОЙДЕН" if validation_results["bandit"]["success"] else "❌ НЕ ПРОЙДЕН"
    print(f"bandit: {bandit_status}")
    if not validation_results["bandit"]["success"]:
        print(f"   Проблемы: {validation_results['bandit']['issues'][:300]}")
    
    # Итоговый статус
    print(f"\n{'=' * 70}")
    if validation_results["all_passed"]:
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
    else:
        print("❌ НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ")
    print(f"{'=' * 70}\n")
    
    # Сохраняем результаты в файлы для отладки
    try:
        with open("generated_code.py", "w", encoding="utf-8") as f:
            f.write(code)
        logger.info("💾 Код сохранён в generated_code.py")
        
        with open("generated_tests.py", "w", encoding="utf-8") as f:
            f.write(tests)
        logger.info("💾 Тесты сохранены в generated_tests.py")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сохранить файлы: {e}")
    
    logger.info("✅ Скрипт завершён")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
