"""Пример интеграции системы логирования с multi-agent системой.

Этот файл показывает, как:
1. Интегрировать LogManager с агентами
2. Логировать этапы выполнения задачи
3. Обрабатывать ошибки как события
4. Использовать MemoryLoggerSink для UI стриминга
"""
from typing import Optional
from infrastructure.logging.manager import LogManager
from infrastructure.logging.config import LoggingConfig
from infrastructure.logging.models import LogSource, LogStage, LogLevel


# Глобальный экземпляр LogManager (singleton через DI)
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """Получает глобальный экземпляр LogManager.
    
    Инициализирует его при первом вызове с конфигурацией для UI.
    
    Returns:
        Экземпляр LogManager
    """
    global _log_manager
    if _log_manager is None:
        config = LoggingConfig.for_ui()  # С памятью для стриминга
        _log_manager = LogManager(config)
    return _log_manager


def set_log_manager(log_manager: LogManager) -> None:
    """Устанавливает глобальный экземпляр LogManager (для тестов).
    
    Args:
        log_manager: Экземпляр LogManager
    """
    global _log_manager
    _log_manager = log_manager


# Пример: Интеграция с агентом IntentAgent
class IntentAgentExample:
    """Пример агента с интегрированным логированием."""
    
    def __init__(self, log_manager: Optional[LogManager] = None) -> None:
        """Инициализация агента.
        
        Args:
            log_manager: Менеджер логирования (по умолчанию глобальный)
        """
        self.log_manager = log_manager or get_log_manager()
    
    def determine_intent(self, user_query: str, task_id: str) -> dict:
        """Определяет намерение пользователя с логированием.
        
        Args:
            user_query: Запрос пользователя
            task_id: ID задачи
            
        Returns:
            Результат определения намерения
        """
        # Логируем начало этапа
        self.log_manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.INTENT,
            message=f"Начат этап определения намерения",
            payload={"query": user_query[:100]},  # Первые 100 символов
            source=LogSource.AGENT
        )
        
        try:
            # Здесь была бы логика определения намерения
            # ...
            
            intent_type = "create"  # Пример результата
            confidence = 0.85
            
            # Логируем успешное завершение этапа
            self.log_manager.log_stage_end(
                task_id=task_id,
                stage=LogStage.INTENT,
                message=f"Намерение определено: {intent_type} (уверенность: {confidence:.2f})",
                payload={"type": intent_type, "confidence": confidence},
                source=LogSource.AGENT
            )
            
            return {"type": intent_type, "confidence": confidence}
            
        except Exception as e:
            # Логируем ошибку как событие, а не traceback-строку
            self.log_manager.log_error(
                message=f"Ошибка при определении намерения: {str(e)}",
                source=LogSource.AGENT,
                stage=LogStage.INTENT,
                task_id=task_id,
                error=e,
                payload={"query": user_query[:100]}
            )
            raise


