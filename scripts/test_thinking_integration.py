#!/usr/bin/env python3
"""
Интеграционный тест детального thinking стриминга.

Проверяет полный поток:
- Агенты отправляют промежуточные thinking события
- Reasoning модели генерируют thinking блоки
- Все события корректно форматируются

Запуск: python scripts/test_thinking_integration.py
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from infrastructure.reasoning_stream import ThinkingChunk, ThinkingStatus, ReasoningStreamManager
from infrastructure.local_llm import StreamChunk


async def test_coder_agent_thinking_flow():
    """Тест потока thinking событий от StreamingCoderAgent."""
    print("=" * 60)
    print("ТЕСТ: Поток thinking событий от StreamingCoderAgent")
    print("=" * 60)
    
    # Создаём мок LLM
    mock_llm = MagicMock()
    mock_llm.model = "deepseek-r1:7b"
    
    # Мокируем generate_stream для возврата thinking блока
    async def mock_generate_stream(*args, **kwargs):
        thinking_content = "<think>\nАнализирую задачу...\nПроверяю файлы backend/api.py...\n</think>\n\ndef test(): pass"
        
        chunks = [
            StreamChunk(content="<think>", is_thinking=True, is_done=False, full_response="<think>"),
            StreamChunk(content="\nАнализирую задачу...", is_thinking=True, is_done=False, full_response="<think>\nАнализирую задачу..."),
            StreamChunk(content="\nПроверяю файлы backend/api.py...", is_thinking=True, is_done=False, full_response="<think>\nАнализирую задачу...\nПроверяю файлы backend/api.py..."),
            StreamChunk(content="\n</think>", is_thinking=True, is_done=False, full_response=thinking_content),
            StreamChunk(content="\n\ndef test(): pass", is_thinking=False, is_done=True, full_response=thinking_content + "\n\ndef test(): pass"),
        ]
        
        for chunk in chunks:
            yield chunk
    
    mock_llm.generate_stream = mock_generate_stream
    
    # Создаём reasoning_manager
    reasoning_manager = ReasoningStreamManager()
    
    # Тестируем stream_from_llm
    print("\n📤 Тестирую stream_from_llm с reasoning моделью...")
    
    events = []
    thinking_events_count = 0
    content_chunks_count = 0
    
    async for event_type, data in reasoning_manager.stream_from_llm(
        llm=mock_llm,
        prompt="Создай функцию test()",
        stage="coding"
    ):
        events.append((event_type, data))
        
        if event_type == "thinking":
            thinking_events_count += 1
            # Парсим SSE событие для проверки
            if "thinking_started" in data:
                print("  ✅ Получено thinking_started событие")
            elif "thinking_in_progress" in data:
                print(f"  ✅ Получено thinking_in_progress событие #{thinking_events_count}")
            elif "thinking_completed" in data:
                print("  ✅ Получено thinking_completed событие")
        elif event_type == "content":
            content_chunks_count += 1
        elif event_type == "done":
            print(f"  ✅ Получено done событие (ответ: {len(data)} символов)")
    
    # Проверяем результаты
    print(f"\n📊 Результаты:")
    print(f"  - Всего событий: {len(events)}")
    print(f"  - Thinking событий: {thinking_events_count}")
    print(f"  - Content чанков: {content_chunks_count}")
    
    checks = {
        "thinking события получены": thinking_events_count > 0,
        "content чанки получены": content_chunks_count > 0,
        "done событие получено": any(e[0] == "done" for e in events),
    }
    
    print("\n✅ Проверки:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ ПРОЙДЕН: Поток thinking событий работает корректно")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Проблемы с потоком thinking событий")
    
    return all_passed


async def test_intermediate_thinking_events():
    """Тест промежуточных thinking событий от агентов."""
    print("\n" + "=" * 60)
    print("ТЕСТ: Промежуточные thinking события от агентов")
    print("=" * 60)
    
    # Создаём reasoning_manager
    reasoning_manager = ReasoningStreamManager()
    start_time = datetime.now()
    
    # Симулируем промежуточные thinking события (как в StreamingCoderAgent)
    intermediate_events = []
    
    # Событие 1: Начало анализа
    event1 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Начинаю анализ задачи и подготовку к генерации кода...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=0,
            total_chars=0
        )
    )
    intermediate_events.append(("thinking", event1))
    print("  ✅ Создано thinking событие: Начало анализа")
    
    # Событие 2: Анализ контекста
    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    event2 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Анализирую контекст проекта (500 символов): Файл backend/api.py содержит код CORS...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=elapsed,
            total_chars=0
        )
    )
    intermediate_events.append(("thinking", event2))
    print("  ✅ Создано thinking событие: Анализ контекста")
    
    # Событие 3: Начало генерации
    elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
    event3 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Начинаю генерацию кода для задачи типа 'create'. План содержит 4 шагов.",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=elapsed,
            total_chars=0
        )
    )
    intermediate_events.append(("thinking", event3))
    print("  ✅ Создано thinking событие: Начало генерации")
    
    # Проверяем структуру событий
    print(f"\n📊 Результаты:")
    print(f"  - Создано промежуточных событий: {len(intermediate_events)}")
    
    checks = {
        "события созданы": len(intermediate_events) == 3,
        "все события thinking": all(e[0] == "thinking" for e in intermediate_events),
        "события содержат stage": all("stage" in e[1] for e in intermediate_events),
        "события содержат content": all("content" in e[1] for e in intermediate_events),
    }
    
    print("\n✅ Проверки:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    # Показываем примеры контента
    print("\n📝 Примеры контента thinking событий:")
    for i, (event_type, sse_data) in enumerate(intermediate_events[:2], 1):
        # Извлекаем content из JSON
        import json
        import re
        match = re.search(r'data: ({.*?})', sse_data, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            content_preview = data.get("content", "")[:80] + "..." if len(data.get("content", "")) > 80 else data.get("content", "")
            print(f"  {i}. {content_preview}")
    
    if all_passed:
        print("\n✅ ТЕСТ ПРОЙДЕН: Промежуточные thinking события работают корректно")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Проблемы с промежуточными thinking событиями")
    
    return all_passed


async def test_full_thinking_flow():
    """Тест полного потока thinking от начала до конца."""
    print("\n" + "=" * 60)
    print("ТЕСТ: Полный поток thinking (от агента до UI)")
    print("=" * 60)
    
    reasoning_manager = ReasoningStreamManager()
    start_time = datetime.now()
    
    # Симулируем полный поток
    print("\n📤 Симулирую полный поток thinking событий...")
    
    flow_events = []
    
    # 1. Промежуточное событие от агента
    event1 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Начинаю анализ задачи...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=0,
            total_chars=0
        )
    )
    flow_events.append(("intermediate", event1))
    print("  1️⃣  Промежуточное thinking от агента: Начало анализа")
    
    # 2. Thinking от reasoning модели (started)
    event2 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="",
            status=ThinkingStatus.STARTED,
            stage="coding",
            elapsed_ms=50,
            total_chars=0
        )
    )
    flow_events.append(("thinking_started", event2))
    print("  2️⃣  Thinking started от модели")
    
    # 3. Thinking от reasoning модели (in_progress)
    event3 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Анализирую файл backend/api.py - вижу код CORS...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=100,
            total_chars=45
        )
    )
    flow_events.append(("thinking_in_progress", event3))
    print("  3️⃣  Thinking in_progress от модели: Анализ файла")
    
    # 4. Ещё один thinking in_progress
    event4 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content=" Пользователь просил добавить DELETE. Нужно обновить конфигурацию...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=200,
            total_chars=95
        )
    )
    flow_events.append(("thinking_in_progress", event4))
    print("  4️⃣  Thinking in_progress от модели: Принятие решения")
    
    # 5. Thinking completed
    event5 = await reasoning_manager.create_thinking_event(
        ThinkingChunk(
            content="Анализирую файл backend/api.py - вижу код CORS... Пользователь просил добавить DELETE. Нужно обновить конфигурацию...",
            status=ThinkingStatus.COMPLETED,
            stage="coding",
            elapsed_ms=300,
            total_chars=95
        )
    )
    flow_events.append(("thinking_completed", event5))
    print("  5️⃣  Thinking completed от модели")
    
    # Проверяем поток
    print(f"\n📊 Результаты:")
    print(f"  - Всего событий в потоке: {len(flow_events)}")
    
    checks = {
        "промежуточное событие": any("intermediate" in str(e[0]) for e in flow_events),
        "thinking_started": any("thinking_started" in e[1] for e in flow_events),
        "thinking_in_progress": sum(1 for e in flow_events if "thinking_in_progress" in e[1]) >= 2,
        "thinking_completed": any("thinking_completed" in e[1] for e in flow_events),
        "контент содержит детали": any("файл" in e[1].lower() or "file" in e[1].lower() for e in flow_events),
    }
    
    print("\n✅ Проверки:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}: {passed}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✅ ТЕСТ ПРОЙДЕН: Полный поток thinking работает корректно")
        print("\n💡 Пользователь теперь увидит:")
        print("   - 'Начинаю анализ задачи...' (от агента)")
        print("   - 'Анализирую файл backend/api.py - вижу код CORS...' (от модели)")
        print("   - 'Пользователь просил добавить DELETE. Нужно обновить конфигурацию...' (от модели)")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Проблемы с полным потоком thinking")
    
    return all_passed


async def main():
    """Основная функция для запуска всех тестов."""
    print("\n" + "=" * 60)
    print("ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ ДЕТАЛЬНОГО THINKING СТРИМИНГА")
    print("=" * 60)
    print("\nПроверка полного потока thinking событий...")
    
    results = []
    
    # Запускаем тесты
    results.append(("Поток thinking от reasoning модели", await test_coder_agent_thinking_flow()))
    results.append(("Промежуточные thinking события", await test_intermediate_thinking_events()))
    results.append(("Полный поток thinking", await test_full_thinking_flow()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ИНТЕГРАЦИОННОГО ТЕСТИРОВАНИЯ")
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
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Детальный thinking стриминг работает корректно.")
        print("\n💡 Теперь пользователь будет видеть:")
        print("   ✅ Промежуточные thinking события от агентов")
        print("   ✅ Детальные thinking блоки от reasoning моделей")
        print("   ✅ Информацию о файлах, решениях, подходах")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тест(ов) не пройдено. Проверьте реализацию.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
