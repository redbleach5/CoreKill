"""Класс для стриминга событий workflow графа.

Вынесен из run_workflow_stream для улучшения читаемости и поддерживаемости.
"""
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from utils.logger import get_logger
from backend.sse_manager import SSEManager
from utils.artifact_saver import ArtifactSaver
from utils.token_counter import estimate_workflow_tokens, check_token_limit
from utils.config import get_config
from infrastructure.workflow_state import AgentState
from agents.intent import IntentResult
from agents.debugger import DebugResult
from agents.reflection import ReflectionResult
from agents.critic import CriticReport

logger = get_logger()


class WorkflowStreamer:
    """Обрабатывает события workflow графа и отправляет SSE события."""
    
    def __init__(
        self,
        task: str,
        task_id: str,
        sse_queue: asyncio.Queue,
        initial_state: AgentState
    ):
        """Инициализирует WorkflowStreamer.
        
        Args:
            task: Текст задачи
            task_id: ID задачи
            sse_queue: Очередь для SSE событий от фоновой задачи
            initial_state: Начальное состояние workflow
        """
        self.task = task
        self.task_id = task_id
        self.sse_queue = sse_queue
        self.initial_state = initial_state
        self.config = get_config()
        
        # Маппинг node_name -> stage для SSE событий
        self.node_to_stage = {
            "intent": "intent",
            "planner": "planning",
            "researcher": "research",
            "test_generator": "testing",
            "coder": "coding",
            "validator": "validation",
            "debugger": "debug",
            "fixer": "fixing",
            "reflection": "reflection",
            "critic": "critic"
        }
        
        # Сообщения для каждого этапа
        self.stage_messages = {
            "intent": ("Определяю намерение...", "Намерение определено"),
            "planning": ("Создаю план выполнения...", "План создан"),
            "research": ("Ищу контекст в базе знаний (RAG)...", "Контекст собран"),
            "testing": ("Генерирую тесты...", "Тесты сгенерированы"),
            "coding": ("Генерирую код...", "Код сгенерирован"),
            "validation": ("Валидирую код (pytest, mypy, bandit)...", "Валидация завершена"),
            "debug": ("Анализирую ошибки...", "Анализ завершён"),
            "fixing": ("Исправляю код по инструкциям...", "Код исправлен"),
            "reflection": ("Анализирую результаты...", "Рефлексия завершена"),
            "critic": ("Критический анализ кода...", "Критический анализ завершён")
        }
    
    async def handle_node(
        self,
        node_name: str,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает событие нода и отправляет соответствующие SSE события.
        
        Args:
            node_name: Имя нода из графа
            node_state: Состояние нода
            greeting_message: Сообщение приветствия (для intent нода)
            help_message: Сообщение помощи (для intent нода)
            
        Yields:
            SSE события в формате text/event-stream
        """
        handler = self._get_node_handler(node_name)
        if handler:
            async for event in handler(node_state, greeting_message, help_message):
                yield event
    
    def _get_node_handler(self, node_name: str):
        """Возвращает обработчик для нода."""
        handlers = {
            "intent": self._handle_intent,
            "planner": self._handle_planner,
            "researcher": self._handle_researcher,
            "test_generator": self._handle_test_generator,
            "coder": self._handle_coder,
            "validator": self._handle_validator,
            "debugger": self._handle_debugger,
            "fixer": self._handle_fixer,
            "reflection": self._handle_reflection,
            "critic": self._handle_critic
        }
        return handlers.get(node_name)
    
    async def _handle_intent(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает intent нод."""
        intent_result: Optional[IntentResult] = node_state.get("intent_result")
        if not intent_result:
            return
        
        logger.debug(f"📤 Отправляю stage_start для intent")
        event1 = await SSEManager.stream_stage_start(
            stage="intent",
            message="Определяю намерение..."
        )
        yield event1
        logger.info(f"✅ Отправлено stage_start, длина: {len(event1)}")
        
        logger.info(f"📤 Отправляю stage_end для intent")
        event2 = await SSEManager.stream_stage_end(
            stage="intent",
            message=f"Намерение определено: {intent_result.type}",
            result={"type": intent_result.type, "confidence": intent_result.confidence}
        )
        yield event2
        logger.info(f"✅ Отправлено stage_end, длина: {len(event2)}")
        
        # Если greeting или help, отправляем специальное сообщение и завершаем
        if intent_result.type in ("greeting", "help"):
            message = greeting_message if intent_result.type == "greeting" else help_message
            if not message:
                logger.warning(f"⚠️ Сообщение для {intent_result.type} не предоставлено")
                return
            
            stage_name = intent_result.type
            
            logger.debug(f"📤 Отправляю {stage_name} stage_end")
            event3 = await SSEManager.stream_stage_end(
                stage=stage_name,
                message=message,
                result={"type": stage_name, "message": message}
            )
            yield event3
            logger.info(f"✅ Отправлено {stage_name}, длина: {len(event3)}")
            
            logger.debug(f"📤 Отправляю final_result (complete)")
            event4 = await SSEManager.stream_final_result(
                task_id=self.task_id,
                results={
                    "task": self.task,
                    "intent": {
                        "type": intent_result.type,
                        "confidence": intent_result.confidence,
                        "description": intent_result.description
                    },
                    "greeting_message": message
                },
                metrics={
                    "planning": 0.0,
                    "research": 0.0,
                    "testing": 0.0,
                    "coding": 0.0,
                    "overall": 0.0
                }
            )
            yield event4
            logger.info(f"✅ Отправлено complete, длина: {len(event4)}")
            # Даем время на отправку последнего события перед завершением
            from utils.ui_delays import ui_sleep
            await ui_sleep("critical")
            # Возвращаем специальный маркер для выхода из цикла
            yield "__STOP_WORKFLOW__"
    
    async def _handle_simple_node(
        self,
        node_state: Dict[str, Any],
        stage: str,
        state_key: str,
        start_message: str,
        end_message: str,
        result_builder: Optional[Callable[[str], Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Универсальный обработчик для простых нодов.
        
        Args:
            node_state: Состояние нода
            stage: Название этапа (planning, research, testing, etc.)
            state_key: Ключ в state для проверки наличия данных
            start_message: Сообщение для stage_start
            end_message: Сообщение для stage_end
            result_builder: Функция для построения result (опционально)
            
        Yields:
            SSE события
        """
        data = node_state.get(state_key, "")
        if data:
            yield await SSEManager.stream_stage_start(
                stage=stage,
                message=start_message
            )
            
            # Строим result
            if result_builder:
                result = result_builder(data)
            else:
                # По умолчанию используем длину данных
                result = {f"{state_key}_length": len(data)}
            
            yield await SSEManager.stream_stage_end(
                stage=stage,
                message=end_message,
                result=result
            )
    
    async def _handle_planner(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает planner нод.
        
        ИСПРАВЛЕНИЕ: Для стриминговых нодов события приходят через event_references,
        а не сразу в state. Поэтому проверяем наличие event_references или plan.
        """
        # Проверяем наличие event_references (для стриминга) или plan (для обычного режима)
        event_references = node_state.get("event_references", [])
        plan = node_state.get("plan", "")
        
        # ИСПРАВЛЕНИЕ: Для стриминговых нодов stage_start уже отправлен в workflow_handler
        # Здесь отправляем только stage_end когда план завершен
        if plan:
            yield await SSEManager.stream_stage_end(
                stage="planning",
                message="План создан",
                result={"plan_length": len(plan)}
            )
    
    async def _handle_researcher(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает researcher нод."""
        context = node_state.get("context", "")
        if context:
            yield await SSEManager.stream_stage_start(
                stage="research",
                message="Ищу контекст в базе знаний (RAG)..."
            )
            yield await SSEManager.stream_stage_end(
                stage="research",
                message="Контекст собран",
                result={"context_length": len(context)}
            )
    
    async def _handle_test_generator(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает test_generator нод."""
        event_references = node_state.get("event_references", [])
        tests = node_state.get("tests", "")
        
        if event_references or tests:
            yield await SSEManager.stream_stage_start(
                stage="testing",
                message="Генерирую тесты..."
            )
            
            if tests:
                yield await SSEManager.stream_stage_end(
                    stage="testing",
                    message="Тесты сгенерированы",
                    result={"tests_length": len(tests)}
                )
    
    async def _handle_coder(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает coder нод."""
        code = node_state.get("code", "")
        if code:
            yield await SSEManager.stream_stage_start(
                stage="coding",
                message="Генерирую код..."
            )
            # Отправляем код как чанк для отображения в IDE
            yield await SSEManager.stream_code_chunk(
                chunk=code,
                is_final=True,
                metadata={"stage": "coding"}
            )
            yield await SSEManager.stream_stage_end(
                stage="coding",
                message="Код сгенерирован",
                result={"code_length": len(code), "code": code}
            )
    
    async def _handle_validator(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает validator нод."""
        validation_results = node_state.get("validation_results", {})
        yield await SSEManager.stream_stage_start(
            stage="validation",
            message="Валидирую код (pytest, mypy, bandit)..."
        )
        yield await SSEManager.stream_stage_end(
            stage="validation",
            message="Валидация завершена",
            result=validation_results
        )
    
    async def _handle_debugger(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает debugger нод."""
        debug_result: Optional[DebugResult] = node_state.get("debug_result")
        iteration = node_state.get("iteration", 0)
        if debug_result:
            yield await SSEManager.stream_stage_start(
                stage="debug",
                message=f"Анализирую ошибки (итерация {iteration})..."
            )
            yield await SSEManager.stream_stage_end(
                stage="debug",
                message=f"Анализ завершён: {debug_result.error_summary}",
                result={
                    "error_type": debug_result.error_type,
                    "confidence": debug_result.confidence,
                    "error_summary": debug_result.error_summary
                }
            )
    
    async def _handle_fixer(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает fixer нод."""
        code = node_state.get("code", "")
        iteration = node_state.get("iteration", 0)
        if code:
            yield await SSEManager.stream_stage_start(
                stage="fixing",
                message=f"Исправляю код по инструкциям (итерация {iteration})..."
            )
            # Отправляем исправленный код для обновления IDE
            yield await SSEManager.stream_code_chunk(
                chunk=code,
                is_final=True,
                metadata={"stage": "fixing", "iteration": iteration}
            )
            yield await SSEManager.stream_stage_end(
                stage="fixing",
                message="Код исправлен",
                result={"code_length": len(code), "code": code}
            )
    
    async def _handle_reflection(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает reflection нод."""
        reflection_result: Optional[ReflectionResult] = node_state.get("reflection_result")
        if not reflection_result:
            return
        
        yield await SSEManager.stream_stage_start(
            stage="reflection",
            message="Анализирую результаты..."
        )
        
        # Сохраняем артефакты
        artifact_saver = ArtifactSaver()
        artifacts_dir = None
        try:
            artifacts_dir = artifact_saver.save_all_artifacts(
                task=self.task,
                code=node_state.get("code", ""),
                tests=node_state.get("tests", ""),
                reflection_data={
                    "planning_score": reflection_result.planning_score,
                    "research_score": reflection_result.research_score,
                    "testing_score": reflection_result.testing_score,
                    "coding_score": reflection_result.coding_score,
                    "overall_score": reflection_result.overall_score,
                    "analysis": reflection_result.analysis,
                    "improvements": reflection_result.improvements,
                    "should_retry": reflection_result.should_retry
                },
                metrics={
                    "planning": reflection_result.planning_score,
                    "research": reflection_result.research_score,
                    "testing": reflection_result.testing_score,
                    "coding": reflection_result.coding_score,
                    "overall": reflection_result.overall_score
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения артефактов: {e}", error=e)
        
        yield await SSEManager.stream_stage_end(
            stage="reflection",
            message="Рефлексия завершена",
            result={
                "planning_score": reflection_result.planning_score,
                "research_score": reflection_result.research_score,
                "testing_score": reflection_result.testing_score,
                "coding_score": reflection_result.coding_score,
                "overall_score": reflection_result.overall_score,
                "artifacts_dir": str(artifacts_dir) if artifacts_dir else None
            }
        )
    
    async def _handle_critic(
        self,
        node_state: Dict[str, Any],
        greeting_message: Optional[str] = None,
        help_message: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Обрабатывает critic нод и отправляет финальный результат."""
        critic_report: Optional[CriticReport] = node_state.get("critic_report")
        reflection_result: Optional[ReflectionResult] = node_state.get("reflection_result")
        
        # Critic stage
        yield await SSEManager.stream_stage_start(
            stage="critic",
            message="Критический анализ кода..."
        )
        
        if critic_report:
            yield await SSEManager.stream_stage_end(
                stage="critic",
                message=critic_report.summary,
                result={
                    "overall_score": critic_report.overall_score,
                    "issues_count": len(critic_report.issues),
                    "issues": [
                        {
                            "category": issue.category,
                            "severity": issue.severity,
                            "location": issue.location,
                            "description": issue.description,
                            "evidence": issue.evidence,
                            "suggestion": issue.suggestion
                        }
                        for issue in critic_report.issues
                    ],
                    "strengths": critic_report.strengths
                }
            )
        else:
            yield await SSEManager.stream_stage_end(
                stage="critic",
                message="Критический анализ пропущен",
                result={"overall_score": 0.0, "issues_count": 0, "issues": [], "strengths": []}
            )
        
        # Подсчитываем токены
        estimated_tokens = estimate_workflow_tokens(
            task=self.task,
            plan=node_state.get("plan", ""),
            context=node_state.get("context", ""),
            tests=node_state.get("tests", ""),
            code=node_state.get("code", ""),
            prompts_used=[]
        )
        
        token_status = check_token_limit(
            current_tokens=estimated_tokens,
            warning_threshold=self.config.max_tokens_warning,
            max_tokens=50000
        )
        
        if token_status["warning"]:
            yield await SSEManager.send_event(
                "warning",
                {
                    "message": token_status["message"],
                    "tokens": estimated_tokens
                }
            )
        
        # Отправляем оставшиеся события из очереди перед финальным результатом
        while not self.sse_queue.empty():
            try:
                sse_event = self.sse_queue.get_nowait()
                yield sse_event
            except asyncio.QueueEmpty:
                break
        
        # Финальный результат с critic данными
        critic_score = critic_report.overall_score if critic_report else 0.0
        reflection_score = reflection_result.overall_score if reflection_result else 0.0
        
        intent_result: Optional[IntentResult] = node_state.get("intent_result")
        
        yield await SSEManager.stream_final_result(
            task_id=self.task_id,
            results={
                "task": self.task,
                "intent": {
                    "type": intent_result.type if intent_result else "unknown",
                    "confidence": intent_result.confidence if intent_result else 0.0,
                    "description": intent_result.description if intent_result else ""
                },
                "plan": node_state.get("plan", ""),
                "context": node_state.get("context", ""),
                "tests": node_state.get("tests", ""),
                "code": node_state.get("code", ""),
                "validation": node_state.get("validation_results", {}),
                "reflection": {
                    "planning_score": reflection_result.planning_score if reflection_result else 0.0,
                    "research_score": reflection_result.research_score if reflection_result else 0.0,
                    "testing_score": reflection_result.testing_score if reflection_result else 0.0,
                    "coding_score": reflection_result.coding_score if reflection_result else 0.0,
                    "overall_score": reflection_score,
                    "analysis": reflection_result.analysis if reflection_result else "",
                    "improvements": reflection_result.improvements if reflection_result else "",
                    "should_retry": reflection_result.should_retry if reflection_result else False
                },
                "critic": {
                    "score": critic_score,
                    "summary": critic_report.summary if critic_report else "",
                    "issues": [
                        {
                            "category": i.category,
                            "severity": i.severity,
                            "description": i.description,
                            "suggestion": i.suggestion
                        }
                        for i in (critic_report.issues[:5] if critic_report else [])
                    ],
                    "strengths": critic_report.strengths if critic_report else []
                },
                "tokens_used": estimated_tokens,
                "token_warning": token_status["warning"]
            },
            metrics={
                "planning": reflection_result.planning_score if reflection_result else 0.0,
                "research": reflection_result.research_score if reflection_result else 0.0,
                "testing": reflection_result.testing_score if reflection_result else 0.0,
                "coding": reflection_result.coding_score if reflection_result else 0.0,
                "critic": critic_score,
                "overall": (reflection_score + critic_score) / 2
            }
        )
