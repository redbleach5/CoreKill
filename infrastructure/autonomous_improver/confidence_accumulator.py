"""Confidence Accumulator - накопление уверенности между циклами.

Решает проблему "LLM никогда не бывает 100% уверенным" через:
- Накопление уверенности между циклами
- Учёт повторяемости предложений
- Подтверждение через AST и стабильность кода
- Учёт внешних источников (веб-поиск)
"""
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
from utils.logger import get_logger

logger = get_logger()


@dataclass
class ConfidenceHistory:
    """История уверенности для предложения."""
    suggestion_hash: str
    file_hash: str
    first_seen: datetime
    last_seen: datetime
    observations: list[Tuple[datetime, float]] = field(default_factory=list)  # (время, confidence)
    ast_confirmations: int = 0  # Количество подтверждений через AST
    web_confirmations: int = 0  # Количество подтверждений через веб-поиск
    code_changed: bool = False  # Изменился ли код с момента первого наблюдения


class ConfidenceAccumulator:
    """Накопление уверенности для предложений между циклами анализа.
    
    Факторы, влияющие на effective_confidence:
    1. Базовая уверенность от LLM
    2. Повторяемость (один и тот же совет найден N раз)
    3. Стабильность кода (код не менялся между наблюдениями)
    4. AST подтверждение (структурные проблемы подтверждены)
    5. Веб-подтверждение (найдено в best practices)
    """
    
    def __init__(
        self,
        min_observations: int = 3,
        stability_window_hours: int = 24,
        max_history_size: int = 10000,
        cleanup_interval_updates: int = 100
    ):
        """Инициализирует аккумулятор.
        
        Args:
            min_observations: Минимальное количество наблюдений для накопления
            stability_window_hours: Окно стабильности в часах (код не менялся)
            max_history_size: Максимальный размер истории (для предотвращения memory leaks)
            cleanup_interval_updates: Количество update() вызовов между периодическими очистками
        """
        self.min_observations = min_observations
        self.stability_window_hours = stability_window_hours
        self.max_history_size = max_history_size
        self.cleanup_interval_updates = cleanup_interval_updates
        
        # suggestion_hash -> ConfidenceHistory
        self._history: Dict[str, ConfidenceHistory] = {}
        
        # file_hash -> last_modified_time
        self._file_hashes: Dict[str, datetime] = {}
        
        # Счётчик вызовов update() для периодической очистки
        self._update_count = 0
    
    def _get_suggestion_hash(self, file_path: str, description: str, suggestion: str) -> str:
        """Вычисляет хеш предложения для идентификации.
        
        Использует SHA256 для более надёжного хеширования (меньше коллизий).
        """
        content = f"{file_path}:{description[:100]}:{suggestion[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_file_hash(self, file_path: str, file_content: Optional[str] = None) -> str:
        """Вычисляет хеш файла для отслеживания изменений.
        
        Использует SHA256 для более надёжного хеширования (меньше коллизий).
        """
        if file_content:
            return hashlib.sha256(file_content.encode()).hexdigest()
        # Если контент не передан, используем путь и время модификации
        try:
            from pathlib import Path
            path = Path(file_path)
            if path.exists():
                mtime = path.stat().st_mtime
                return hashlib.sha256(f"{file_path}:{mtime}".encode()).hexdigest()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения mtime для {file_path}, используем fallback: {e}")
        return hashlib.sha256(file_path.encode()).hexdigest()
    
    def update(
        self,
        file_path: str,
        description: str,
        suggestion: str,
        base_confidence: float,
        file_content: Optional[str] = None,
        ast_confirmed: bool = False,
        web_confirmed: bool = False
    ) -> float:
        """Обновляет историю и возвращает effective_confidence.
        
        Args:
            file_path: Путь к файлу
            description: Описание проблемы
            suggestion: Предложение по улучшению
            base_confidence: Базовая уверенность от LLM (0.0-1.0)
            file_content: Содержимое файла (для отслеживания изменений)
            ast_confirmed: Подтверждено ли через AST
            web_confirmed: Подтверждено ли через веб-поиск
            
        Returns:
            Effective confidence (0.0-1.0)
        """
        suggestion_hash = self._get_suggestion_hash(file_path, description, suggestion)
        file_hash = self._get_file_hash(file_path, file_content)
        current_time = datetime.now()
        
        # Периодическая очистка (каждые N вызовов update)
        self._update_count += 1
        if self._update_count >= self.cleanup_interval_updates:
            self._update_count = 0
            # Очищаем старую историю (старше 7 дней)
            self.clear_old_history(max_age_days=7)
        
        # Проверяем ограничение размера истории ПЕРЕД добавлением новой записи
        # Если история уже достигла лимита, удаляем самые старые записи
        if len(self._history) >= self.max_history_size:
            # Очищаем старую историю (старше 7 дней) или самые старые записи
            self.clear_old_history(max_age_days=7)
            
            # Если всё ещё переполнено, удаляем самые старые записи
            if len(self._history) >= self.max_history_size:
                sorted_history = sorted(
                    self._history.items(),
                    key=lambda x: x[1].last_seen
                )
                # Удаляем достаточно записей, чтобы освободить место для новой
                to_remove = len(self._history) - self.max_history_size + 1
                for hash_val, _ in sorted_history[:to_remove]:
                    del self._history[hash_val]
        
        # Получаем или создаём историю
        if suggestion_hash not in self._history:
            self._history[suggestion_hash] = ConfidenceHistory(
                suggestion_hash=suggestion_hash,
                file_hash=file_hash,
                first_seen=current_time,
                last_seen=current_time
            )
            self._file_hashes[file_hash] = current_time
        
        history = self._history[suggestion_hash]
        
        # Проверяем, изменился ли код
        if history.file_hash != file_hash:
            history.code_changed = True
            history.file_hash = file_hash
            # Сбрасываем наблюдения при изменении кода
            history.observations.clear()
            history.ast_confirmations = 0
            history.web_confirmations = 0
            history.first_seen = current_time
        
        # Обновляем историю
        history.last_seen = current_time
        history.observations.append((current_time, base_confidence))
        
        if ast_confirmed:
            history.ast_confirmations += 1
        if web_confirmed:
            history.web_confirmations += 1
        
        # Вычисляем effective_confidence
        return self._calculate_effective_confidence(history, base_confidence)
    
    def _calculate_effective_confidence(
        self,
        history: ConfidenceHistory,
        base_confidence: float
    ) -> float:
        """Вычисляет effective_confidence на основе истории.
        
        Формула:
        effective = base + repetition_bonus + stability_bonus + ast_bonus + web_bonus
        
        Где:
        - repetition_bonus: до 0.15 за повторяемость (3+ наблюдения)
        - stability_bonus: до 0.10 за стабильность кода (не менялся)
        - ast_bonus: до 0.05 за AST подтверждение
        - web_bonus: до 0.05 за веб-подтверждение
        """
        effective = base_confidence
        
        # Бонус за повторяемость
        observation_count = len(history.observations)
        if observation_count >= self.min_observations:
            # Максимум 0.15 за 5+ наблюдений
            repetition_bonus = min(0.15, (observation_count - self.min_observations + 1) * 0.03)
            effective += repetition_bonus
        
        # Бонус за стабильность кода
        if not history.code_changed and observation_count >= 2:
            # Код не менялся между наблюдениями
            time_span = (history.last_seen - history.first_seen).total_seconds() / 3600
            if time_span >= self.stability_window_hours:
                # Код стабилен более stability_window_hours часов
                stability_bonus = min(0.10, time_span / self.stability_window_hours * 0.05)
                effective += stability_bonus
        
        # Бонус за AST подтверждение
        if history.ast_confirmations > 0:
            ast_bonus = min(0.05, history.ast_confirmations * 0.02)
            effective += ast_bonus
        
        # Бонус за веб-подтверждение
        if history.web_confirmations > 0:
            web_bonus = min(0.05, history.web_confirmations * 0.02)
            effective += web_bonus
        
        # Ограничиваем максимумом 1.0
        return min(1.0, effective)
    
    def get_history(self, suggestion_hash: str) -> Optional[ConfidenceHistory]:
        """Возвращает историю для предложения."""
        return self._history.get(suggestion_hash)
    
    def clear_old_history(self, max_age_days: int = 30):
        """Очищает старую историю (старше max_age_days дней).
        
        Также очищает связанные file_hashes для освобождения памяти.
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        to_remove = []
        file_hashes_to_remove = set()
        
        for hash_val, history in self._history.items():
            if history.last_seen < cutoff:
                to_remove.append(hash_val)
                file_hashes_to_remove.add(history.file_hash)
        
        # Удаляем старую историю
        for hash_val in to_remove:
            del self._history[hash_val]
        
        # Удаляем связанные file_hashes (если они больше не используются)
        for file_hash in file_hashes_to_remove:
            # Проверяем, используется ли file_hash в оставшейся истории
            still_used = any(
                h.file_hash == file_hash 
                for h in self._history.values()
            )
            if not still_used:
                self._file_hashes.pop(file_hash, None)
    
    def get_stats(self) -> Dict[str, any]:
        """Возвращает статистику аккумулятора."""
        total_suggestions = len(self._history)
        if total_suggestions == 0:
            return {
                "total_suggestions": 0,
                "total_observations": 0,
                "average_observations": 0,
                "suggestions_with_accumulation": 0,
                "accumulation_rate": 0.0,
                "history_size": 0,
                "max_history_size": self.max_history_size
            }
        
        total_observations = sum(len(h.observations) for h in self._history.values())
        accumulated = sum(1 for h in self._history.values() if len(h.observations) >= self.min_observations)
        
        # Вычисляем среднюю и максимальную уверенность
        all_confidences = []
        for history in self._history.values():
            all_confidences.extend([obs[1] for obs in history.observations])
        
        return {
            "total_suggestions": total_suggestions,
            "total_observations": total_observations,
            "average_observations": total_observations / total_suggestions,
            "suggestions_with_accumulation": accumulated,
            "accumulation_rate": accumulated / total_suggestions if total_suggestions > 0 else 0,
            "average_confidence": sum(all_confidences) / len(all_confidences) if all_confidences else 0.0,
            "max_confidence": max(all_confidences) if all_confidences else 0.0,
            "history_size": len(self._history),
            "max_history_size": self.max_history_size
        }
