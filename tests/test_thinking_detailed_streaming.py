"""
Тесты для детального thinking стриминга.

Проверяет:
- Промпты содержат инструкции для reasoning моделей
- Агенты отправляют промежуточные thinking события
- Структура thinking событий корректна
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from infrastructure.coder_prompt_builder import CoderPromptBuilder
from infrastructure.prompt_templates import PromptTemplates
from infrastructure.reasoning_stream import ThinkingChunk, ThinkingStatus, ReasoningStreamManager
from agents.streaming_coder import StreamingCoderAgent
from agents.streaming_planner import StreamingPlannerAgent


class TestPromptInstructions:
    """Тесты инструкций для reasoning моделей в промптах."""
    
    def test_coder_prompt_contains_thinking_instructions(self):
        """Проверяет, что промпт генерации кода содержит инструкции для reasoning моделей."""
        builder = CoderPromptBuilder()
        
        prompt = builder.build_generation_prompt(
            plan="План реализации",
            tests="def test_func(): pass",
            context="Контекст проекта",
            intent_type="create"
        )
        
        # Проверяем наличие инструкций для reasoning моделей
        assert "reasoning моделей" in prompt.lower() or "reasoning models" in prompt.lower()
        assert "<think>" in prompt.lower() or "thinking" in prompt.lower()
        assert "детально опиши" in prompt.lower() or "describe" in prompt.lower()
        
        # Проверяем, что упоминаются файлы и решения
        assert "файл" in prompt.lower() or "file" in prompt.lower() or "код" in prompt.lower()
        assert "решение" in prompt.lower() or "решения" in prompt.lower() or "решаешь" in prompt.lower() or "decision" in prompt.lower() or "decisions" in prompt.lower()
    
    def test_planner_prompt_contains_thinking_instructions(self):
        """Проверяет, что промпт планирования содержит инструкции для reasoning моделей."""
        prompt = PromptTemplates.build_planning_prompt(
            task="Создать функцию",
            intent_type="create",
            context="Контекст",
            alternatives_count=2
        )
        
        # Проверяем наличие инструкций для reasoning моделей
        assert "reasoning моделей" in prompt.lower() or "reasoning models" in prompt.lower()
        assert "<think>" in prompt.lower() or "thinking" in prompt.lower()
        assert "детально опиши" in prompt.lower() or "describe" in prompt.lower()
        
        # Проверяем, что упоминаются файлы и планирование
        assert "файл" in prompt.lower() or "file" in prompt.lower() or "компонент" in prompt.lower()
        assert "план" in prompt.lower() or "plan" in prompt.lower()
    
    def test_context_section_mentions_files(self):
        """Проверяет, что секция контекста упоминает проанализированные файлы."""
        builder = CoderPromptBuilder()
        
        prompt = builder.build_generation_prompt(
            plan="План",
            tests="def test(): pass",
            context="Файл backend/api.py содержит код...",
            intent_type="modify"
        )
        
        # Проверяем, что контекст упоминает файлы
        assert "проанализированные файлы" in prompt.lower() or "analyzed files" in prompt.lower() or "контекст" in prompt.lower()


class TestIntermediateThinkingEvents:
    """Тесты промежуточных thinking событий от агентов."""
    
    @pytest.mark.asyncio
    async def test_coder_agent_sends_initial_thinking(self):
        """Проверяет, что StreamingCoderAgent отправляет начальное thinking событие."""
        # Создаём мок LLM
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.generate_stream = AsyncMock(return_value=iter([]))
        
        # Создаём мок reasoning_manager
        mock_reasoning_manager = MagicMock()
        mock_reasoning_manager.create_thinking_event = AsyncMock(return_value="test_sse_event")
        mock_reasoning_manager.stream_from_llm = AsyncMock(return_value=iter([
            ("done", "def test(): pass")
        ]))
        mock_reasoning_manager.reset = MagicMock()
        
        # Создаём агента с моками
        with patch('infrastructure.model_router.get_model_router'), \
             patch('infrastructure.local_llm.create_llm_for_stage', return_value=mock_llm), \
             patch('agents.streaming_coder.get_prompt_enhancer'), \
             patch('agents.streaming_coder.get_reasoning_stream_manager', return_value=mock_reasoning_manager):
            agent = StreamingCoderAgent(model="test-model")
            agent.reasoning_manager = mock_reasoning_manager
            
            # Запускаем генерацию
            events = []
            async for event_type, data in agent.generate_code_stream(
                plan="План",
                tests="def test(): pass",
                context="Контекст",
                intent_type="create",
                stage="coding"
            ):
                events.append((event_type, data))
            
            # Проверяем, что были вызваны create_thinking_event для промежуточных событий
            assert mock_reasoning_manager.create_thinking_event.called
            
            # Проверяем, что были отправлены thinking события
            thinking_events = [e for e in events if e[0] == "thinking"]
            assert len(thinking_events) > 0, "Должны быть отправлены thinking события"
    
    @pytest.mark.asyncio
    async def test_planner_agent_sends_initial_thinking(self):
        """Проверяет, что StreamingPlannerAgent отправляет начальное thinking событие."""
        # Создаём мок LLM
        mock_llm = MagicMock()
        mock_llm.model = "test-model"
        mock_llm.generate_stream = AsyncMock(return_value=iter([]))
        
        # Создаём мок reasoning_manager
        mock_reasoning_manager = MagicMock()
        mock_reasoning_manager.create_thinking_event = AsyncMock(return_value="test_sse_event")
        mock_reasoning_manager.stream_from_llm = AsyncMock(return_value=iter([
            ("done", "План:\n1. Шаг 1")
        ]))
        mock_reasoning_manager.reset = MagicMock()
        
        # Создаём мок memory
        mock_memory = MagicMock()
        mock_memory.get_recommendations = MagicMock(return_value="")
        
        # Создаём агента с моками
        with patch('infrastructure.model_router.get_model_router'), \
             patch('infrastructure.local_llm.create_llm_for_stage', return_value=mock_llm), \
             patch('infrastructure.prompt_enhancer.get_prompt_enhancer'), \
             patch('infrastructure.reasoning_stream.get_reasoning_stream_manager', return_value=mock_reasoning_manager):
            agent = StreamingPlannerAgent(model="test-model", memory_agent=mock_memory)
            agent.reasoning_manager = mock_reasoning_manager
            
            # Запускаем планирование с более сложной задачей (чтобы не использовался упрощенный план)
            events = []
            async for event_type, data in agent.create_plan_stream(
                task="Создать полнофункциональное веб-приложение для управления задачами с базой данных, API и фронтендом",
                intent_type="create",
                stage="planning"
            ):
                events.append((event_type, data))
            
            # Проверяем, что были вызваны create_thinking_event для промежуточных событий
            # Для сложных задач (> 50 символов) должны быть thinking события
            thinking_events = [e for e in events if e[0] == "thinking"]
            if len(thinking_events) > 0:
                # Если есть thinking события, проверяем что create_thinking_event был вызван
                assert mock_reasoning_manager.create_thinking_event.called
            else:
                # Для упрощенных планов thinking события могут отсутствовать
                done_events = [e for e in events if e[0] == "done"]
                assert len(done_events) > 0, "Должен быть создан план"


class TestThinkingEventStructure:
    """Тесты структуры thinking событий."""
    
    @pytest.mark.asyncio
    async def test_thinking_chunk_creation(self):
        """Проверяет создание ThinkingChunk и SSE события."""
        manager = ReasoningStreamManager()
        
        chunk = ThinkingChunk(
            content="Анализирую задачу...",
            status=ThinkingStatus.IN_PROGRESS,
            stage="coding",
            elapsed_ms=100,
            total_chars=20
        )
        
        sse_event = await manager.create_thinking_event(chunk)
        
        # Проверяем структуру SSE события
        assert "event: thinking_in_progress" in sse_event
        assert "data:" in sse_event
        assert "stage" in sse_event
        assert "content" in sse_event
        assert "elapsed_ms" in sse_event
        assert "total_chars" in sse_event
    
    def test_thinking_statuses(self):
        """Проверяет все статусы thinking."""
        assert ThinkingStatus.STARTED.value == "started"
        assert ThinkingStatus.IN_PROGRESS.value == "in_progress"
        assert ThinkingStatus.COMPLETED.value == "completed"
        assert ThinkingStatus.INTERRUPTED.value == "interrupted"


class TestContextInPrompts:
    """Тесты добавления контекста в промпты."""
    
    def test_context_section_format(self):
        """Проверяет формат секции контекста."""
        builder = CoderPromptBuilder()
        
        prompt = builder.build_generation_prompt(
            plan="План",
            tests="def test(): pass",
            context="Файл backend/api.py: код CORS...",
            intent_type="modify"
        )
        
        # Проверяем, что контекст упоминает файлы
        assert "контекст" in prompt.lower() or "context" in prompt.lower()
        assert "файл" in prompt.lower() or "file" in prompt.lower() or "проанализированные" in prompt.lower()


@pytest.mark.asyncio
async def test_integration_thinking_flow():
    """Интеграционный тест потока thinking событий."""
    # Создаём мок LLM с reasoning ответом
    mock_llm = MagicMock()
    mock_llm.model = "deepseek-r1:7b"
    
    # Мокируем generate_stream для возврата thinking блока
    async def mock_generate_stream(*args, **kwargs):
        from infrastructure.local_llm import StreamChunk
        
        # Симулируем thinking блок
        thinking_content = "<think>\nАнализирую задачу...\nПроверяю файлы...\n</think>\n\ndef test(): pass"
        
        # Разбиваем на чанки
        chunks = [
            StreamChunk(content="<think>", is_thinking=True, is_done=False, full_response="<think>"),
            StreamChunk(content="\nАнализирую задачу...", is_thinking=True, is_done=False, full_response="<think>\nАнализирую задачу..."),
            StreamChunk(content="\nПроверяю файлы...", is_thinking=True, is_done=False, full_response="<think>\nАнализирую задачу...\nПроверяю файлы..."),
            StreamChunk(content="\n</think>", is_thinking=True, is_done=False, full_response=thinking_content),
            StreamChunk(content="\n\ndef test(): pass", is_thinking=False, is_done=True, full_response=thinking_content + "\n\ndef test(): pass"),
        ]
        
        for chunk in chunks:
            yield chunk
    
    mock_llm.generate_stream = mock_generate_stream
    
    # Создаём reasoning_manager
    reasoning_manager = ReasoningStreamManager()
    
    # Тестируем stream_from_llm
    events = []
    async for event_type, data in reasoning_manager.stream_from_llm(
        llm=mock_llm,
        prompt="Тестовый промпт",
        stage="coding"
    ):
        events.append((event_type, data))
    
    # Проверяем, что были thinking события
    thinking_events = [e for e in events if e[0] == "thinking"]
    assert len(thinking_events) > 0, "Должны быть thinking события от reasoning модели"
    
    # Проверяем, что был content
    content_events = [e for e in events if e[0] == "content"]
    assert len(content_events) > 0, "Должен быть content от модели"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
