#!/usr/bin/env python3
"""Быстрый тест системы с задачей 'привет'."""
import sys
from agents.intent import IntentAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.test_generator import TestGeneratorAgent
from agents.coder import CoderAgent
from agents.reflection import ReflectionAgent
from agents.memory import MemoryAgent
from utils.validation import validate_code
from utils.logger import setup_logger

logger = setup_logger(level=20)

def main():
    """Тестирование задачи 'привет'."""
    print("=" * 70)
    print("🧪 Тестирование задачи: 'привет'")
    print("=" * 70)
    
    task = "привет"
    
    # Инициализация агентов
    print("\n📦 Инициализация агентов...")
    memory_agent = MemoryAgent()
    intent_agent = IntentAgent()
    planner_agent = PlannerAgent(memory_agent=memory_agent)
    researcher_agent = ResearcherAgent(memory_agent=memory_agent)
    test_generator = TestGeneratorAgent()
    coder_agent = CoderAgent()
    reflection_agent = ReflectionAgent()
    
    try:
        # Шаг 1: Intent
        print("\n1️⃣ Определение намерения...")
        intent_result = intent_agent.determine_intent(task)
        print(f"   ✅ Тип: {intent_result.type}, уверенность: {intent_result.confidence:.2f}")
        
        # Обработка приветствий
        if intent_result.type == "greeting":
            print("\n" + "=" * 70)
            print("👋 Привет! Я локальная многоагентная система генерации кода.")
            print("Я могу помочь вам:")
            print("  • Создать новый код (create)")
            print("  • Изменить существующий код (modify)")
            print("  • Найти и исправить ошибки (debug)")
            print("  • Оптимизировать код (optimize)")
            print("  • Объяснить как работает код (explain)")
            print("  • Написать тесты (test)")
            print("  • Рефакторить код (refactor)")
            print("\nПросто опишите задачу, и я помогу вам!")
            print("=" * 70)
            print("\n✅ Тестирование завершено успешно!")
            return
        
        # Шаг 2: Planner
        print("\n2️⃣ Планирование...")
        plan = planner_agent.create_plan(task=task, intent_type=intent_result.type)
        print(f"   ✅ План создан ({len(plan)} символов)")
        
        # Шаг 3: Researcher
        print("\n3️⃣ Исследование...")
        context = researcher_agent.research(query=task, intent_type=intent_result.type)
        print(f"   ✅ Контекст собран ({len(context)} символов)")
        
        # Шаг 4: Test Generator
        print("\n4️⃣ Генерация тестов...")
        tests = test_generator.generate_tests(
            plan=plan,
            context=context,
            intent_type=intent_result.type
        )
        if tests:
            print(f"   ✅ Тесты сгенерированы ({len(tests)} символов)")
            print(f"   Тесты:\n{tests[:200]}...")
        else:
            print("   ❌ Тесты не сгенерированы")
            return
        
        # Шаг 5: Coder
        print("\n5️⃣ Генерация кода...")
        code = coder_agent.generate_code(
            plan=plan,
            tests=tests,
            context=context,
            intent_type=intent_result.type
        )
        if code:
            print(f"   ✅ Код сгенерирован ({len(code)} символов)")
            print(f"   Код:\n{code[:200]}...")
        else:
            print("   ❌ Код не сгенерирован")
            return
        
        # Шаг 6: Validation
        print("\n6️⃣ Валидация...")
        validation_results = validate_code(code_str=code, test_str=tests)
        print(f"   pytest: {'✅' if validation_results.get('pytest', {}).get('success') else '❌'}")
        print(f"   mypy: {'✅' if validation_results.get('mypy', {}).get('success') else '❌'}")
        print(f"   bandit: {'✅' if validation_results.get('bandit', {}).get('success') else '❌'}")
        
        # Шаг 7: Reflection
        print("\n7️⃣ Рефлексия...")
        reflection_result = reflection_agent.reflect(
            task=task,
            plan=plan,
            context=context,
            tests=tests,
            code=code,
            validation_results=validation_results
        )
        print(f"   ✅ Оценка: overall={reflection_result.overall_score:.2f}")
        
        print("\n" + "=" * 70)
        print("✅ Тестирование завершено успешно!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
