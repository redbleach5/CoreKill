"""Context Engine v0.1 - Минимальная реализация для понимания структуры кода.

Проблема: Небольшие модели (7B) не могут обработать большие кодовые базы (50-500K токенов)
в контексте (4-8K). Простой RAG не учитывает структуру кода и зависимости.

Решение v0.1 (минимальная реализация):
- Умное разбиение кода на чанки (учитывает функции/классы)
- Простая оценка релевантности (BM25 + ключевые слова)
- Сборка оптимального контекста в пределах лимита токенов
- Кэширование индекса проекта

Что НЕ включено (для упрощения):
- AST парсинг и граф зависимостей (слишком сложно для v0.1)
- Иерархические сводки через LLM (слишком дорого)
- Сложные стратегии композиции (GREEDY достаточно)
"""
import re
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from collections import Counter
import math


@dataclass
class CodeChunk:
    """Чанк кода с метаданными."""
    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: str  # "function", "class", "module"
    name: str  # Имя функции/класса/модуля
    signature: str = ""  # Сигнатура функции/класса
    docstring: str = ""  # Docstring если есть
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def estimated_tokens(self) -> int:
        """Примерная оценка токенов (~4 символа = 1 токен)."""
        return len(self.content) // 4


@dataclass
class ScoredChunk:
    """Чанк с оценкой релевантности."""
    chunk: CodeChunk
    score: float
    matched_keywords: List[str] = field(default_factory=list)


