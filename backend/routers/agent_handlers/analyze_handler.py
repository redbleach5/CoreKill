"""Handler для режима анализа проекта."""
import asyncio
import uuid
from typing import AsyncGenerator, Optional, List

from agents.researcher import ResearcherAgent
from agents.chat import get_chat_agent
from agents.conversation import get_conversation_memory
from utils.config import get_config
from utils.model_checker import TaskComplexity
from utils.ui_delays import ui_sleep
from backend.sse_manager import SSEManager
from infrastructure.model_router import get_model_router
from utils.logger import get_logger

logger = get_logger()


async def run_analyze_stream(
    task: str,
    model: str,
    temperature: float,
    project_path: Optional[str] = None,
    file_extensions: Optional[List[str]] = None,
    conversation_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Обрабатывает запрос на анализ проекта.
    
    Workflow:
    1. Индексирует кодовую базу через ContextEngine
    2. Собирает контекст релевантных файлов
    3. Генерирует отчёт через ChatAgent
    
    Args:
        task: Запрос пользователя на анализ
        model: Модель Ollama
        temperature: Температура генерации
        project_path: Путь к проекту для анализа
        file_extensions: Расширения файлов для индексации
        conversation_id: ID диалога для сохранения контекста
        
    Yields:
        SSE события с результатами анализа
    """
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or task_id
    
    config = get_config()
    
    # Проверяем, указан ли путь к проекту
    if not project_path:
        logger.warning("⚠️ Не указан путь к проекту для анализа")
        yield await SSEManager.stream_error(
            stage="analyze",
            error_message="Для анализа необходимо выбрать папку проекта. Используйте кнопку 'Выбрать папку' в IDE панели."
        )
        return
    
    # Отправляем stage_start для intent
    yield await SSEManager.stream_stage_start(
        stage="intent",
        message="Определяю намерение..."
    )
    await ui_sleep()
    
    yield await SSEManager.stream_stage_end(
        stage="intent",
        message="Намерение определено: analyze",
        result={"type": "analyze", "confidence": 0.95}
    )
    await ui_sleep()
    
    # Stage: indexing - индексация проекта
    yield await SSEManager.stream_stage_start(
        stage="indexing",
        message=f"Индексирую проект: {project_path}..."
    )
    await ui_sleep()
    
    try:
        # Собираем контекст из проекта
        researcher = ResearcherAgent()
        
        codebase_context = await asyncio.to_thread(
            researcher.research,
            query=task,
            intent_type="analyze",
            disable_web_search=True,
            project_path=project_path,
            file_extensions=file_extensions or [".py"]
        )
        
        if not codebase_context:
            logger.warning("⚠️ Не удалось собрать контекст из проекта")
            yield await SSEManager.stream_stage_end(
                stage="indexing",
                message="Проект проиндексирован, но релевантный контекст не найден",
                result={"context_length": 0}
            )
        else:
            yield await SSEManager.stream_stage_end(
                stage="indexing",
                message=f"Проект проиндексирован ({len(codebase_context)} символов контекста)",
                result={"context_length": len(codebase_context)}
            )
        await ui_sleep()
        
        # Stage: analysis - генерация отчёта
        yield await SSEManager.stream_stage_start(
            stage="analysis",
            message="Анализирую кодовую базу..."
        )
        await ui_sleep()
        
        # Выбираем модель через SmartModelRouter
        router = get_model_router()
        try:
            model_selection = router.select_model_for_complexity(
                complexity=TaskComplexity.COMPLEX,
                task_type="chat"
            )
            analyze_model = model_selection.model
            logger.info(f"🤖 Модель для анализа: {analyze_model}")
        except RuntimeError:
            analyze_model = model or config.default_model
        
        # Генерируем отчёт через ChatAgent
        chat_agent = get_chat_agent(model=analyze_model, temperature=temperature)
        
        analysis_response = await asyncio.to_thread(
            chat_agent.analyze_project,
            task=task,
            codebase_context=codebase_context or "Контекст не найден",
            project_path=project_path
        )
        
        analysis_text = analysis_response.content
        
        yield await SSEManager.stream_stage_end(
            stage="analysis",
            message=analysis_text,
            result={
                "type": "analyze",
                "analysis": analysis_text,
                "model_used": analysis_response.model_used
            }
        )
        await ui_sleep()
        
        # Сохраняем в историю диалога
        conv_memory = get_conversation_memory()
        conv_memory.add_message(conv_id, "user", task)
        conv_memory.add_message(conv_id, "assistant", analysis_text)
        
        # Финальный результат
        yield await SSEManager.stream_final_result(
            task_id=task_id,
            results={
                "task": task,
                "intent": {
                    "type": "analyze",
                    "confidence": 0.95,
                    "description": "Анализ проекта"
                },
                "analysis": analysis_text,
                "context_length": len(codebase_context) if codebase_context else 0,
                "project_path": project_path,
                "conversation_id": conv_id
            },
            metrics={
                "planning": 0.0,
                "research": 1.0,
                "testing": 0.0,
                "coding": 0.0,
                "overall": 0.8
            }
        )
        await asyncio.sleep(0.1)
        
        logger.info(f"✅ Анализ проекта завершён ({len(analysis_text)} символов)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа проекта: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="analyze",
            error_message=f"Ошибка анализа проекта: {str(e)}"
        )
