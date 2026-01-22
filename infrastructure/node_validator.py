"""Валидация входных данных для workflow узлов.

Проверяет наличие обязательных ключей в AgentState перед выполнением узлов,
предотвращая ошибки KeyError и некорректное поведение.
"""
from typing import Set, Optional
from infrastructure.workflow_state import AgentState
from utils.logger import get_logger

logger = get_logger()


class NodeInputValidator:
    """Валидатор входных данных для узлов workflow.
    
    Проверяет наличие обязательных ключей в AgentState перед выполнением узлов.
    """
    
    # Обязательные ключи для каждого узла
    REQUIRED_KEYS = {
        "intent": {"task"},
        "planning": {"intent_result"},
        "research": {"intent_result"},
        "testing": {"intent_result", "plan", "context"},
        "coding": {"intent_result", "plan", "context"},
        "validation": {"code"},
        "debug": {"validation_results", "code"},  # Соответствует stage="debug" в workflow_nodes
        "fixing": {"debug_result", "code"},
        "reflection": {"intent_result", "code"},
        "critic": {"code"},
    }
    
    @classmethod
    def validate(cls, stage: str, state: AgentState) -> tuple[bool, Optional[str]]:
        """Валидирует входные данные для узла.
        
        Args:
            stage: Название этапа (intent, planning, coding, etc.)
            state: AgentState для проверки
            
        Returns:
            tuple[bool, Optional[str]]: (валидно, сообщение об ошибке)
        """
        required = cls.REQUIRED_KEYS.get(stage, set())
        
        if not required:
            # Нет требований для этого узла
            return True, None
        
        missing = required - set(state.keys())
        
        if missing:
            error_msg = (
                f"Отсутствуют обязательные ключи для узла '{stage}': {missing}. "
                f"Доступные ключи: {set(state.keys())}"
            )
            return False, error_msg
        
        return True, None
    
    @classmethod
    def validate_intent_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для intent узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("intent", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_planning_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для planning узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("planning", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_research_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для research узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("research", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_testing_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для testing узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("testing", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_coding_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для coding узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("coding", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_validation_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для validation узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("validation", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_debugging_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для debug узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("debug", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_fixing_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для fixing узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("fixing", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_reflection_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для reflection узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("reflection", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
    
    @classmethod
    def validate_critic_input(cls, state: AgentState) -> bool:
        """Валидирует входные данные для critic узла.
        
        Args:
            state: AgentState для проверки
            
        Returns:
            True если валидно, False иначе
        """
        valid, error = cls.validate("critic", state)
        if not valid and error:
            logger.error(f"❌ {error}")
        return valid
