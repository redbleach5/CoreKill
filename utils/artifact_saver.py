"""Утилита для автоматического сохранения артефактов задачи.

Сохраняет код, тесты, рефлексию и метрики в структурированные директории
с timestamp для каждой задачи.

Примеры использования:
    ```python
    from utils.artifact_saver import ArtifactSaver
    
    # Создать экземпляр
    saver = ArtifactSaver(base_output_dir="output")
    
    # Создать директорию для задачи
    task_dir = saver.create_task_directory("Создать калькулятор")
    
    # Сохранить отдельные артефакты
    saver.save_code(code, "calculator.py")
    saver.save_tests(tests, "test_calculator.py")
    saver.save_reflection(reflection_data, "reflection.md")
    saver.save_metrics(metrics, "metrics.json")
    
    # Или сохранить все сразу
    saver.save_all_artifacts(
        task="Создать калькулятор",
        code=code,
        tests=tests,
        reflection_data=reflection_data,
        metrics=metrics
    )
    ```

Зависимости:
    - pathlib: для работы с путями
    - json: для сохранения метрик
    - datetime: для timestamp в именах директорий

Связанные утилиты:
    - cli.py: использует для сохранения результатов
    - backend.workflow_streamer: использует для сохранения артефактов

Примечания:
    - Создаёт директории с timestamp: YYYYMMDD_HHMMSS_task_name
    - Безопасно обрабатывает имена задач (удаляет недопустимые символы)
    - Автоматически создаёт необходимые директории
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class ArtifactSaver:
    """Сохраняет все артефакты задачи в директорию с timestamp."""

    def __init__(self, base_output_dir: str = "output") -> None:
        """Инициализация ArtifactSaver.
        
        Args:
            base_output_dir: Базовая директория для сохранения артефактов
        """
        self.base_output_dir = Path(base_output_dir)
        self.current_task_dir: Optional[Path] = None

    def create_task_directory(self, task: str) -> Path:
        """Создаёт директорию для задачи с timestamp.
        
        Args:
            task: Текст задачи (используется для имени директории)
            
        Returns:
            Path к созданной директории
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Безопасное имя файла из задачи (первые 50 символов)
        safe_task_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in task[:50])
        safe_task_name = safe_task_name.strip()[:50] or "task"
        
        task_dir = self.base_output_dir / f"{timestamp}_{safe_task_name}"
        task_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_task_dir = task_dir
        return task_dir

    def save_code(self, code: str, filename: str = "code.py") -> Path:
        """Сохраняет код в файл.
        
        Args:
            code: Код для сохранения
            filename: Имя файла (по умолчанию code.py)
            
        Returns:
            Path к сохранённому файлу
        """
        if not self.current_task_dir:
            raise ValueError("Сначала создайте директорию задачи через create_task_directory()")
        
        file_path = self.current_task_dir / filename
        file_path.write_text(code, encoding="utf-8")
        return file_path

    def save_tests(self, tests: str, filename: str = "tests.py") -> Path:
        """Сохраняет тесты в файл.
        
        Args:
            tests: Тесты для сохранения
            filename: Имя файла (по умолчанию tests.py)
            
        Returns:
            Path к сохранённому файлу
        """
        if not self.current_task_dir:
            raise ValueError("Сначала создайте директорию задачи через create_task_directory()")
        
        file_path = self.current_task_dir / filename
        file_path.write_text(tests, encoding="utf-8")
        return file_path

    def save_reflection(self, reflection_data: Dict[str, Any], filename: str = "reflection.md") -> Path:
        """Сохраняет рефлексию в Markdown файл.
        
        Args:
            reflection_data: Данные рефлексии (planning_score, analysis, improvements и т.д.)
            filename: Имя файла (по умолчанию reflection.md)
            
        Returns:
            Path к сохранённому файлу
        """
        if not self.current_task_dir:
            raise ValueError("Сначала создайте директорию задачи через create_task_directory()")
        
        file_path = self.current_task_dir / filename
        
        md_content = f"""# Рефлексия и оценка

## Оценки системы

- **Planning:** {reflection_data.get('planning_score', 0):.2f}
- **Research:** {reflection_data.get('research_score', 0):.2f}
- **Testing:** {reflection_data.get('testing_score', 0):.2f}
- **Coding:** {reflection_data.get('coding_score', 0):.2f}
- **Overall:** {reflection_data.get('overall_score', 0):.2f}

## Анализ

{reflection_data.get('analysis', 'Анализ не предоставлен')}

## Предложения по улучшению

{reflection_data.get('improvements', 'Улучшения не предложены')}

## Нужна повторная попытка

{reflection_data.get('should_retry', False)}
"""
        file_path.write_text(md_content, encoding="utf-8")
        return file_path

    def save_metrics(self, metrics: Dict[str, float], filename: str = "metrics.json") -> Path:
        """Сохраняет метрики в JSON файл.
        
        Args:
            metrics: Словарь с метриками (planning, research, testing, coding, overall)
            filename: Имя файла (по умолчанию metrics.json)
            
        Returns:
            Path к сохранённому файлу
        """
        if not self.current_task_dir:
            raise ValueError("Сначала создайте директорию задачи через create_task_directory()")
        
        file_path = self.current_task_dir / filename
        
        metrics_with_timestamp = {
            **metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        file_path.write_text(
            json.dumps(metrics_with_timestamp, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return file_path

    def save_all_artifacts(
        self,
        task: str,
        code: str,
        tests: str,
        reflection_data: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> Path:
        """Сохраняет все артефакты задачи.
        
        Args:
            task: Текст задачи
            code: Сгенерированный код
            tests: Сгенерированные тесты
            reflection_data: Данные рефлексии
            metrics: Метрики
            
        Returns:
            Path к директории с артефактами
        """
        self.create_task_directory(task)
        
        if code:
            self.save_code(code)
        
        if tests:
            self.save_tests(tests)
        
        if reflection_data:
            self.save_reflection(reflection_data)
        
        if metrics:
            self.save_metrics(metrics)
        
        # Сохраняем также задачу в файл
        if self.current_task_dir:
            task_file = self.current_task_dir / "task.txt"
            task_file.write_text(task, encoding="utf-8")
        
        return self.current_task_dir if self.current_task_dir else Path(".")
