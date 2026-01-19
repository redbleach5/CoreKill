"""Агент для сбора контекста (RAG + веб-поиск + память)."""
from typing import Optional
from infrastructure.rag import RAGSystem
from infrastructure.web_search import web_search
from agents.memory import MemoryAgent
from utils.logger import get_logger


logger = get_logger()


class ResearcherAgent:
    """Агент для сбора релевантного контекста из RAG и веб-поиска.
    
    Стратегия:
    1. Сначала пытается найти информацию в локальном RAG
    2. Если уверенность < 0.7 или результатов мало → делает веб-поиск
    3. Объединяет результаты в качественный контекстный блок
    """
    
    def __init__(
        self,
        rag_system: Optional[RAGSystem] = None,
        memory_agent: Optional[MemoryAgent] = None
    ) -> None:
        """Инициализация агента исследования.
        
        Args:
            rag_system: Опциональный экземпляр RAGSystem. Если None, создаётся новый.
            memory_agent: Опциональный экземпляр MemoryAgent для получения рекомендаций.
        """
        self.rag = rag_system if rag_system is not None else RAGSystem()
        self.memory = memory_agent
        self.min_confidence_threshold = 0.7
        self.min_rag_results = 2
    
    def research(
        self,
        query: str,
        intent_type: Optional[str] = None,
        max_web_results: int = 3,
        disable_web_search: bool = False
    ) -> str:
        """Собирает релевантный контекст для запроса.
        
        Args:
            query: Поисковый запрос
            intent_type: Опциональный тип намерения для поиска в памяти
            max_web_results: Максимальное количество результатов веб-поиска
            disable_web_search: Отключить веб-поиск даже если RAG не нашёл контекст
            
        Returns:
            Объединённый контекстный блок с информацией из RAG, памяти и веб-поиска
        """
        if not query.strip():
            return ""
        
        # Не ищем контекст для приветствий
        if intent_type == "greeting":
            logger.info("ℹ️ Пропущен поиск контекста для приветствия")
            return ""
        
        logger.info(f"🔍 Ищу контекст для: {query[:60]}...")
        
        context_parts: list[str] = []
        
        # Шаг 0: Проверяем память на наличие похожих задач
        if self.memory and intent_type:
            memory_recommendations = self.memory.get_recommendations(query, intent_type)
            if memory_recommendations:
                context_parts.append(memory_recommendations)
                context_parts.append("")  # Пустая строка для разделения
                logger.info("💾 Найдены рекомендации из памяти прошлых задач")
        
        # Шаг 1: Поиск в локальном RAG
        rag_context = self.rag.get_relevant_context(query, n_results=4)
        rag_results_with_meta = self.rag.get_relevant_context_with_metadata(query, n_results=4)
        
        # Оцениваем качество RAG-результатов
        rag_confidence = self._calculate_rag_confidence(rag_results_with_meta)
        has_enough_rag = len(rag_results_with_meta) >= self.min_rag_results
        
        logger.info(
            f"📚 RAG результаты: найдено {len(rag_results_with_meta)} документов "
            f"(уверенность: {rag_confidence:.2f})"
        )
        
        # Добавляем RAG-контекст если он есть
        if rag_context:
            context_parts.append("[Локальный контекст из RAG]")
            context_parts.append(rag_context)
            context_parts.append("")  # Пустая строка для разделения
        
        # Шаг 2: Веб-поиск если нужно
        needs_web_search = (
            not disable_web_search and
            (rag_confidence < self.min_confidence_threshold or
            not has_enough_rag or
            not rag_context.strip())
        )
        
        if needs_web_search:
            logger.info("🌐 RAG недостаточно, выполняю веб-поиск...")
            web_results = web_search(query, max_results=max_web_results, timeout=10)
            
            if web_results:
                logger.info(f"✅ Найдено {len(web_results)} результатов веб-поиска")
                
                web_context = self._format_web_results(web_results)
                if web_context:
                    context_parts.append("[Веб-контекст]")
                    context_parts.append(web_context)
            else:
                logger.warning("⚠️ Веб-поиск не вернул результатов")
        
        # Объединяем весь контекст
        final_context = "\n".join(context_parts).strip()
        
        if final_context:
            logger.info(f"✅ Контекст собран (размер: {len(final_context)} символов)")
        else:
            logger.warning("⚠️ Не удалось собрать контекст")
        
        return final_context
    
    def _calculate_rag_confidence(self, results: list[dict]) -> float:
        """Вычисляет уверенность на основе RAG-результатов.
        
        Уверенность зависит от:
        - Количества найденных результатов
        - Расстояния до ближайших документов (distance в ChromaDB)
        
        Args:
            results: Список результатов RAG с метаданными
            
        Returns:
            Уверенность от 0.0 до 1.0
        """
        if not results:
            return 0.0
        
        # Если есть результаты, берём минимальное расстояние
        # ChromaDB возвращает косинусное расстояние (меньше = лучше)
        min_distance = min((r.get("distance", 1.0) for r in results), default=1.0)
        
        # Преобразуем расстояние в уверенность
        # Косинусное расстояние обычно в диапазоне [0, 2]
        # Для близких результатов (distance < 0.5) → высокая уверенность
        # Для далёких результатов (distance > 1.0) → низкая уверенность
        if min_distance < 0.3:
            base_confidence = 0.9
        elif min_distance < 0.5:
            base_confidence = 0.75
        elif min_distance < 0.7:
            base_confidence = 0.6
        else:
            base_confidence = 0.4
        
        # Учитываем количество результатов
        count_factor = min(len(results) / 4.0, 1.0)
        
        confidence = base_confidence * (0.7 + 0.3 * count_factor)
        return min(confidence, 1.0)
    
    def _format_web_results(self, results: list[dict[str, str]]) -> str:
        """Форматирует результаты веб-поиска в читаемый текст.
        
        Args:
            results: Список словарей с полями title, url, snippet
            
        Returns:
            Отформатированная строка с контекстом
        """
        if not results:
            return ""
        
        formatted_parts: list[str] = []
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "").strip()
            url = result.get("url", "").strip()
            snippet = result.get("snippet", "").strip()
            
            if title:
                formatted_parts.append(f"{i}. {title}")
                if url:
                    formatted_parts.append(f"   URL: {url}")
                if snippet:
                    formatted_parts.append(f"   {snippet}")
                formatted_parts.append("")  # Пустая строка между результатами
        
        return "\n".join(formatted_parts).strip()