class CodeChunker:
    """Умное разбиение кода на чанки с учётом структуры."""
    
    # Регулярные выражения для поиска структурных элементов
    CLASS_PATTERN = re.compile(r'^class\s+(\w+)(?:\([^)]+\))?:', re.MULTILINE)
    FUNCTION_PATTERN = re.compile(r'^def\s+(\w+)\s*\([^)]*\)\s*[-:>]?', re.MULTILINE)
    
    def __init__(self, max_chunk_tokens: int = 500) -> None:
        """Инициализация чанкера.
        
        Args:
            max_chunk_tokens: Максимальный размер чанка в токенах
        """
        self.max_chunk_tokens = max_chunk_tokens
    
    def chunk_file(self, file_path: str, content: str) -> List[CodeChunk]:
        """Разбивает файл на структурированные чанки.
        
        Args:
            file_path: Путь к файлу
            content: Содержимое файла
            
        Returns:
            Список чанков с учётом структуры (классы, функции)
        """
        if not content.strip():
            return []
        
        chunks: List[CodeChunk] = []
        lines = content.split('\n')
        
        # Находим все классы и функции
        class_positions = self._find_classes(content, lines)
        function_positions = self._find_functions(content, lines)
        
        # Сортируем все элементы по позиции
        all_elements = sorted(
            class_positions + function_positions,
            key=lambda x: x['start_line']
        )
        
        if not all_elements:
            # Если нет классов/функций, создаём один чанк для всего файла
            return [self._create_module_chunk(file_path, content, 1, len(lines))]
        
        # Разбиваем на чанки по границам классов/функций
        for i, element in enumerate(all_elements):
            start_line = element['start_line']
            end_line = element['end_line']
            
            # Извлекаем сигнатуру и docstring
            signature, docstring = self._extract_metadata(
                content,
                start_line - 1,
                end_line
            )
            
            chunk_content = self._extract_content(lines, start_line - 1, end_line)
            chunk = CodeChunk(
                id=f"{file_path}:{start_line}-{end_line}",
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=chunk_content,
                chunk_type=element['type'],
                name=element['name'],
                signature=signature,
                docstring=docstring
            )
            
            # Если чанк слишком большой, разбиваем его
            if chunk.estimated_tokens() > self.max_chunk_tokens:
                # Разбиваем большой чанк на меньшие части
                sub_chunks = self._split_large_chunk(chunk)
                chunks.extend(sub_chunks)
            else:
                chunks.append(chunk)
        
        return chunks
    
    def _find_classes(self, content: str, lines: List[str]) -> List[Dict]:
        """Находит все классы в коде."""
        classes = []
        for match in self.CLASS_PATTERN.finditer(content):
            class_name = match.group(1)
            start_line = content[:match.start()].count('\n') + 1
            
            # Находим конец класса (следующий класс/функция на том же уровне или конец файла)
            end_line = self._find_block_end(content, match.start(), lines, indent_level=0)
            
            classes.append({
                'type': 'class',
                'name': class_name,
                'start_line': start_line,
                'end_line': end_line
            })
        
        return classes
    
    def _find_functions(self, content: str, lines: List[str]) -> List[Dict]:
        """Находит все функции в коде."""
        functions = []
        for match in self.FUNCTION_PATTERN.finditer(content):
            func_name = match.group(1)
            start_line = content[:match.start()].count('\n') + 1
            
            # Находим конец функции
            end_line = self._find_block_end(content, match.start(), lines, indent_level=0)
            
            functions.append({
                'type': 'function',
                'name': func_name,
                'start_line': start_line,
                'end_line': end_line
            })
        
        return functions
    
    def _find_block_end(self, content: str, start_pos: int, lines: List[str], indent_level: int) -> int:
        """Находит конец блока (класса/функции) по отступам."""
        start_line_idx = content[:start_pos].count('\n')
        if start_line_idx >= len(lines):
            return len(lines)
        
        # Определяем отступ начала блока
        start_line = lines[start_line_idx]
        base_indent = len(start_line) - len(start_line.lstrip())
        
        # Ищем первую строку с меньшим отступом (или на том же уровне, но это новый блок)
        for i in range(start_line_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip():  # Пустые строки пропускаем
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            # Если отступ меньше или равен базовому, это конец блока
            if current_indent <= base_indent:
                return i
        
        return len(lines)
    
    def _extract_content(self, lines: List[str], start: int, end: int) -> str:
        """Извлекает содержимое между строками."""
        return '\n'.join(lines[start:end])
    
    def _extract_metadata(self, content: str, start_line: int, end_line: int) -> Tuple[str, str]:
        """Извлекает сигнатуру и docstring из блока кода."""
        lines = content.split('\n')[start_line:end_line]
        
        signature = ""
        docstring = ""
        
        # Сигнатура - первая непустая строка
        for line in lines:
            if line.strip():
                signature = line.strip()
                break
        
        # Ищем docstring (тройные кавычки)
        content_slice = '\n'.join(lines)
        docstring_match = re.search(r'"""([^"]*)"""', content_slice, re.DOTALL)
        if not docstring_match:
            docstring_match = re.search(r"'''([^']*)'''", content_slice, re.DOTALL)
        
        if docstring_match:
            docstring = docstring_match.group(1).strip()
        
        return signature, docstring
    
    def _split_large_chunk(self, chunk: CodeChunk) -> List[CodeChunk]:
        """Разбивает большой чанк на меньшие части.
        
        Args:
            chunk: Большой чанк для разбиения
            
        Returns:
            Список меньших чанков
        """
        sub_chunks: List[CodeChunk] = []
        lines = chunk.content.split('\n')
        
        # Простое разбиение по строкам
        chunk_size_lines = max(1, (self.max_chunk_tokens * 4) // 80)  # ~80 символов на строку
        
        for i in range(0, len(lines), chunk_size_lines):
            sub_lines = lines[i:i + chunk_size_lines]
            sub_content = '\n'.join(sub_lines)
            
            if not sub_content.strip():
                continue
            
            sub_chunk = CodeChunk(
                id=f"{chunk.id}:part{i // chunk_size_lines}",
                file_path=chunk.file_path,
                start_line=chunk.start_line + i,
                end_line=min(chunk.start_line + i + len(sub_lines) - 1, chunk.end_line),
                content=sub_content,
                chunk_type=chunk.chunk_type,
                name=f"{chunk.name}_part{i // chunk_size_lines}",
                signature=chunk.signature if i == 0 else "",
                docstring=chunk.docstring if i == 0 else ""
            )
            sub_chunks.append(sub_chunk)
        
        return sub_chunks if sub_chunks else [chunk]
    
    def _create_module_chunk(self, file_path: str, content: str, start: int, end: int) -> CodeChunk:
        """Создаёт чанк для модуля без классов/функций."""
        return CodeChunk(
            id=f"{file_path}:module",
            file_path=file_path,
            start_line=start,
            end_line=end,
            content=content,
            chunk_type="module",
            name=Path(file_path).stem
        )


class RelevanceScorer:
    """Простая оценка релевантности чанков к запросу (BM25-подобная)."""
    
    def __init__(self) -> None:
        """Инициализация скорера."""
        self.idf_cache: Dict[str, float] = {}
    
    def score_chunks(self, query: str, chunks: List[CodeChunk]) -> List[ScoredChunk]:
        """Оценивает релевантность чанков к запросу.
        
        Args:
            query: Поисковый запрос
            chunks: Список чанков для оценки
            
        Returns:
            Список оцененных чанков, отсортированный по релевантности
        """
        if not chunks:
            return []
        
        if not query.strip():
            return [ScoredChunk(chunk=ch, score=0.0) for ch in chunks]
        
        query_terms = self._tokenize(query)
        if not query_terms:
            return [ScoredChunk(chunk=ch, score=0.0) for ch in chunks]
        
        # Предвычисляем IDF для всех терминов
        self._compute_idf(query_terms, chunks)
        
        scored: List[ScoredChunk] = []
        
        for chunk in chunks:
            score, matched = self._score_chunk(query_terms, chunk, chunks)
            scored.append(ScoredChunk(
                chunk=chunk,
                score=score,
                matched_keywords=matched
            ))
        
        # Сортируем по убыванию релевантности
        scored.sort(key=lambda x: x.score, reverse=True)
        
        return scored
    
    def _tokenize(self, text: str) -> List[str]:
        """Разбивает текст на токены (ключевые слова).
        
        Поддерживает CamelCase и snake_case.
        """
        # Сначала разбиваем CamelCase на отдельные слова
        # ConfigManager -> Config Manager
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        # Заменяем snake_case на пробелы
        text = text.replace('_', ' ')
        # Приводим к нижнему регистру
        text = text.lower()
        # Разбиваем по пробелам и знакам препинания
        tokens = re.findall(r'\b\w+\b', text)
        # Фильтруем очень короткие токены и стоп-слова
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by'}
        return [t for t in tokens if len(t) > 2 and t not in stop_words]
    
    def _compute_idf(self, query_terms: List[str], chunks: List[CodeChunk]) -> None:
        """Вычисляет IDF (inverse document frequency) для терминов запроса."""
        total_chunks = len(chunks)
        if total_chunks == 0:
            return
        
        for term in query_terms:
            if term in self.idf_cache:
                continue
            
            # Считаем, в скольких чанках встречается термин
            # Используем _tokenize для правильной обработки CamelCase
            doc_freq = sum(
                1 for chunk in chunks
                if term in self._tokenize(chunk.content) or
                   term in self._tokenize(chunk.name) or
                   term in self._tokenize(chunk.signature)
            )
            
            # IDF = log((total_docs - docs_with_term + 0.5) / (docs_with_term + 0.5))
            # Используем BM25 IDF формулу для избежания нулевых значений
            if doc_freq > 0:
                self.idf_cache[term] = math.log((total_chunks - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
            else:
                # Если термин не найден, даем максимальный IDF
                self.idf_cache[term] = math.log(total_chunks + 1.0)
    
    def _score_chunk(self, query_terms: List[str], chunk: CodeChunk, all_chunks: List[CodeChunk]) -> Tuple[float, List[str]]:
        """Оценивает один чанк по запросу."""
        # Собираем текст чанка для поиска (НЕ lowercase, чтобы сохранить CamelCase)
        chunk_text = f"{chunk.name} {chunk.signature} {chunk.docstring} {chunk.content}"
        
        score = 0.0
        matched = []
        
        # TF (term frequency) - частота термина в чанке
        chunk_terms = self._tokenize(chunk_text)
        total_terms = len(chunk_terms) + 1  # +1 чтобы избежать деления на 0
        
        for term in query_terms:
            term_freq = chunk_terms.count(term)
            
            if term_freq > 0:
                # TF * IDF
                tf = term_freq / total_terms
                idf = self.idf_cache.get(term, 0.0)
                
                # Бонусы за совпадение в имени или сигнатуре
                if term in chunk.name.lower():
                    tf *= 3.0  # Имя - очень важно
                elif term in chunk.signature.lower():
                    tf *= 2.0  # Сигнатура - важно
                elif term in chunk.docstring.lower():
                    tf *= 1.5  # Docstring - важно
                
                score += tf * idf
                matched.append(term)
        
        return score, matched


class ContextComposer:
    """Собирает оптимальный контекст в пределах лимита токенов."""
    
    def __init__(self, max_tokens: int = 4000) -> None:
        """Инициализация композитора.
        
        Args:
            max_tokens: Максимальное количество токенов в контексте
        """
        self.max_tokens = max_tokens
    
    def compose(self, scored_chunks: List[ScoredChunk], query: str = "") -> str:
        """Собирает контекст из оцененных чанков.
        
        Args:
            scored_chunks: Список оцененных чанков (уже отсортированных)
            query: Поисковый запрос (для контекста)
            
        Returns:
            Собранный контекст в пределах лимита токенов
        """
        if not scored_chunks:
            return ""
        
        sections: List[str] = []
        total_tokens = 0
        
        for scored in scored_chunks:
            chunk = scored.chunk
            chunk_tokens = chunk.estimated_tokens()
            
            # Проверяем, поместится ли чанк
            if total_tokens + chunk_tokens > self.max_tokens:
                # Если чанк слишком большой, можем взять только его часть
                # или пропустить, если уже есть достаточно контекста
                
                # Улучшенная логика: если набрали меньше 70% лимита, пробуем взять частично
                # Это даёт больше шансов включить важные чанки
                if total_tokens < self.max_tokens * 0.7:
                    remaining_tokens = self.max_tokens - total_tokens
                    # Минимум 150 токенов для частичного чанка (чтобы было достаточно контекста)
                    if remaining_tokens > 150:
                        partial_content = self._truncate_chunk(chunk, remaining_tokens)
                        sections.append(self._format_chunk(chunk, partial_content, scored.matched_keywords))
                        total_tokens += remaining_tokens  # Обновляем счётчик
                # Если уже набрали достаточно (>= 70%), останавливаемся
                # чтобы не обрезать важные чанки слишком сильно
                break
            
            sections.append(self._format_chunk(chunk, chunk.content, scored.matched_keywords))
            total_tokens += chunk_tokens
        
        return '\n\n'.join(sections)
    
    def _format_chunk(self, chunk: CodeChunk, content: str, matched_keywords: List[str]) -> str:
        """Форматирует чанк для включения в контекст."""
        parts = [f"# {chunk.file_path}:{chunk.name} ({chunk.chunk_type})"]
        
        if chunk.signature:
            parts.append(f"```python\n{chunk.signature}\n```")
        
        if chunk.docstring:
            parts.append(f"Docstring: {chunk.docstring}")
        
        if matched_keywords:
            parts.append(f"Relevant keywords: {', '.join(matched_keywords[:5])}")
        
        parts.append(f"```python\n{content}\n```")
        
        return '\n'.join(parts)
    
    def _truncate_chunk(self, chunk: CodeChunk, max_tokens: int) -> str:
        """Умно обрезает чанк до нужного количества токенов.
        
        Старается сохранить:
        - Начало (сигнатуру и начало функции/класса)
        - Конец (return statements, важные завершающие части)
        
        Args:
            chunk: Чанк для обрезки
            max_tokens: Максимальное количество токенов
            
        Returns:
            Обрезанный контент с сохранением важных частей
        """
        max_chars = max_tokens * 4  # ~4 символа на токен
        if len(chunk.content) <= max_chars:
            return chunk.content
        
        lines = chunk.content.split('\n')
        total_lines = len(lines)
        
        # Если чанк небольшой, просто обрезаем
        if total_lines <= 50:
            truncated = chunk.content[:max_chars]
            last_newline = truncated.rfind('\n')
            if last_newline > max_chars * 0.8:
                truncated = truncated[:last_newline]
            return truncated + "\n# ... (truncated)"
        
        # Для больших чанков: сохраняем начало и конец
        # Распределяем: 60% начало, 40% конец
        start_chars = int(max_chars * 0.6)
        end_chars = max_chars - start_chars
        
        # Начало: берём первые строки до start_chars
        start_lines = []
        start_length = 0
        for line in lines:
            if start_length + len(line) + 1 > start_chars:
                break
            start_lines.append(line)
            start_length += len(line) + 1
        
        # Конец: берём последние строки до end_chars
        # Ищем важные маркеры (return, yield, raise, class/def окончания)
        end_lines = []
        end_length = 0
        
        # Идём с конца и собираем важные строки
        important_keywords = ['return', 'yield', 'raise', 'pass', 'break', 'continue']
        
        for i in range(len(lines) - 1, len(start_lines) - 1, -1):
            line = lines[i]
            line_len = len(line) + 1
            
            if end_length + line_len > end_chars:
                break
            
            # Всегда включаем строки с важными ключевыми словами
            is_important = any(kw in line for kw in important_keywords)
            
            if is_important or end_length == 0:  # Первая строка с конца всегда
                end_lines.insert(0, line)
                end_length += line_len
            elif end_length + line_len <= end_chars * 0.9:  # Оставляем запас
                end_lines.insert(0, line)
                end_length += line_len
        
        # Объединяем начало и конец
        if end_lines and len(end_lines) > 0:
            result = '\n'.join(start_lines) + '\n# ... (middle part truncated) ...\n' + '\n'.join(end_lines)
        else:
            # Если не удалось взять конец, просто обрезаем начало
            result = '\n'.join(start_lines) + '\n# ... (truncated)'
        
        # Проверяем размер и обрезаем если нужно
        if len(result) > max_chars:
            result = result[:max_chars]
            last_newline = result.rfind('\n')
            if last_newline > max_chars * 0.8:
                result = result[:last_newline]
            result += "\n# ... (truncated)"
        
        return result


class ContextEngine:
    """Основной класс Context Engine - объединяет все компоненты."""
    
    def __init__(
        self,
        max_context_tokens: int = 4000,
        max_chunk_tokens: int = 500,
        cache_dir: Optional[Path] = None
    ) -> None:
        """Инициализация Context Engine.
        
        Args:
            max_context_tokens: Максимальный размер контекста
            max_chunk_tokens: Максимальный размер чанка
            cache_dir: Директория для кэширования индексов
        """
        self.chunker = CodeChunker(max_chunk_tokens=max_chunk_tokens)
        self.scorer = RelevanceScorer()
        self.composer = ContextComposer(max_tokens=max_context_tokens)
        self.cache_dir = cache_dir or Path(".context_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # Кэш индексов проектов: cache_key -> {file_path -> chunks}
        self._index_cache: Dict[str, Dict[str, List[CodeChunk]]] = {}
    
    def index_project(self, project_path: str, extensions: Optional[List[str]] = None) -> Dict[str, List[CodeChunk]]:
        """Индексирует проект - разбивает все файлы на чанки.
        
        Args:
            project_path: Путь к корню проекта
            extensions: Список расширений файлов для индексации (по умолчанию ['.py'])
            
        Returns:
            Словарь {file_path: [chunks]}
        """
        if extensions is None:
            extensions = ['.py']
        
        project_path_obj = Path(project_path)
        if not project_path_obj.exists():
            raise ValueError(f"Проект не найден: {project_path}")
        
        # Проверяем кэш
        cache_key = self._get_cache_key(project_path, extensions)
        cached_index = self._load_cache(cache_key)
        if cached_index:
            return cached_index
        
        # Индексируем все файлы
        index: Dict[str, List[CodeChunk]] = {}
        
        for ext in extensions:
            for file_path in project_path_obj.rglob(f"*{ext}"):
                # Пропускаем скрытые папки и __pycache__
                if any(part.startswith('.') or part == '__pycache__' for part in file_path.parts):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    chunks = self.chunker.chunk_file(str(file_path.relative_to(project_path_obj)), content)
                    
                    if chunks:
                        index[str(file_path.relative_to(project_path_obj))] = chunks
                except Exception as e:
                    # Игнорируем ошибки чтения файлов
                    continue
        
        # Сохраняем в кэш
        self._save_cache(cache_key, index)
        self._index_cache[cache_key] = index
        
        return index
    
    def get_context(
        self,
        query: str,
        project_path: str,
        extensions: Optional[List[str]] = None
    ) -> str:
        """Получает релевантный контекст для запроса из проекта.
        
        Args:
            query: Поисковый запрос
            project_path: Путь к проекту
            extensions: Расширения файлов для поиска
            
        Returns:
            Собранный контекст в пределах лимита токенов
        """
        # Индексируем проект (с кэшированием)
        index = self.index_project(project_path, extensions)
        
        # Собираем все чанки из индекса
        all_chunks: List[CodeChunk] = []
        for chunks in index.values():
            all_chunks.extend(chunks)
        
        if not all_chunks:
            return ""
        
        # Оцениваем релевантность
        scored_chunks = self.scorer.score_chunks(query, all_chunks)
        
        # Собираем контекст
        context = self.composer.compose(scored_chunks, query)
        
        return context
    
    def _get_cache_key(self, project_path: str, extensions: List[str]) -> str:
        """Генерирует ключ кэша для проекта."""
        key_str = f"{project_path}:{sorted(extensions)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_cache(self, cache_key: str) -> Optional[Dict[str, List[CodeChunk]]]:
        """Загружает индекс из кэша."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        
        try:
            # Кэш содержит только метаданные, нужно будет перестроить
            # Для v0.1 просто не используем кэш файлов, только память
            return self._index_cache.get(cache_key)
        except Exception:
            return None
    
    def _save_cache(self, cache_key: str, index: Dict[str, List[CodeChunk]]) -> None:
        """Сохраняет индекс в кэш (для v0.1 - только в память)."""
        self._index_cache[cache_key] = index
