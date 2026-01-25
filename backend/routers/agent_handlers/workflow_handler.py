"""Handler для режима полного workflow (code generation)."""
import asyncio
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional, List

from agents.intent import IntentAgent
from utils.config import get_config
from utils.model_checker import TaskComplexity, check_model_available
from utils.ui_delays import ui_sleep
from backend.sse_manager import SSEManager
from backend.sse_helpers import send_greeting_response
from backend.workflow_streamer import WorkflowStreamer
from backend.messages import GREETING_MESSAGE, HELP_MESSAGE
from infrastructure.workflow_graph import create_workflow_graph
from infrastructure.workflow_state import AgentState
from infrastructure.model_router import get_model_router
from infrastructure.event_store import get_event_store, EventStore
from backend.dependencies import get_memory_agent
from utils.logger import get_logger

logger = get_logger()


async def run_workflow_stream(
    task: str,
    model: str,
    temperature: float,
    disable_web_search: bool,
    max_iterations: int,
    project_path: Optional[str] = None,
    file_extensions: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """Запускает workflow агентов с SSE стримингом через LangGraph.
    
    Args:
        task: Текст задачи
        model: Модель Ollama (будет проверена на доступность)
        temperature: Температура генерации
        disable_web_search: Отключить веб-поиск
        max_iterations: Максимальное количество итераций (ограничено до 5)
        project_path: Путь к проекту для индексации кодовой базы (опционально)
        file_extensions: Расширения файлов для индексации (опционально)
        
    Yields:
        SSE события в формате text/event-stream
    """
    task_id = str(uuid.uuid4())
    
    # Создаём очередь событий для реального времени
    event_queue = EventStore.get_event_queue(task_id)
    
    # Очередь для SSE событий от фоновой задачи
    sse_queue: asyncio.Queue = asyncio.Queue()
    
    # Флаг для остановки фоновой задачи
    stop_realtime_streaming = asyncio.Event()
    
    # Фоновая задача для отправки событий в реальном времени
    async def stream_events_realtime():
        """Отправляет события из очереди в SSE поток в реальном времени.
        
        ОПТИМИЗАЦИЯ: Уменьшен таймаут с 0.1 до 0.01 для более быстрой отправки событий.
        Thinking блоки и чанки кода отправляются немедленно без задержек.
        ИСПРАВЛЕНИЕ: Добавлены heartbeat события каждые 15 секунд для предотвращения timeout.
        """
        import time
        last_heartbeat = time.time()
        HEARTBEAT_INTERVAL = 15.0  # Отправляем heartbeat каждые 15 секунд
        
        try:
            while not stop_realtime_streaming.is_set():
                try:
                    # ОПТИМИЗАЦИЯ: Уменьшен таймаут для более быстрой отправки (0.01 вместо 0.1)
                    # Это позволяет отправлять события почти мгновенно
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.01)
                    
                    # Преобразуем событие в SSE формат
                    if event.event_type == "thinking" or event.event_type.startswith("thinking_"):
                        if isinstance(event.data, str):
                            # ReasoningStreamManager всегда возвращает готовую SSE строку
                            sse_event = event.data
                        else:
                            # Fallback: если по какой-то причине data не строка,
                            # создаём событие с правильным типом (thinking_started/in_progress/etc)
                            event_type = event.event_type if event.event_type.startswith("thinking_") else "thinking_started"
                            sse_event = await SSEManager.send_event(event_type, {"content": str(event.data), "stage": "unknown"})
                    elif event.event_type == "progress":
                        # ИСПРАВЛЕНИЕ: Пробрасываем progress события для non-reasoning моделей
                        # data уже содержит готовую SSE строку от SSEManager.stream_stage_progress
                        if isinstance(event.data, str):
                            sse_event = event.data
                        else:
                            # Fallback: создаём progress событие
                            sse_event = await SSEManager.send_event("stage_progress", event.data if isinstance(event.data, dict) else {"message": str(event.data)})
                    elif event.event_type in ("plan_chunk", "test_chunk", "code_chunk"):
                        sse_event = await SSEManager.send_event(event.event_type, {"chunk": event.data})
                    elif event.event_type == "error":
                        # ИСПРАВЛЕНИЕ: Обработка error событий - если data уже строка (SSE событие), используем её,
                        # иначе создаём error событие из данных
                        if isinstance(event.data, str):
                            sse_event = event.data
                        else:
                            # event.data должен быть словарём с полями stage, message, type и т.д.
                            error_data = event.data if isinstance(event.data, dict) else {"message": str(event.data)}
                            sse_event = await SSEManager.stream_error(
                                stage=error_data.get("stage", "unknown"),
                                error_message=error_data.get("message", "Неизвестная ошибка"),
                                error_details=error_data.get("error_details", {})
                            )
                    else:
                        sse_event = await SSEManager.send_event(event.event_type, {"data": event.data})
                    
                    # ОПТИМИЗАЦИЯ: Отправляем событие немедленно без дополнительных задержек
                    await sse_queue.put(sse_event)
                    last_heartbeat = time.time()  # Обновляем время последнего события
                    # ОПТИМИЗАЦИЯ: Логируем только важные события или периодически
                    # Это уменьшает объем логов (события отправляются очень часто)
                    if event.event_type in ("error", "done", "stage_start", "stage_end"):
                        logger.debug(f"📤 Событие отправлено: {event.event_type}")
                    
                except asyncio.TimeoutError:
                    # ИСПРАВЛЕНИЕ: Отправляем heartbeat если прошло больше HEARTBEAT_INTERVAL
                    current_time = time.time()
                    if current_time - last_heartbeat > HEARTBEAT_INTERVAL:
                        heartbeat_event = await SSEManager.send_event("heartbeat", {"status": "alive"})
                        await sse_queue.put(heartbeat_event)
                        last_heartbeat = current_time
                        logger.debug("💓 Heartbeat отправлен")
                    continue
                except Exception as e:
                    logger.error(f"❌ Ошибка в stream_events_realtime: {e}", error=e)
                    break
        except asyncio.CancelledError:
            logger.debug("🛑 stream_events_realtime отменён")
        finally:
            logger.debug("🧹 stream_events_realtime завершён, очищаем очередь")
            while not sse_queue.empty():
                try:
                    sse_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
    
    # Запускаем фоновую задачу
    realtime_task: Optional[asyncio.Task] = None
    try:
        realtime_task = asyncio.create_task(stream_events_realtime())
    except Exception as e:
        logger.error(f"❌ Ошибка создания фоновой задачи: {e}", error=e)
        realtime_task = None
    
    # ИСПРАВЛЕНИЕ: Быстрая проверка приветствия только для простых приветствий
    # Если приветствие содержит вопросы - используем ChatAgent с веб-поиском
    if IntentAgent.is_greeting_fast(task):
        # Проверяем, есть ли в запросе вопросы или команды рассказать
        # Если есть - используем ChatAgent вместо простого greeting ответа
        has_question = any(indicator in task.lower() for indicator in 
                          ["?", "знаешь", "расскажи", "do you know", "tell me", "what", "who", "when", "where"])
        has_tell_command = any(cmd in task.lower() for cmd in 
                              ["расскажи", "опиши", "tell", "describe", "explain"])
        
        # Если это простое приветствие без вопросов - быстрый ответ
        if not (has_question or has_tell_command) or len(task.split()) <= 3:
            async for event in send_greeting_response(
                task_id=task_id,
                greeting_message=GREETING_MESSAGE,
                task=task
            ):
                yield event
            return
        else:
            # Приветствие с вопросом - используем ChatAgent (он проверит необходимость веб-поиска)
            logger.info("💬 Приветствие содержит вопрос - используем ChatAgent с веб-поиском")
            # Продолжаем выполнение - запрос будет обработан через chat режим
    
    # Ограничиваем max_iterations
    config = get_config()
    max_iterations = min(max_iterations, config.max_iterations, 5)
    
    # ПРОВЕРКА ПАМЯТИ: ищем идентичную/очень похожую задачу
    memory_agent = get_memory_agent()
    
    similar_task = await asyncio.to_thread(
        memory_agent.find_exact_or_very_similar_task,
        query=task,
        intent_type=None,
        min_success=0.8,
        similarity_threshold=0.85
    )
    
    if similar_task:
        similarity = similar_task.get("similarity", 0.0)
        success = similar_task.get("success", 0.0)
        has_code = similar_task.get("has_code", False)
        
        logger.info(
            f"🎯 Найдена очень похожая задача в памяти "
            f"(схожесть: {similarity:.2f}, успех: {success:.2f}, код: {'есть' if has_code else 'нет'})"
        )
        
        if similarity >= 0.9 and success >= 0.85 and has_code:
            logger.info("✅ Задача уже решалась успешно - используем готовое решение из памяти")
            
            yield await SSEManager.stream_stage_start(
                stage="memory_check",
                message="Проверяю память..."
            )
            # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
            # await ui_sleep()
            
            yield await SSEManager.stream_stage_end(
                stage="memory_check",
                message=f"Найдено готовое решение (схожесть: {similarity:.1%})",
                result={"similarity": similarity, "success": success}
            )
            # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
            # await ui_sleep()
            
            code_preview = similar_task.get("code_preview", similar_task.get("code", ""))
            plan_preview = similar_task.get("plan_preview", similar_task.get("plan", ""))
            
            memory_message = (
                f"🎯 Найдено готовое решение для похожей задачи!\n\n"
                f"**Исходная задача:** {similar_task.get('task', '')[:200]}...\n"
                f"**Успешность:** {success:.1%}\n"
                f"**Схожесть:** {similarity:.1%}\n\n"
            )
            
            if plan_preview:
                memory_message += f"**План из памяти:**\n{plan_preview[:500]}...\n\n"
            
            if code_preview:
                memory_message += f"**Код из памяти:**\n```\n{code_preview[:1000]}...\n```\n\n"
            
            memory_message += (
                "💡 Система может использовать это решение или создать новое. "
                "Продолжаю с полным циклом для адаптации под текущую задачу."
            )
            
            yield await SSEManager.stream_stage_end(
                stage="memory_reuse",
                message=memory_message,
                result={
                    "similarity": similarity,
                    "success": success,
                    "has_code": has_code,
                    "code_preview": code_preview[:500] if code_preview else "",
                    "plan_preview": plan_preview[:300] if plan_preview else ""
                }
            )
            # ОПТИМИЗАЦИЯ: Убрана задержка для более быстрого стриминга
            # await ui_sleep()
            
            logger.info("🔄 Продолжаю workflow с контекстом из памяти")
        else:
            logger.info(f"ℹ️ Найдена похожая задача, но схожесть недостаточна для пропуска workflow (схожесть: {similarity:.2f})")
    
    # УМНЫЙ ВЫБОР МОДЕЛИ
    model_to_use = (model.strip() if model and isinstance(model, str) and model.strip() else None)
    task_complexity = TaskComplexity.MEDIUM
    
    intent_agent = IntentAgent(lazy_llm=True)
    task_complexity = intent_agent._estimate_complexity_heuristic(task)
    logger.info(f"📊 Определена сложность задачи: {task_complexity.value}")
    
    router = get_model_router()
    
    try:
        if model_to_use:
            if check_model_available(model_to_use):
                model_selection = router.select_model_for_complexity(
                    complexity=task_complexity,
                    task_type="coding",
                    preferred_model=model_to_use
                )
                model_to_use = model_selection.model
                logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
            else:
                logger.warning(f"⚠️ Модель {model_to_use} недоступна, выбираю оптимальную")
                model_selection = router.select_model_for_complexity(
                    complexity=task_complexity,
                    task_type="coding"
                )
                model_to_use = model_selection.model
                logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
        else:
            model_selection = router.select_model_for_complexity(
                complexity=task_complexity,
                task_type="coding"
            )
            model_to_use = model_selection.model
            logger.info(f"🤖 {model_selection.reason}: {model_to_use}")
        
        # Проверяем, не слишком ли слабая модель для задачи
        if model_selection.metadata and model_selection.metadata.get("model_too_small", False):
            min_quality = model_selection.metadata.get("min_quality_required", 0.0)
            quality = model_selection.metadata.get("quality", 0.0)
            complexity_name = task_complexity.value if task_complexity else "неизвестной"
            
            warning_message = (
                f"⚠️ ВНИМАНИЕ: Для {complexity_name} задачи рекомендуется модель с качеством >= {min_quality:.2f}, "
                f"но выбранная модель {model_to_use} имеет качество только {quality:.2f}. "
                f"Результат может быть неудовлетворительным. Рекомендуется использовать более мощную модель."
            )
            
            logger.warning(warning_message)
            
            # Отправляем предупреждение пользователю через SSE
            yield await SSEManager.send_event(
                "warning",
                {
                    "message": warning_message,
                    "stage": "model_selection",
                    "model": model_to_use,
                    "quality": quality,
                    "min_quality_required": min_quality,
                    "complexity": complexity_name
                }
            )
            
    except RuntimeError as e:
        logger.error(f"❌ Ошибка инициализации: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="initialization",
            error_message=str(e)
        )
        return
    
    # ИСПРАВЛЕНИЕ: Автоматически определяем project_path если не указан
    # Проверяем текущую рабочую директорию на наличие признаков проекта
    if not project_path or project_path.strip() == '':
        cwd = Path.cwd()
        # Проверяем наличие признаков проекта (requirements.txt, package.json, pyproject.toml, etc.)
        project_indicators = ['requirements.txt', 'package.json', 'pyproject.toml', 'setup.py', '.git']
        if any((cwd / indicator).exists() for indicator in project_indicators):
            project_path = str(cwd)
            logger.info(f"📁 Автоматически определен project_path: {project_path}")
        else:
            logger.debug(f"ℹ️ project_path не указан и не найден в текущей директории: {cwd}")
    else:
        logger.info(f"📁 Используется указанный project_path: {project_path}")
    
    # Нормализуем project_path (убираем пробелы, проверяем существование)
    if project_path:
        project_path = project_path.strip()
        project_path_obj = Path(project_path)
        if not project_path_obj.exists() or not project_path_obj.is_dir():
            logger.warning(f"⚠️ Указанный project_path не существует или не является директорией: {project_path}")
            project_path = None
        else:
            logger.info(f"✅ project_path валиден: {project_path}")
    
    # Создаём начальный state
    initial_state: AgentState = {
        "task": task,
        "max_iterations": max_iterations,
        "disable_web_search": disable_web_search,
        "model": model_to_use,
        "temperature": temperature,
        "interaction_mode": "code",
        "conversation_id": None,
        "conversation_history": None,
        "chat_response": None,
        "project_path": project_path,
        "file_extensions": file_extensions,
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
        "critic_report": None,
        "iteration": 0,
        "task_id": task_id,
        "enable_sse": True,
        "event_references": [],
        "file_path": None,
        "file_context": None
    }
    
    # Создаём граф
    graph = create_workflow_graph()
    
    # Создаём WorkflowStreamer для обработки нодов
    streamer = WorkflowStreamer(
        task=task,
        task_id=task_id,
        sse_queue=sse_queue,
        initial_state=initial_state
    )
    
    try:
        # Запускаем граф с стримингом
        graph_iteration = 0
        async for event in graph.astream(initial_state):
            graph_iteration += 1
            
            # Проверяем очередь SSE событий из фоновой задачи
            for _ in range(10):
                if sse_queue.empty():
                    break
                try:
                    sse_event = sse_queue.get_nowait()
                    yield sse_event
                    # ОПТИМИЗАЦИЯ: Убрана минимальная задержка для более быстрого стриминга
                    # await asyncio.sleep(0.001)
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка отправки realtime SSE события: {e}")
            
            # Обрабатываем события графа
            for node_name, node_state in event.items():
                event_references = node_state.get("event_references") or []
                
                # ИСПРАВЛЕНИЕ: Для стриминговых нодов отправляем stage_start сразу при получении события графа
                # даже если plan еще не заполнен (он заполнится позже через event_references)
                if node_name == "planner" and event_references and not node_state.get("plan"):
                    # Отправляем stage_start для planner если есть event_references (стриминг начался)
                    yield await SSEManager.stream_stage_start(
                        stage="planning",
                        message="Создаю план выполнения..."
                    )
                
                if event_references:
                    session_id = initial_state.get("task_id") or initial_state.get("session_id") or "default"
                    event_store = await get_event_store(session_id)
                    
                    existing_refs = initial_state.get("event_references") or []
                    new_refs = [ref for ref in event_references if ref not in existing_refs]
                    
                    if new_refs:
                        stored_events = await event_store.get_events(new_refs)
                        logger.debug(f"📤 Отправляю {len(stored_events)} SSE событий из узла {node_name}")
                        
                        for stored_event in stored_events:
                            if stored_event.event_type == "thinking":
                                if isinstance(stored_event.data, str):
                                    # ReasoningStreamManager всегда возвращает готовую SSE строку
                                    sse_event = stored_event.data
                                else:
                                    # Fallback: создаём thinking_started событие
                                    sse_event = await SSEManager.send_event("thinking_started", {"content": str(stored_event.data), "stage": "unknown"})
                            elif stored_event.event_type.startswith("thinking_"):
                                if isinstance(stored_event.data, str):
                                    # Готовая SSE строка с правильным event_type
                                    sse_event = stored_event.data
                                else:
                                    # Fallback: используем event_type из stored_event
                                    sse_event = await SSEManager.send_event(stored_event.event_type, {"content": str(stored_event.data), "stage": "unknown"})
                            elif stored_event.event_type == "progress":
                                # ИСПРАВЛЕНИЕ: Пробрасываем progress события для non-reasoning моделей
                                if isinstance(stored_event.data, str):
                                    sse_event = stored_event.data
                                else:
                                    sse_event = await SSEManager.send_event("stage_progress", stored_event.data if isinstance(stored_event.data, dict) else {"message": str(stored_event.data)})
                            elif stored_event.event_type in ("plan_chunk", "test_chunk", "code_chunk"):
                                sse_event = await SSEManager.send_event(stored_event.event_type, {"chunk": stored_event.data})
                            else:
                                sse_event = await SSEManager.send_event(stored_event.event_type, {"data": stored_event.data})
                            yield sse_event
                        
                        if "event_references" not in initial_state:
                            initial_state["event_references"] = []
                        initial_state["event_references"].extend(new_refs)
                
                # Используем WorkflowStreamer для обработки нодов
                should_stop = False
                async for sse_event in streamer.handle_node(
                    node_name=node_name,
                    node_state=node_state,
                    greeting_message=GREETING_MESSAGE,
                    help_message=HELP_MESSAGE
                ):
                    if sse_event == "__STOP_WORKFLOW__":
                        should_stop = True
                        break
                    yield sse_event
                
                if should_stop:
                    break
                
                # Специальная обработка для critic нода
                if node_name == "critic":
                    stop_realtime_streaming.set()
                    if realtime_task and not realtime_task.done():
                        realtime_task.cancel()
                        try:
                            await realtime_task
                        except asyncio.CancelledError:
                            pass
                    
                    EventStore.remove_event_queue(task_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения workflow: {e}", error=e)
        yield await SSEManager.stream_error(
            stage="workflow",
            error_message=f"Ошибка выполнения workflow: {str(e)}",
            error_details={"exception_type": type(e).__name__}
        )
    finally:
        # Останавливаем фоновую задачу и очищаем ресурсы
        stop_realtime_streaming.set()
        if realtime_task and not realtime_task.done():
            realtime_task.cancel()
            try:
                await asyncio.wait_for(realtime_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при отмене фоновой задачи: {e}")
        
        # Очищаем сессию из EventStore
        try:
            await EventStore.cleanup_session(task_id)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке сессии EventStore: {e}")
        
        # Удаляем очередь событий
        EventStore.remove_event_queue(task_id)
