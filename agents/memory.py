"""Система памяти для сохранения и поиска прошлого опыта."""
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from infrastructure.rag import RAGSystem
from utils.logger import get_logger


logger = get_logger()


@dataclass
class TaskMemory:
    """Структура для хранения информации о выполненной задаче."""
    task: str  # Исходная задача
    intent_type: str  # Тип намерения
    success: float  # Успешность (0.0-1.0, из reflection)
    planning_score: float
    research_score: float
    testing_score: float
    coding_score: float
    overall_score: float
    key_decisions: str  # Ключевые решения/подходы, которые сработали
    prompts_used: str  # Промпты/стратегии, которые были эффективны
    what_worked: str  # Что сработало хорошо
    what_didnt_work: str  # Что не сработало


class MemoryAgent:
    """Агент для сохранения и поиска прошлого опыта в ChromaDB.
    
    Сохраняет информацию о выполненных задачах и умеет находить похожие задачи
    для извлечения уроков.
    """

    def __init__(self, rag_system: Optional[RAGSystem] = None) -> None:
        """Инициализация агента памяти.
        
        Args:
            rag_system: Опциональный RAGSystem для хранения памяти.
                       Если None, создаётся новый с коллекцией "task_memory".
        """
        # Используем отдельную коллекцию для памяти
        if rag_system is not None:
            self.memory_rag = rag_system
        else:
            # Создаём отдельную RAG систему для памяти
            from infrastructure.rag import RAGSystem as BaseRAG
            self.memory_rag = BaseRAG(collection_name="task_memory", persist_directory=".chromadb")
        
        self.collection_name = "task_memory"
        self.task_counter = 0

    def save_task_experience(
        self,
        task: str,
        intent_type: str,
        reflection_result: Any,  # ReflectionResult
        key_decisions: str = "",
        prompts_used: str = "",
        what_worked: str = "",
        what_didnt_work: str = "",
        feedback: Optional[str] = None,  # "positive" или "negative"
        code: str = "",  # Готовый код для переиспользования
        plan: str = ""  # План для переиспользования
    ) -> None:
        """Сохраняет опыт выполнения задачи в память.
        
        Args:
            task: Исходная задача
            intent_type: Тип намерения
            reflection_result: Результат рефлексии (ReflectionResult)
            key_decisions: Ключевые решения, которые были приняты
            prompts_used: Промпты/стратегии, которые использовались
            what_worked: Что сработало хорошо
            what_didnt_work: Что не сработало
            code: Готовый код для переиспользования (опционально)
            plan: План для переиспользования (опционально)
        """
        self.task_counter += 1
        
        task_memory = TaskMemory(
            task=task,
            intent_type=intent_type,
            success=reflection_result.overall_score,
            planning_score=reflection_result.planning_score,
            research_score=reflection_result.research_score,
            testing_score=reflection_result.testing_score,
            coding_score=reflection_result.coding_score,
            overall_score=reflection_result.overall_score,
            key_decisions=key_decisions or reflection_result.analysis,
            prompts_used=prompts_used,
            what_worked=what_worked or reflection_result.analysis,
            what_didnt_work=what_didnt_work or ""
        )
        
        # Формируем текст для сохранения в RAG (включая код и план для поиска)
        memory_text = self._format_memory_text(task_memory, code=code, plan=plan)
        
        # Создаём метаданные
        metadata = {
            "task_id": f"task_{self.task_counter}",
            "intent_type": intent_type,
            "success": str(reflection_result.overall_score),
            "overall_score": str(reflection_result.overall_score),
            "timestamp": str(self.task_counter),  # Простой счётчик вместо timestamp
            "has_code": "true" if code else "false",
            "has_plan": "true" if plan else "false"
        }
        
        # Сохраняем код и план отдельно в метаданных для быстрого доступа
        # (ограничиваем размер для метаданных)
        if code:
            metadata["code_preview"] = code[:500]  # Первые 500 символов для быстрого поиска
        if plan:
            metadata["plan_preview"] = plan[:500]
        
        # Сохраняем в RAG
        self.memory_rag.add_documents(
            documents=[memory_text],
            metadatas=[metadata]
        )
        
        # Сохраняем полный код и план в отдельном хранилище (если нужно)
        # Пока используем расширенный текст в документе
        
        logger.info(f"💾 Опыт задачи сохранён в память (ID: task_{self.task_counter}, успех: {reflection_result.overall_score:.2f}, код: {'да' if code else 'нет'})")

    def find_exact_or_very_similar_task(
        self,
        query: str,
        intent_type: Optional[str] = None,
        min_success: float = 0.8,
        similarity_threshold: float = 0.85  # Порог для "очень похожей" задачи
    ) -> Optional[Dict[str, Any]]:
        """Находит идентичную или очень похожую задачу для переиспользования решения.
        
        Используется для пропуска workflow, если задача уже решалась.
        
        Args:
            query: Поисковый запрос (текущая задача)
            intent_type: Опциональный фильтр по типу намерения
            min_success: Минимальный уровень успешности прошлой задачи
            similarity_threshold: Минимальный порог схожести (distance < 1 - threshold)
            
        Returns:
            Словарь с информацией о найденной задаче или None
        """
        if not query.strip():
            return None
        
        logger.info(f"🔍 Ищу идентичную/очень похожую задачу для: {query[:50]}...")
        
        # Ищем похожие задачи в RAG
        results = self.memory_rag.get_relevant_context_with_metadata(
            query=query,
            n_results=5  # Берём несколько для проверки схожести
        )
        
        for result in results:
            metadata = result.get("metadata", {})
            document = result.get("document", "")
            distance = result.get("distance", 1.0)
            
            # Проверяем схожесть (distance < 0.15 означает очень высокую схожесть)
            similarity = 1.0 - distance
            if similarity < similarity_threshold:
                continue
            
            # Фильтруем по типу намерения если указан
            if intent_type and metadata.get("intent_type") != intent_type:
                continue
            
            # Фильтруем по успешности
            try:
                success = float(metadata.get("success", "0.0"))
                if success < min_success:
                    continue
            except (ValueError, TypeError):
                continue
            
            # Проверяем, есть ли готовый код
            has_code = metadata.get("has_code", "false") == "true"
            
            # Парсим информацию из документа
            task_info = self._parse_memory_document(document, metadata)
            task_info["similarity"] = similarity
            task_info["distance"] = distance
            task_info["has_code"] = has_code
            
            logger.info(f"✅ Найдена очень похожая задача (схожесть: {similarity:.2f}, успех: {success:.2f})")
            return task_info
        
        logger.info("ℹ️ Идентичной/очень похожей задачи не найдено")
        return None

    def find_similar_tasks(
        self,
        query: str,
        intent_type: Optional[str] = None,
        min_success: float = 0.7,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Находит похожие задачи из прошлого опыта.
        
        Args:
            query: Поисковый запрос (обычно текущая задача)
            intent_type: Опциональный фильтр по типу намерения
            min_success: Минимальный уровень успешности прошлых задач
            max_results: Максимальное количество результатов
            
        Returns:
            Список словарей с информацией о похожих задачах:
            {
                "task": str,
                "intent_type": str,
                "success": float,
                "what_worked": str,
                "key_decisions": str,
                "metadata": dict
            }
        """
        if not query.strip():
            return []
        
        logger.info(f"🔍 Ищу похожие задачи в памяти для: {query[:50]}...")
        
        # Ищем похожие задачи в RAG
        results = self.memory_rag.get_relevant_context_with_metadata(
            query=query,
            n_results=max_results * 2  # Берём больше, потом отфильтруем
        )
        
        similar_tasks: List[Dict[str, Any]] = []
        
        for result in results:
            metadata = result.get("metadata", {})
            document = result.get("document", "")
            
            # Фильтруем по типу намерения если указан
            if intent_type and metadata.get("intent_type") != intent_type:
                continue
            
            # Фильтруем по успешности
            try:
                success = float(metadata.get("success", "0.0"))
                if success < min_success:
                    continue
            except (ValueError, TypeError):
                continue
            
            # Парсим информацию из документа
            task_info = self._parse_memory_document(document, metadata)
            
            similar_tasks.append(task_info)
            
            if len(similar_tasks) >= max_results:
                break
        
        if similar_tasks:
            logger.info(f"✅ Найдено {len(similar_tasks)} похожих успешных задач")
        else:
            logger.info("ℹ️ Похожих задач в памяти не найдено")
        
        return similar_tasks

    def get_recommendations(
        self,
        current_task: str,
        intent_type: str
    ) -> str:
        """Получает рекомендации на основе прошлого опыта.
        
        Args:
            current_task: Текущая задача
            intent_type: Тип намерения
            
        Returns:
            Текст с рекомендациями на основе прошлого опыта
        """
        similar_tasks = self.find_similar_tasks(
            query=current_task,
            intent_type=intent_type,
            min_success=0.7,
            max_results=2
        )
        
        if not similar_tasks:
            return ""
        
        recommendations_parts: List[str] = []
        recommendations_parts.append("[Рекомендации из памяти]")
        recommendations_parts.append("В прошлый раз для похожей задачи сработало:")
        
        for i, task_info in enumerate(similar_tasks, 1):
            recommendations_parts.append(f"\n{i}. Задача: {task_info['task'][:100]}...")
            recommendations_parts.append(f"   Успешность: {task_info['success']:.2f}")
            
            if task_info.get("what_worked"):
                recommendations_parts.append(f"   Что сработало: {task_info['what_worked'][:200]}")
            
            if task_info.get("key_decisions"):
                recommendations_parts.append(f"   Ключевые решения: {task_info['key_decisions'][:200]}")
        
        return "\n".join(recommendations_parts)

    def _format_memory_text(self, task_memory: TaskMemory, code: str = "", plan: str = "") -> str:
        """Форматирует TaskMemory в текст для сохранения в RAG.
        
        Args:
            task_memory: Экземпляр TaskMemory
            code: Готовый код (опционально)
            plan: План (опционально)
            
        Returns:
            Отформатированный текст
        """
        parts: List[str] = []
        
        parts.append(f"Задача: {task_memory.task}")
        parts.append(f"Тип намерения: {task_memory.intent_type}")
        parts.append(f"Успешность: {task_memory.overall_score:.2f}")
        
        if plan:
            parts.append(f"План: {plan[:1000]}")  # Ограничиваем размер плана
        
        if task_memory.what_worked:
            parts.append(f"Что сработало: {task_memory.what_worked}")
        
        if task_memory.key_decisions:
            parts.append(f"Ключевые решения: {task_memory.key_decisions}")
        
        if task_memory.prompts_used:
            parts.append(f"Промпты/стратегии: {task_memory.prompts_used}")
        
        if code:
            # Добавляем код для поиска (первые 2000 символов для embedding)
            parts.append(f"Код: {code[:2000]}")
        
        if task_memory.what_didnt_work:
            parts.append(f"Что не сработало: {task_memory.what_didnt_work}")
        
        return "\n".join(parts)

    def _parse_memory_document(self, document: str, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Парсит документ из памяти обратно в структурированный формат.
        
        Args:
            document: Текст документа из RAG
            metadata: Метаданные из RAG
            
        Returns:
            Словарь с информацией о задаче
        """
        task_info: Dict[str, Any] = {
            "task": "",
            "intent_type": metadata.get("intent_type", ""),
            "success": float(metadata.get("success", "0.0")),
            "what_worked": "",
            "key_decisions": "",
            "metadata": metadata
        }
        
        # Парсим текст документа
        lines = document.split("\n")
        current_field = None
        
        for line in lines:
            stripped = line.strip()
            
            if "Задача:" in stripped:
                task_info["task"] = stripped.split(":", 1)[-1].strip()
            elif "План:" in stripped:
                current_field = "plan"
                task_info["plan"] = stripped.split(":", 1)[-1].strip()
            elif "Код:" in stripped:
                current_field = "code"
                task_info["code"] = stripped.split(":", 1)[-1].strip()
            elif "Что сработало:" in stripped:
                current_field = "what_worked"
                task_info["what_worked"] = stripped.split(":", 1)[-1].strip()
            elif "Ключевые решения:" in stripped:
                current_field = "key_decisions"
                task_info["key_decisions"] = stripped.split(":", 1)[-1].strip()
            elif current_field and stripped:
                # Продолжение предыдущего поля
                if current_field not in task_info:
                    task_info[current_field] = ""
                task_info[current_field] += " " + stripped
        
        # Извлекаем код и план из метаданных если есть
        if metadata.get("code_preview"):
            task_info["code_preview"] = metadata.get("code_preview", "")
        if metadata.get("plan_preview"):
            task_info["plan_preview"] = metadata.get("plan_preview", "")
        
        return task_info
