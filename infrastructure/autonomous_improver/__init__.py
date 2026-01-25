"""Autonomous Improver - модуль автономного улучшения проекта.

Работает в фоне в свободное время, анализирует кодовую базу и предлагает
аргументированные улучшения при высокой уверенности.

Использование:
    from infrastructure.autonomous_improver import get_autonomous_improver
    
    improver = get_autonomous_improver()
    improver.start()
    suggestions = improver.get_suggestions()
"""

from .core import (
    AutonomousImprover,
    ImprovementSuggestion,
    ImprovementType,
    get_autonomous_improver,
    reset_autonomous_improver
)

__all__ = [
    'AutonomousImprover',
    'ImprovementSuggestion',
    'ImprovementType',
    'get_autonomous_improver',
    'reset_autonomous_improver'
]
