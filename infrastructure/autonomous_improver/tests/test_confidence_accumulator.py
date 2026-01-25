"""Тесты для ConfidenceAccumulator."""
import pytest
from datetime import datetime, timedelta
from infrastructure.autonomous_improver.confidence_accumulator import (
    ConfidenceAccumulator,
    ConfidenceHistory
)


class TestConfidenceAccumulator:
    """Тесты для ConfidenceAccumulator."""
    
    def test_initialization(self):
        """Тест инициализации."""
        accumulator = ConfidenceAccumulator(
            min_observations=3,
            stability_window_hours=24
        )
        assert accumulator.min_observations == 3
        assert accumulator.stability_window_hours == 24
        assert len(accumulator._history) == 0
    
    def test_first_observation(self):
        """Тест первого наблюдения."""
        accumulator = ConfidenceAccumulator()
        
        confidence = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8
        )
        
        # Первое наблюдение - confidence не накапливается
        assert confidence == 0.8
        assert len(accumulator._history) == 1
    
    def test_confidence_accumulation(self):
        """Тест накопления уверенности."""
        accumulator = ConfidenceAccumulator(min_observations=2)
        
        # Первое наблюдение
        conf1 = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8
        )
        assert conf1 == 0.8
        
        # Второе наблюдение - должен быть бонус
        conf2 = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8
        )
        assert conf2 > 0.8  # Должна быть выше базовой
        assert conf2 <= 1.0  # Но не больше 1.0
    
    def test_ast_confirmation_bonus(self):
        """Тест бонуса за AST подтверждение."""
        accumulator = ConfidenceAccumulator(min_observations=1)
        
        # С AST подтверждением
        conf_with_ast = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            ast_confirmed=True
        )
        
        # Без AST подтверждения
        accumulator2 = ConfidenceAccumulator(min_observations=1)
        conf_without_ast = accumulator2.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            ast_confirmed=False
        )
        
        assert conf_with_ast > conf_without_ast
    
    def test_web_confirmation_bonus(self):
        """Тест бонуса за веб-подтверждение."""
        accumulator = ConfidenceAccumulator(min_observations=1)
        
        conf_with_web = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            web_confirmed=True
        )
        
        accumulator2 = ConfidenceAccumulator(min_observations=1)
        conf_without_web = accumulator2.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            web_confirmed=False
        )
        
        assert conf_with_web > conf_without_web
    
    def test_code_stability_bonus(self):
        """Тест бонуса за стабильность кода."""
        accumulator = ConfidenceAccumulator(min_observations=2)
        
        file_content = "def test(): pass"
        
        # Первое наблюдение
        accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            file_content=file_content
        )
        
        # Второе наблюдение с тем же содержимым (стабильный код)
        conf_stable = accumulator.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            file_content=file_content  # Тот же код
        )
        
        # Третье наблюдение с изменённым кодом
        accumulator2 = ConfidenceAccumulator(min_observations=2)
        accumulator2.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            file_content="def test(): pass"
        )
        conf_changed = accumulator2.update(
            file_path="test.py",
            description="Test issue",
            suggestion="Test fix",
            base_confidence=0.8,
            file_content="def test(): return True"  # Изменённый код
        )
        
        # Стабильный код должен давать больший бонус
        assert conf_stable >= conf_changed
    
    def test_history_cleanup(self):
        """Тест очистки старой истории."""
        accumulator = ConfidenceAccumulator()
        
        # Добавляем несколько наблюдений
        for i in range(10):
            accumulator.update(
                file_path=f"test{i}.py",
                description=f"Test issue {i}",
                suggestion="Test fix",
                base_confidence=0.8
            )
        
        assert len(accumulator._history) == 10
        
        # Очищаем старую историю (старше 1 дня)
        accumulator.clear_old_history(max_age_days=1)
        
        # История должна остаться (все недавние)
        assert len(accumulator._history) == 10
        
        # Симулируем старую историю
        old_date = datetime.now() - timedelta(days=2)
        for history in accumulator._history.values():
            history.first_seen = old_date
            history.last_seen = old_date
        
        accumulator.clear_old_history(max_age_days=1)
        
        # Вся история должна быть очищена
        assert len(accumulator._history) == 0
    
    def test_get_stats(self):
        """Тест получения статистики."""
        accumulator = ConfidenceAccumulator()
        
        # Добавляем наблюдения
        for i in range(5):
            accumulator.update(
                file_path=f"test{i}.py",
                description=f"Test issue {i}",
                suggestion="Test fix",
                base_confidence=0.8
            )
        
        stats = accumulator.get_stats()
        
        assert stats['total_suggestions'] == 5
        assert stats['total_observations'] >= 5
        assert 'average_confidence' in stats
        assert 'max_confidence' in stats
        assert 'history_size' in stats
        assert 'max_history_size' in stats
    
    def test_max_history_size_limit(self):
        """Тест ограничения размера истории."""
        accumulator = ConfidenceAccumulator(max_history_size=5)
        
        # Добавляем больше записей, чем лимит
        for i in range(10):
            accumulator.update(
                file_path=f"test{i}.py",
                description=f"Test issue {i}",
                suggestion="Test fix",
                base_confidence=0.8
            )
        
        # История не должна превышать лимит
        assert len(accumulator._history) <= 5
