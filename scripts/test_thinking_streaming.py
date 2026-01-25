#!/usr/bin/env python3
"""
Простой скрипт для тестирования детального thinking стриминга.

Проверяет:
- Промпты содержат инструкции для reasoning моделей
- Структура thinking событий корректна
- Агенты могут создавать thinking события

Запуск: python scripts/test_thinking_streaming.py
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from infrastructure.coder_prompt_builder import CoderPromptBuilder
from infrastructure.prompt_templates import PromptTemplates
from infrastructure.reasoning_stream import ThinkingChunk, ThinkingStatus, ReasoningStreamManager
from datetime import datetime
import asyncio


def test_prompt_instructions():
    """Тест 1: Проверка инструкций для reasoning моделей в промптах."""
    print("=" * 60)
    print("ТЕСТ 1: Проверка инструкций для reasoning моделей в промптах")
    print("=" * 60)
    
    # Тест промпта генерации кода
    builder = CoderPromptBuilder()
    prompt = builder.build_generation_prompt(
        plan="План реализации функции",
        tests="def test_func(): assert func() == 'result'",
        context="Файл backend/api.py содержит код CORS...",
        intent_type="create"
    )
    
    checks = {
        "reasoning моделей": "reasoning моделей" in prompt.lower() or "reasoning models" in prompt.lower(),
        "<think> блоки": "<think>" in prompt.lower() or "thinking" in prompt.lower(),
        "детальное описание": "детально опиши" in prompt.lower() or "describe" in prompt.lower(),
        "файлы/код": "файл" in prompt.lower() or "file" in prompt.lower() or "код" in prompt.lower() or "code" in prompt.lower(),
        "решения/подход": "решение" in prompt.lower() or "decision" in prompt.lower() or "подход" in prompt.lower() or "approach" in prompt.lower(),
    }
    
    print("\nПроверка промпта генерации кода:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    # Тест промпта планирования
    planning_prompt = PromptTemplates.build_planning_prompt(
        task="Создать функцию для обработки данных",
        intent_type="create",
        context="Контекст проекта",
        alternatives_count=2
    )
    
    planning_checks = {
        "reasoning моделей": "reasoning моделей" in planning_prompt.lower() or "reasoning models" in planning_prompt.lower(),
        "<think> блоки": "<think>" in planning_prompt.lower() or "thinking" in planning_prompt.lower(),
        "детальное описание": "детально опиши" in planning_prompt.lower() or "describe" in planning_prompt.lower(),
        "файлы/компоненты": "файл" in planning_prompt.lower() or "file" in planning_prompt.lower() or "компонент" in planning_prompt.lower(),
    }
    
    print("\nПроверка промпта планирования:")
    for check_name, passed in planning_checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ 1 ПРОЙДЕН: Все инструкции для reasoning моделей присутствуют в промптах")
    else:
        print("\n❌ ТЕСТ 1 НЕ ПРОЙДЕН: Некоторые инструкции отсутствуют")
    
    return all_passed


async def test_thinking_event_structure():
    """Тест 2: Проверка структуры thinking событий."""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Проверка структуры thinking событий")
    print("=" * 60)
    
    manager = ReasoningStreamManager()
    
    # Создаём thinking chunk
    chunk = ThinkingChunk(
        content="Анализирую задачу и проверяю файлы...",
        status=ThinkingStatus.IN_PROGRESS,
        stage="coding",
        elapsed_ms=150,
        total_chars=45
    )
    
    # Создаём SSE событие
    sse_event = await manager.create_thinking_event(chunk)
    
    checks = {
        "event: thinking_in_progress": "event: thinking_in_progress" in sse_event,
        "data:": "data:" in sse_event,
        "stage": '"stage"' in sse_event or "'stage'" in sse_event,
        "content": '"content"' in sse_event or "'content'" in sse_event,
        "elapsed_ms": '"elapsed_ms"' in sse_event or "'elapsed_ms'" in sse_event,
        "total_chars": '"total_chars"' in sse_event or "'total_chars'" in sse_event,
    }
    
    print("\nПроверка структуры SSE события:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    # Проверяем все статусы
    print("\nПроверка статусов ThinkingStatus:")
    status_checks = {
        "STARTED": ThinkingStatus.STARTED.value == "started",
        "IN_PROGRESS": ThinkingStatus.IN_PROGRESS.value == "in_progress",
        "COMPLETED": ThinkingStatus.COMPLETED.value == "completed",
        "INTERRUPTED": ThinkingStatus.INTERRUPTED.value == "interrupted",
    }
    
    for status_name, passed in status_checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {status_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ 2 ПРОЙДЕН: Структура thinking событий корректна")
    else:
        print("\n❌ ТЕСТ 2 НЕ ПРОЙДЕН: Проблемы со структурой событий")
    
    return all_passed


def test_context_in_prompts():
    """Тест 3: Проверка контекста в промптах."""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Проверка контекста в промптах")
    print("=" * 60)
    
    builder = CoderPromptBuilder()
    
    prompt = builder.build_generation_prompt(
        plan="План",
        tests="def test(): pass",
        context="Файл backend/api.py: код CORS с настройками...",
        intent_type="modify"
    )
    
    checks = {
        "контекст упоминается": "контекст" in prompt.lower() or "context" in prompt.lower(),
        "файлы упоминаются": "файл" in prompt.lower() or "file" in prompt.lower() or "проанализированные" in prompt.lower(),
    }
    
    print("\nПроверка контекста в промпте:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ 3 ПРОЙДЕН: Контекст правильно добавлен в промпты")
    else:
        print("\n❌ ТЕСТ 3 НЕ ПРОЙДЕН: Проблемы с контекстом в промптах")
    
    return all_passed


async def test_thinking_chunk_creation():
    """Тест 4: Проверка создания thinking chunks с разными статусами."""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Проверка создания thinking chunks")
    print("=" * 60)
    
    manager = ReasoningStreamManager()
    
    chunks = [
        ThinkingChunk(
            content="",
            status=ThinkingStatus.STARTED,
            stage="coding",
            elapsed_ms=0,
            total_chars=0
        ),
        ThinkingChunk(
            content="Анализирую задачу...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=100,
            total_chars=20
        ),
        ThinkingChunk(
            content="Задача проанализирована. Начинаю генерацию...",
            status=ThinkingStatus.COMPLETED,
            stage="coding",
            elapsed_ms=500,
            total_chars=50
        ),
    ]
    
    print("\nПроверка создания SSE событий для разных статусов:")
    all_passed = True
    
    for i, chunk in enumerate(chunks, 1):
        sse_event = await manager.create_thinking_event(chunk)
        
        event_type = f"thinking_{chunk.status.value}"
        check_passed = f"event: {event_type}" in sse_event
        
        status = "✅" if check_passed else "❌"
        print(f"  {status} Статус {chunk.status.value}: {check_passed}")
        
        if not check_passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ 4 ПРОЙДЕН: Thinking chunks создаются корректно")
    else:
        print("\n❌ ТЕСТ 4 НЕ ПРОЙДЕН: Проблемы с созданием thinking chunks")
    
    return all_passed


def test_prompt_examples():
    """Тест 5: Проверка примеров в промптах."""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Проверка примеров детального thinking в промптах")
    print("=" * 60)
    
    builder = CoderPromptBuilder()
    prompt = builder.build_generation_prompt(
        plan="План",
        tests="def test(): pass",
        context="Контекст",
        intent_type="create"
    )
    
    # Проверяем наличие примеров или инструкций
    checks = {
        "пример thinking": "пример" in prompt.lower() or "example" in prompt.lower(),
        "анализ файлов": "анализируешь" in prompt.lower() or "analyze" in prompt.lower(),
        "принятие решений": "решение" in prompt.lower() or "decision" in prompt.lower(),
    }
    
    print("\nПроверка примеров в промпте:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ 5 ПРОЙДЕН: Примеры присутствуют в промптах")
    else:
        print("\n⚠️  ТЕСТ 5 ЧАСТИЧНО: Некоторые примеры могут отсутствовать (не критично)")
    
    return all_passed


async def main():
    """Основная функция для запуска всех тестов."""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ДЕТАЛЬНОГО THINKING СТРИМИНГА")
    print("=" * 60)
    print("\nПроверка реализации улучшений для детального thinking стриминга...")
    
    results = []
    
    # Синхронные тесты
    results.append(("Промпты с инструкциями", test_prompt_instructions()))
    results.append(("Контекст в промптах", test_context_in_prompts()))
    results.append(("Примеры в промптах", test_prompt_examples()))
    
    # Асинхронные тесты
    results.append(("Структура thinking событий", await test_thinking_event_structure()))
    results.append(("Создание thinking chunks", await test_thinking_chunk_creation()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"{status}: {test_name}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Не пройдено: {total - passed}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Реализация работает корректно.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) не пройдено. Проверьте реализацию.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
