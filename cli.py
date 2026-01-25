#!/usr/bin/env python3
"""CLI интерфейс для многоагентной системы генерации кода.

Интерактивный командный интерфейс для работы с многоагентной системой
генерации кода через LangGraph workflow.

Примеры использования:
    ```bash
    # Запуск CLI
    python3 cli.py
    
    # Интерактивный режим
    # Введите задачу, система обработает её через workflow
    📝 Введите задачу: Создать калькулятор
    
    # Выход из CLI
    📝 Введите задачу: quit
    ```

Возможности:
    - Интерактивный ввод задач
    - Полный workflow через LangGraph
    - Автоматическое сохранение артефактов
    - Вывод результатов и метрик
    - Предложение улучшений

Зависимости:
    - infrastructure.workflow_graph: создание графа workflow
    - infrastructure.workflow_state: состояние агентов
    - utils.config: конфигурация
    - utils.logger: логирование
    - utils.artifact_saver: сохранение артефактов

Связанные утилиты:
    - run.py: веб-интерфейс (альтернатива CLI)
    - utils.artifact_saver: сохранение результатов

Примечания:
    - Работает в интерактивном режиме
    - Сохраняет все артефакты в output/
    - Поддерживает все типы задач (create, modify, debug, etc.)
    - Использует те же агенты, что и веб-интерфейс
"""
import sys
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState
from utils.config import get_config
from utils.logger import setup_logger
from utils.artifact_saver import ArtifactSaver


logger = setup_logger(level=20)  # INFO уровень


def main() -> None:
    """Основной цикл CLI."""
    logger.info("=" * 70)
    logger.info("🚀 Локальная многоагентная система генерации кода")
    logger.info("=" * 70)
    
    # Создаём граф LangGraph
    graph = create_workflow_graph()
    config = get_config()
    
    print("\n" + "=" * 70)
    
    while True:
        try:
            # Получаем задачу от пользователя
            user_task = input("\n📝 Введите задачу (или 'quit' для выхода): ").strip()
            
            if not user_task or user_task.lower() in ["quit", "exit", "q"]:
                logger.info("👋 До свидания!")
                break
            
            print("\n" + "=" * 70)
            print(f"Обработка задачи: {user_task}")
            print("=" * 70)
            
            # Создаём начальный state
            initial_state: AgentState = {
                "task": user_task,
                "max_iterations": config.max_iterations,
                "disable_web_search": False,
                "model": None,
                "temperature": config.temperature,
                "intent_result": None,
                "plan": "",
                "context": "",
                "tests": "",
                "code": "",
                "validation_results": {},
                "debug_result": None,
                "reflection_result": None,
                "iteration": 0,
                "task_id": "",
                "enable_sse": False,
                "file_path": None,
                "file_context": None
            }
            
            # Запускаем граф синхронно
            logger.info("\n🔄 Запускаю workflow...")
            final_state = graph.invoke(initial_state)
            
            # Получаем результаты
            intent_result = final_state.get("intent_result")
            plan = final_state.get("plan", "")
            context = final_state.get("context", "")
            tests = final_state.get("tests", "")
            code = final_state.get("code", "")
            validation_results = final_state.get("validation_results", {})
            reflection_result = final_state.get("reflection_result")
            
            # Обработка приветствий
            if intent_result and intent_result.type == "greeting":
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
                continue
            
            # Выводим результаты
            print("\n" + "=" * 70)
            print("📊 РЕЗУЛЬТАТЫ")
            print("=" * 70)
            
            if intent_result:
                print(f"\n📋 Намерение: {intent_result.type} (уверенность: {intent_result.confidence:.2f})")
            
            if plan:
                print(f"\n📝 План создан (размер: {len(plan)} символов)")
            
            if context:
                print(f"📚 Контекст собран (размер: {len(context)} символов)")
            
            if tests:
                print(f"🧪 Тесты сгенерированы (размер: {len(tests)} символов)")
            
            if code:
                print(f"💻 Код сгенерирован (размер: {len(code)} символов)")
            
            if reflection_result:
                print(f"\n📋 Оценка системы:")
                print(f"   Planning:  {reflection_result.planning_score:.2f}")
                print(f"   Research:  {reflection_result.research_score:.2f}")
                print(f"   Testing:   {reflection_result.testing_score:.2f}")
                print(f"   Coding:    {reflection_result.coding_score:.2f}")
                print(f"   Overall:   {reflection_result.overall_score:.2f}")
                
                print(f"\n📝 Анализ:")
                print(f"   {reflection_result.analysis[:300]}")
                
                if reflection_result.improvements:
                    print(f"\n💡 Улучшения:")
                    print(f"   {reflection_result.improvements[:300]}")
            
            # Статус валидации
            if validation_results:
                print(f"\n✅ Валидация:")
                if tests:
                    pytest_status = "✅" if validation_results.get("pytest", {}).get("success", False) else "❌"
                    print(f"   pytest: {pytest_status}")
                mypy_status = "✅" if validation_results.get("mypy", {}).get("success", False) else "❌"
                bandit_status = "✅" if validation_results.get("bandit", {}).get("success", False) else "❌"
                print(f"   mypy: {mypy_status}")
                print(f"   bandit: {bandit_status}")
            
            # Сохраняем артефакты
            if code or tests:
                try:
                    artifact_saver = ArtifactSaver()
                    artifacts_dir = artifact_saver.save_all_artifacts(
                        task=user_task,
                        code=code,
                        tests=tests,
                        reflection_data={
                            "planning_score": reflection_result.planning_score if reflection_result else 0.0,
                            "research_score": reflection_result.research_score if reflection_result else 0.0,
                            "testing_score": reflection_result.testing_score if reflection_result else 0.0,
                            "coding_score": reflection_result.coding_score if reflection_result else 0.0,
                            "overall_score": reflection_result.overall_score if reflection_result else 0.0,
                            "analysis": reflection_result.analysis if reflection_result else "",
                            "improvements": reflection_result.improvements if reflection_result else "",
                            "should_retry": reflection_result.should_retry if reflection_result else False
                        } if reflection_result else {},
                        metrics={
                            "planning": reflection_result.planning_score if reflection_result else 0.0,
                            "research": reflection_result.research_score if reflection_result else 0.0,
                            "testing": reflection_result.testing_score if reflection_result else 0.0,
                            "coding": reflection_result.coding_score if reflection_result else 0.0,
                            "overall": reflection_result.overall_score if reflection_result else 0.0
                        } if reflection_result else {}
                    )
                    if artifacts_dir:
                        print(f"\n💾 Артефакты сохранены в: {artifacts_dir}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка сохранения артефактов: {e}", error=e)
            
            print("\n" + "=" * 70)
            
            # Предложение улучшить
            if reflection_result and reflection_result.should_retry and reflection_result.overall_score < 0.7:
                retry_input = input("\n❓ Качество ниже порога. Хотите улучшить? (y/n): ").strip().lower()
                if retry_input == "y":
                    logger.info("🔄 Повторная попытка...")
                    print("   (Повторная попытка будет реализована в следующих версиях)")
            elif reflection_result:
                improve_input = input("\n❓ Хотите улучшить результат? (y/n): ").strip().lower()
                if improve_input == "y":
                    logger.info("💡 Улучшение результата...")
                    print("   (Функция улучшения будет реализована в следующих версиях)")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Прервано пользователем")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке задачи: {e}")
            import traceback
            traceback.print_exc()
            print("\nПродолжаем работу...\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 До свидания!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