# Пример: Интеграция с workflow (множественные этапы и итерации)
class WorkflowExample:
    """Пример workflow с логированием этапов и итераций."""
    
    def __init__(self, log_manager: Optional[LogManager] = None) -> None:
        """Инициализация workflow.
        
        Args:
            log_manager: Менеджер логирования
        """
        self.log_manager = log_manager or get_log_manager()
    
    def run_task(self, task: str, task_id: str, max_iterations: int = 3) -> dict:
        """Запускает выполнение задачи с логированием.
        
        Args:
            task: Текст задачи
            task_id: ID задачи
            max_iterations: Максимальное количество итераций
            
        Returns:
            Результаты выполнения
        """
        # Логируем начало задачи
        self.log_manager.log_info(
            message=f"Начато выполнение задачи: {task[:100]}",
            source=LogSource.SYSTEM,
            task_id=task_id,
            payload={"task": task, "max_iterations": max_iterations}
        )
        
        for iteration in range(1, max_iterations + 1):
            # Логируем начало итерации
            self.log_manager.log_info(
                message=f"Начата итерация {iteration}/{max_iterations}",
                source=LogSource.SYSTEM,
                task_id=task_id,
                iteration=iteration
            )
            
            try:
                # Этап 1: Planning
                self.log_manager.log_stage_start(
                    task_id=task_id,
                    stage=LogStage.PLANNING,
                    message="Начат этап планирования",
                    iteration=iteration
                )
                # ... логика планирования ...
                self.log_manager.log_stage_end(
                    task_id=task_id,
                    stage=LogStage.PLANNING,
                    message="Этап планирования завершён",
                    payload={"plan_length": 150},
                    iteration=iteration
                )
                
                # Этап 2: Research
                self.log_manager.log_stage_start(
                    task_id=task_id,
                    stage=LogStage.RESEARCH,
                    message="Начат этап исследования",
                    iteration=iteration
                )
                # ... логика исследования ...
                self.log_manager.log_stage_end(
                    task_id=task_id,
                    stage=LogStage.RESEARCH,
                    message="Этап исследования завершён",
                    payload={"context_chunks": 5},
                    iteration=iteration
                )
                
                # Этап 3: Coding
                self.log_manager.log_stage_start(
                    task_id=task_id,
                    stage=LogStage.CODING,
                    message="Начат этап генерации кода",
                    iteration=iteration
                )
                # ... логика генерации кода ...
                self.log_manager.log_stage_end(
                    task_id=task_id,
                    stage=LogStage.CODING,
                    message="Этап генерации кода завершён",
                    payload={"code_lines": 42},
                    iteration=iteration
                )
                
                # Логируем успешное завершение итерации
                self.log_manager.log_info(
                    message=f"Итерация {iteration} завершена успешно",
                    source=LogSource.SYSTEM,
                    task_id=task_id,
                    iteration=iteration
                )
                
                # Если всё хорошо, выходим из цикла
                break
                
            except Exception as e:
                # Логируем ошибку в итерации
                self.log_manager.log_error(
                    message=f"Ошибка в итерации {iteration}: {str(e)}",
                    source=LogSource.SYSTEM,
                    task_id=task_id,
                    iteration=iteration,
                    error=e
                )
                
                # Если это последняя итерация, пробрасываем ошибку
                if iteration == max_iterations:
                    raise
        
        # Логируем завершение задачи
        self.log_manager.log_info(
            message=f"Задача {task_id} завершена",
            source=LogSource.SYSTEM,
            task_id=task_id,
            payload={"completed_iterations": iteration}
        )
        
        return {"task_id": task_id, "status": "completed"}


# Пример: Тестируемость с MemoryLoggerSink
def test_agent_with_logging():
    """Пример тестирования агента с логированием."""
    from infrastructure.logging.config import LoggingConfig
    from infrastructure.logging.memory_sink import MemoryLoggerSink
    
    # Создаём конфигурацию только с памятью (без файлов)
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        enable_file=False,
        enable_console=False,
        enable_memory=True,
        memory_max_events=100
    )
    
    # Создаём LogManager только с MemoryLoggerSink
    log_manager = LogManager(config)
    
    # Используем агента с этим логгером
    agent = IntentAgentExample(log_manager=log_manager)
    
    # Выполняем операцию
    task_id = "test-123"
    result = agent.determine_intent("создай функцию", task_id=task_id)
    
    # Проверяем, что нужные события были залогированы
    memory_sink = log_manager.get_memory_sink()
    assert memory_sink is not None
    
    # Получаем события для этой задачи
    events = memory_sink.get_events(task_id=task_id)
    
    # Проверяем наличие нужных событий
    assert len(events) >= 2  # Начало и конец этапа
    assert any(e.stage == LogStage.INTENT and e.level == LogLevel.INFO for e in events)
    
    # Закрываем логгер
    log_manager.close()
    
    return events