#!/usr/bin/env python3
"""End-to-end тестовый скрипт для проверки работы ядра системы."""
import sys
from agents.intent import IntentAgent, IntentResult
from agents.researcher import ResearcherAgent
from utils.logger import setup_logger


def main() -> None:
    """Основная функция тестового скрипта."""
    # Настраиваем логгер
    logger = setup_logger(level=20)  # INFO уровень
    
    logger.info("=" * 60)
    logger.info("🚀 Запуск тестового скрипта ядра системы")
    logger.info("=" * 60)
    
    # Получаем запрос от пользователя
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = input("\n📝 Введите задачу: ").strip()
    
    if not user_query:
        logger.error("❌ Пустой запрос, выход")
        return
    
    print(f"\n{'=' * 60}")
    print(f"Запрос: {user_query}")
    print(f"{'=' * 60}\n")
    
    # Шаг 1: Определяем намерение
    logger.info("📋 Шаг 1: Определение намерения...")
    intent_agent = IntentAgent()
    intent_result: IntentResult = intent_agent.determine_intent(user_query)
    
    print(f"\n✅ Результат определения намерения:")
    print(f"   Тип: {intent_result.type}")
    print(f"   Уверенность: {intent_result.confidence:.2f}")
    print(f"   Описание: {intent_result.description}")
    
    # Шаг 2: Собираем контекст
    logger.info("\n📚 Шаг 2: Сбор контекста...")
    researcher_agent = ResearcherAgent()
    context = researcher_agent.research(user_query)
    
    print(f"\n✅ Собранный контекст:")
    print(f"{'=' * 60}")
    if context:
        print(context)
    else:
        print("   (контекст не найден)")
    print(f"{'=' * 60}")
    
    # Итоговая сводка
    print(f"\n{'=' * 60}")
    print("📊 Итоговая сводка:")
    print(f"   Намерение: {intent_result.type} ({intent_result.confidence:.2f})")
    print(f"   Контекст: {'найден' if context else 'не найден'}")
    print(f"   Размер контекста: {len(context)} символов")
    print(f"{'=' * 60}\n")
    
    logger.info("✅ Тестовый скрипт завершён")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
