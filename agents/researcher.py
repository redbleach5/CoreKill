"""Агент для сбора контекста (RAG + веб-поиск + память + codebase indexing)."""
from typing import Optional, Any
from pathlib import Path
from infrastructure.rag import RAGSystem
from infrastructure.web_search import web_search
from infrastructure.context_engine import ContextEngine
from agents.memory import MemoryAgent
from utils.logger import get_logger


logger = get_logger()


class ResearcherAgent:
    """Агент для сбора релевантного контекста из RAG, codebase и веб-поиска.
    
    Стратегия:
    1. Если указан project_path — индексирует и ищет в кодовой базе (ContextEngine)
    2. Пытается найти информацию в локальном RAG (память прошлых задач)
    3. Если уверенность < 0.7 или результатов мало → делает веб-поиск
    4. Объединяет результаты в качественный контекстный блок
    """
    
    def __init__(
        self,
        rag_system: Optional[RAGSystem] = None,
        memory_agent: Optional[MemoryAgent] = None,
        context_engine: Optional[ContextEngine] = None
    ) -> None:
        """Инициализация агента исследования.
        
        Args:
            rag_system: Опциональный экземпляр RAGSystem. Если None, создаётся новый.
            memory_agent: Опциональный экземпляр MemoryAgent для получения рекомендаций.
            context_engine: Опциональный экземпляр ContextEngine для индексации кодовой базы.
        """
        self.rag = rag_system if rag_system is not None else RAGSystem()
        self.memory = memory_agent
        self.context_engine = context_engine if context_engine is not None else ContextEngine()
        self.min_confidence_threshold = 0.7
        self.min_rag_results = 2
    
    def research(
        self,
        query: str,
        intent_type: Optional[str] = None,
        max_web_results: int = 3,
        disable_web_search: bool = False,
        project_path: Optional[str] = None,
        file_extensions: Optional[list[str]] = None,
        complexity: Optional[Any] = None
    ) -> str:
        """Собирает релевантный контекст для запроса.
        
        Args:
            query: Поисковый запрос
            intent_type: Опциональный тип намерения для поиска в памяти
            max_web_results: Максимальное количество результатов веб-поиска
            disable_web_search: Отключить веб-поиск даже если RAG не нашёл контекст
            project_path: Путь к проекту для индексации кодовой базы (ContextEngine)
            file_extensions: Расширения файлов для индексации (по умолчанию ['.py'])
            complexity: Сложность задачи (для ограничения контекста для простых задач)
            
        Returns:
            Объединённый контекстный блок с информацией из codebase, RAG, памяти и веб-поиска
        """
        if not query.strip():
            return ""
        
        # ИСПРАВЛЕНИЕ: Для приветствий с вопросами всё равно используем веб-поиск
        # если запрос содержит вопросы о фактах
        if intent_type == "greeting":
            # Проверяем, есть ли в запросе вопросы (не просто "привет")
            has_question = any(indicator in query.lower() for indicator in ["?", "знаешь", "do you know", "what", "who", "when", "where"])
            if not has_question or len(query.split()) <= 3:
                logger.info("ℹ️ Пропущен поиск контекста для простого приветствия")
                return ""
            else:
                logger.info("ℹ️ Приветствие содержит вопрос - используем веб-поиск для ответа")
        
        logger.info(f"🔍 Ищу контекст для: {query[:60]}...")
        
        context_parts: list[str] = []
        
        # Шаг 0: Если указан project_path — ищем в кодовой базе через ContextEngine
        # Для create+simple задач ограничиваем или пропускаем контекст из codebase
        # чтобы не засорять промпт посторонним кодом
        should_limit_codebase = (
            intent_type == "create" and 
            complexity is not None and 
            hasattr(complexity, 'value') and 
            complexity.value == "simple"
        )
        
        if project_path and not should_limit_codebase:
            codebase_context = self._search_codebase(query, project_path, file_extensions)
            if codebase_context:
                context_parts.append("[Контекст кодовой базы]")
                context_parts.append(codebase_context)
                context_parts.append("")  # Пустая строка для разделения
        elif project_path and should_limit_codebase:
            # Для create+simple используем сильно ограниченный контекст
            codebase_context = self._search_codebase(
                query, project_path, file_extensions, max_context_tokens=500
            )
            if codebase_context:
                context_parts.append("[Контекст кодовой базы (ограничен для простой задачи)]")
                context_parts.append(codebase_context)
                context_parts.append("")  # Пустая строка для разделения
        
        # Шаг 1: Проверяем память на наличие похожих задач
        if self.memory and intent_type:
            memory_recommendations = self.memory.get_recommendations(query, intent_type)
            if memory_recommendations:
                context_parts.append(memory_recommendations)
                context_parts.append("")  # Пустая строка для разделения
                logger.info("💾 Найдены рекомендации из памяти прошлых задач")
        
        # Шаг 2: Поиск в локальном RAG
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
        
        # Шаг 3: Веб-поиск если нужно
        # Типы intent где веб-поиск обычно не нужен (генерация кода, тесты, рефакторинг, анализ проекта)
        skip_web_for_intents = {"create", "test", "refactor", "greeting", "modify", "analyze"}
        
        needs_web_search = (
            not disable_web_search and
            intent_type not in skip_web_for_intents and  # Пропускаем поиск для code-задач
            (rag_confidence < self.min_confidence_threshold or
            not has_enough_rag or
            not rag_context.strip())
        )
        
        # Для explain, debug, optimize — поиск может быть полезен
        if intent_type in ("explain", "debug", "optimize") and not disable_web_search:
            # Для этих типов ищем даже если RAG нашёл что-то
            if not rag_context.strip():
                needs_web_search = True
                logger.info(f"🌐 Intent {intent_type} требует контекста — включаем веб-поиск")
        
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
        # ChromaDB с cosine distance возвращает значения где:
        # - 0.0 = идентичные векторы (максимальная схожесть)
        # - 1.0 = ортогональные векторы (нет схожести)
        # - 2.0 = противоположные векторы (максимальная несхожесть)
        # Для cosine distance: меньше = лучше (больше схожесть)
        min_distance = min((r.get("distance", 1.0) for r in results), default=1.0)
        
        # Преобразуем cosine distance в уверенность
        # Cosine distance в диапазоне [0, 2], но обычно для похожих документов < 0.5
        # Для близких результатов (distance < 0.2) → очень высокая уверенность
        # Для далёких результатов (distance > 0.8) → низкая уверенность
        if min_distance < 0.2:
            base_confidence = 0.95  # Очень похожие документы
        elif min_distance < 0.3:
            base_confidence = 0.85  # Похожие документы
        elif min_distance < 0.5:
            base_confidence = 0.7   # Умеренно похожие
        elif min_distance < 0.7:
            base_confidence = 0.5   # Слабо похожие
        else:
            base_confidence = 0.3   # Не очень релевантные
        
        # Учитываем количество результатов
        count_factor = min(len(results) / 4.0, 1.0)
        
        confidence = base_confidence * (0.7 + 0.3 * count_factor)
        return min(confidence, 1.0)
    
    def _search_codebase(
        self,
        query: str,
        project_path: str,
        file_extensions: Optional[list[str]] = None,
        max_context_tokens: Optional[int] = None
    ) -> str:
        """Ищет релевантный контекст в кодовой базе проекта.
        
        Args:
            query: Поисковый запрос
            project_path: Путь к проекту
            file_extensions: Расширения файлов для поиска (по умолчанию ['.py'])
            max_context_tokens: Максимальное количество токенов в контексте (опционально)
            
        Returns:
            Контекст из кодовой базы или пустая строка
        """
        if not project_path:
            return ""
        
        # Проверяем существование пути
        project_path_obj = Path(project_path)
        if not project_path_obj.exists():
            logger.warning(f"⚠️ Путь к проекту не существует: {project_path}")
            return ""
        
        extensions = file_extensions or ['.py']
        
        try:
            # Получаем контекст через ContextEngine
            codebase_context = self.context_engine.get_context(
                query=query,
                project_path=project_path,
                extensions=extensions,
                max_context_tokens=max_context_tokens
            )
            
            if codebase_context:
                logger.info(f"📂 Найден контекст в кодовой базе ({len(codebase_context)} символов)")
                return codebase_context
            else:
                logger.info("ℹ️ Релевантный контекст в кодовой базе не найден")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска в кодовой базе: {e}", error=e)
            return ""
    
    def index_project(
        self,
        project_path: str,
        file_extensions: Optional[list[str]] = None
    ) -> int:
        """Индексирует проект для последующего поиска.
        
        Args:
            project_path: Путь к проекту
            file_extensions: Расширения файлов для индексации
            
        Returns:
            Количество проиндексированных файлов
        """
        extensions = file_extensions or ['.py']
        
        try:
            index = self.context_engine.index_project(project_path, extensions)
            file_count = len(index)
            logger.info(f"📚 Проиндексировано {file_count} файлов в проекте {project_path}")
            return file_count
        except Exception as e:
            logger.error(f"❌ Ошибка индексации проекта: {e}", error=e)
            return 0
    
    def _format_web_results(self, results: list[dict[str, str]]) -> str:
        """Форматирует результаты веб-поиска в markdown.
        
        Args:
            results: Список словарей с полями title, url, snippet
            
        Returns:
            Отформатированная строка с контекстом в markdown
        """
        if not results:
            return ""
        
        formatted_parts: list[str] = []
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "").strip()
            url = result.get("url", "").strip()
            snippet = result.get("snippet", "").strip()
            
            if title and url:
                # Markdown ссылка
                formatted_parts.append(f"**{i}. [{title}]({url})**")
                if snippet:
                    formatted_parts.append(f"   {snippet}")
                formatted_parts.append("")  # Пустая строка между результатами
            elif title:
                formatted_parts.append(f"**{i}. {title}**")
                if snippet:
                    formatted_parts.append(f"   {snippet}")
                formatted_parts.append("")
        
        return "\n".join(formatted_parts).strip()
