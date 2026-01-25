#!/usr/bin/env python3
"""Скрипт для запуска всего проекта с проверками и мониторингом.

Запускает backend и frontend, проверяет их здоровье и логирует ошибки.
Поддерживает расширение для добавления новых проверок.
"""
__version__ = "1.0.0"

import sys
import subprocess
import signal
import time
import shutil
import os
import queue
from pathlib import Path
from typing import Optional, List, Dict
import threading
import requests
from datetime import datetime


class Colors:
    """ANSI цвета для терминала."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class ProjectRunner:
    """Класс для запуска и мониторинга проекта.
    
    Поддерживает расширение через добавление новых методов проверки:
    - Добавьте новые методы check_* для дополнительных проверок
    - Добавьте новые методы start_* для запуска дополнительных сервисов
    - Переопределите run() для кастомизации последовательности запуска
    """
    
    def __init__(
        self,
        backend_port: int = 8000,
        frontend_port: int = 5173,
        no_backend: bool = False,
        no_frontend: bool = False,
        skip_checks: bool = False,
        require_ollama: bool = False
    ) -> None:
        """Инициализация runner.
        
        Args:
            backend_port: Порт для backend сервера (по умолчанию 8000)
            frontend_port: Порт для frontend сервера (по умолчанию 5173)
            no_backend: Не запускать backend
            no_frontend: Не запускать frontend
            skip_checks: Пропустить проверки (не рекомендуется)
            require_ollama: Требовать наличие Ollama (иначе ошибка)
        """
        self.no_backend = no_backend
        self.no_frontend = no_frontend
        self.skip_checks = skip_checks
        self.require_ollama = require_ollama
        self.project_root = Path(__file__).parent.absolute()
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.backend_url = f"http://localhost:{self.backend_port}"
        self.frontend_url = f"http://localhost:{self.frontend_port}"
        
        # ИСПРАВЛЕНИЕ: Кросс-платформенные пути к виртуальному окружению
        self.is_windows = sys.platform == "win32"
        if self.is_windows:
            venv_python = self.project_root / ".venv" / "Scripts" / "python.exe"
            venv_pip = self.project_root / ".venv" / "Scripts" / "pip.exe"
        else:
            venv_python = self.project_root / ".venv" / "bin" / "python3"
            venv_pip = self.project_root / ".venv" / "bin" / "pip3"
        
        if venv_python.exists():
            self.python_executable = str(venv_python)
            self.pip_executable = str(venv_pip) if venv_pip.exists() else "pip3"
        else:
            self.python_executable = sys.executable
            self.pip_executable = "pip3" if not self.is_windows else "pip"
        
        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        
        self.backend_log: List[str] = []
        self.frontend_log: List[str] = []
        
        self.running = True
        self.errors_detected = False
        
        # Регистрируем обработчик сигналов для корректного завершения
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Обработчик сигналов для корректного завершения."""
        print(f"\n{Colors.YELLOW}Получен сигнал завершения...{Colors.RESET}")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def print_header(self, text: str) -> None:
        """Выводит заголовок."""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}{text.center(70)}{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")
    
    def print_success(self, text: str) -> None:
        """Выводит успешное сообщение."""
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")
    
    def print_error(self, text: str) -> None:
        """Выводит сообщение об ошибке."""
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")
        self.errors_detected = True
    
    def print_warning(self, text: str) -> None:
        """Выводит предупреждение."""
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")
    
    def print_info(self, text: str) -> None:
        """Выводит информационное сообщение."""
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")
    
    def check_command(self, command: str, name: str) -> bool:
        """Проверяет наличие команды в PATH."""
        if shutil.which(command) is None:
            self.print_error(f"{name} не найден в PATH. Установите {name}.")
            return False
        return True
    
    def check_python_version(self) -> bool:
        """Проверяет версию Python."""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 12):
            self.print_error(
                f"Требуется Python 3.12+, установлен {version.major}.{version.minor}.{version.micro}"
            )
            return False
        self.print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    def check_node_version(self) -> bool:
        """Проверяет версию Node.js."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.print_error("Не удалось определить версию Node.js")
                return False
            
            version_str = result.stdout.strip().replace("v", "")
            major = int(version_str.split(".")[0])
            if major < 18:
                self.print_error(f"Требуется Node.js 18+, установлен {version_str}")
                return False
            
            self.print_success(f"Node.js {version_str}")
            return True
        except Exception as e:
            self.print_error(f"Ошибка при проверке Node.js: {e}")
            return False
    
    def check_ollama(self) -> bool:
        """Проверяет доступность Ollama."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                self.print_warning("Ollama не отвечает. Убедитесь что Ollama запущен.")
                return False
            
            self.print_success("Ollama доступен")
            return True
        except FileNotFoundError:
            self.print_warning("Ollama не найден. Установите Ollama для работы с моделями.")
            return False
        except Exception as e:
            self.print_warning(f"Ошибка при проверке Ollama: {e}")
            return False
    
    def check_dependencies(self) -> bool:
        """Проверяет и устанавливает зависимости."""
            # Создаём виртуальное окружение если его нет
        venv_path = self.project_root / ".venv"
        if venv_path.exists():
            self.print_info(f"Виртуальное окружение найдено: {venv_path}")
        else:
            self.print_warning("Виртуальное окружение не найдено, создаю...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_path)],
                    timeout=60
                )
                if result.returncode == 0:
                    self.print_success("Виртуальное окружение создано: .venv")
                    # ИСПРАВЛЕНИЕ: Обновляем путь к Python с учётом платформы
                    if self.is_windows:
                        self.python_executable = str(venv_path / "Scripts" / "python.exe")
                        self.pip_executable = str(venv_path / "Scripts" / "pip.exe")
                    else:
                        self.python_executable = str(venv_path / "bin" / "python3")
                        self.pip_executable = str(venv_path / "bin" / "pip3")
                else:
                    self.print_warning("Не удалось создать venv, продолжаю с системным Python")
            except Exception as e:
                self.print_warning(f"Ошибка создания venv: {e}")
        
        # ИСПРАВЛЕНИЕ: Используем правильный pip для платформы
        pip_cmd = self.pip_executable
        
        try:
            # Пробуем импортировать с помощью правильного Python (включая langgraph)
            result = subprocess.run(
                [self.python_executable, "-c", "import fastapi, uvicorn, ollama, chromadb, langgraph"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.print_success("Python зависимости установлены")
            else:
                self.print_warning("Python зависимости не установлены, устанавливаю...")
                install_result = subprocess.run(
                    [pip_cmd, "install", "-r", "requirements.txt"],
                    cwd=self.project_root,
                    timeout=300
                )
                if install_result.returncode != 0:
                    self.print_error("Не удалось установить Python зависимости")
                    self.print_info(f"Попробуйте вручную: {pip_cmd} install -r requirements.txt")
                    return False
                self.print_success("Python зависимости установлены")
        except subprocess.TimeoutExpired:
            self.print_error("Таймаут при установке зависимостей")
            return False
        except Exception as e:
            self.print_error(f"Ошибка при проверке зависимостей: {e}")
            self.print_info(f"Запустите вручную: {pip_cmd} install -r requirements.txt")
            return False
        
        # Проверяем Node.js зависимости
        frontend_dir = self.project_root / "frontend"
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            self.print_warning("Node.js зависимости не установлены, устанавливаю...")
            try:
                install_result = subprocess.run(
                    ["npm", "install"],
                    cwd=frontend_dir,
                    timeout=300
                )
                if install_result.returncode != 0:
                    self.print_error("Не удалось установить Node.js зависимости")
                    self.print_info("Попробуйте вручную: cd frontend && npm install")
                    return False
            except subprocess.TimeoutExpired:
                self.print_error("Таймаут при установке Node.js зависимостей")
                return False
            except Exception as e:
                self.print_error(f"Ошибка установки Node.js зависимостей: {e}")
                return False
        
        self.print_success("Node.js зависимости установлены")
        return True
    
    def _kill_process_on_port(self, port: int) -> bool:
        """Убивает процесс, занимающий указанный порт (кросс-платформенно).
        
        Args:
            port: Номер порта
            
        Returns:
            True если порт освобождён, False если не удалось
        """
        try:
            # Получаем PID текущего процесса и его родителя (чтобы не убить себя)
            current_pid = os.getpid()
            parent_pid = os.getppid()
            safe_pids = {current_pid, parent_pid}
            
            # ИСПРАВЛЕНИЕ: Кросс-платформенное получение PID процесса на порту
            pids = []
            
            if self.is_windows:
                # Windows: используем netstat для поиска PID
                try:
                    result = subprocess.run(
                        ["netstat", "-ano"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if f":{port}" in line and "LISTENING" in line:
                                parts = line.split()
                                if parts:
                                    pid = parts[-1]
                                    try:
                                        pid_int = int(pid)
                                        if pid_int not in safe_pids:
                                            pids.append(pid_int)
                                    except ValueError:
                                        pass
                except FileNotFoundError:
                    # Пробуем использовать psutil если доступен
                    try:
                        import psutil
                        for conn in psutil.net_connections(kind='inet'):
                            if conn.laddr.port == port and conn.pid and conn.pid not in safe_pids:
                                pids.append(conn.pid)
                    except ImportError:
                        self.print_warning("psutil не установлен, не могу освободить порт на Windows")
                        return False
            else:
                # Unix/Linux/macOS: используем lsof
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        for pid_str in result.stdout.strip().split('\n'):
                            try:
                                pid_int = int(pid_str.strip())
                                if pid_int not in safe_pids:
                                    pids.append(pid_int)
                            except ValueError:
                                pass
                except FileNotFoundError:
                    # Пробуем использовать psutil если доступен
                    try:
                        import psutil
                        for conn in psutil.net_connections(kind='inet'):
                            if conn.laddr.port == port and conn.pid and conn.pid not in safe_pids:
                                pids.append(conn.pid)
                    except ImportError:
                        self.print_warning("lsof не найден, не могу освободить порт")
                        return False
            
            if not pids:
                # Порт свободен
                return True
            
            # Убиваем процессы
            killed_any = False
            for pid in pids:
                try:
                    if self.is_windows:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            capture_output=True,
                            timeout=5
                        )
                    else:
                        subprocess.run(
                            ["kill", "-9", str(pid)],
                            capture_output=True,
                            timeout=5
                        )
                    self.print_info(f"Процесс {pid} на порту {port} остановлен")
                    killed_any = True
                except Exception:
                    pass
            
            # Даём время на освобождение порта только если что-то убили
            if killed_any:
                time.sleep(1)
            return True
            
        except Exception as e:
            self.print_warning(f"Не удалось освободить порт {port}: {e}")
            return False
    
    def check_python_syntax(self) -> bool:
        """Проверяет синтаксис всех Python файлов в проекте.
        
        Использует py_compile для быстрой проверки синтаксиса без импорта модулей.
        
        Returns:
            True если синтаксис корректен, False если найдены ошибки
        """
        import py_compile
        import ast
        
        self.print_info("Проверка синтаксиса Python файлов...")
        
        # Директории для проверки
        check_dirs = [
            "agents",
            "backend",
            "infrastructure",
            "utils",
            "scripts"
        ]
        
        errors = []
        checked_files = 0
        
        for dir_name in check_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            # Находим все .py файлы
            for py_file in dir_path.rglob("*.py"):
                # Пропускаем __pycache__ и .venv
                if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                    continue
                
                checked_files += 1
                try:
                    # Проверяем синтаксис через py_compile
                    py_compile.compile(str(py_file), doraise=True)
                    
                    # Дополнительная проверка через AST (более строгая)
                    with open(py_file, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source, filename=str(py_file))
                    
                except py_compile.PyCompileError as e:
                    errors.append(f"{py_file.relative_to(self.project_root)}: {e.msg}")
                except SyntaxError as e:
                    errors.append(f"{py_file.relative_to(self.project_root)}:{e.lineno}: {e.msg}")
                except Exception as e:
                    errors.append(f"{py_file.relative_to(self.project_root)}: {e}")
        
        # Проверяем основной run.py
        try:
            py_compile.compile(str(self.project_root / "run.py"), doraise=True)
            with open(self.project_root / "run.py", "r", encoding="utf-8") as f:
                ast.parse(f.read(), filename="run.py")
            checked_files += 1
        except Exception as e:
            errors.append(f"run.py: {e}")
        
        if errors:
            self.print_error(f"Найдено {len(errors)} синтаксических ошибок в Python файлах:")
            for error in errors[:10]:  # Показываем первые 10 ошибок
                self.print_error(f"  ❌ {error}")
            if len(errors) > 10:
                self.print_error(f"  ... и ещё {len(errors) - 10} ошибок")
            return False
        
        self.print_success(f"Синтаксис Python корректен ({checked_files} файлов проверено)")
        return True
    
    def check_typescript_syntax(self) -> bool:
        """Проверяет синтаксис TypeScript файлов в frontend.
        
        Использует tsc --noEmit для проверки без компиляции.
        
        Returns:
            True если синтаксис корректен, False если найдены ошибки
        """
        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            self.print_warning("Директория frontend не найдена, пропускаю проверку TypeScript")
            return True
        
        self.print_info("Проверка синтаксиса TypeScript файлов...")
        
        try:
            # ИСПРАВЛЕНИЕ: Пробуем npm run type-check, если нет - используем npx tsc напрямую
            try:
                result = subprocess.run(
                    ["npm", "run", "type-check"],
                    cwd=frontend_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            except FileNotFoundError:
                # Если npm не найден, пробуем напрямую через npx
                self.print_info("npm не найден, пробую npx tsc --noEmit...")
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    cwd=frontend_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            
            if result.returncode == 0:
                self.print_success("Синтаксис TypeScript корректен")
                return True
            else:
                # Показываем ошибки
                error_output = result.stderr or result.stdout
                error_lines = error_output.split("\n")
                
                # Фильтруем только ошибки (не предупреждения)
                errors = [line for line in error_lines if "error TS" in line]
                
                if errors:
                    self.print_error(f"Найдено {len(errors)} ошибок TypeScript:")
                    for error in errors[:10]:  # Показываем первые 10 ошибок
                        self.print_error(f"  ❌ {error}")
                    if len(errors) > 10:
                        self.print_error(f"  ... и ещё {len(errors) - 10} ошибок")
                else:
                    # Если только предупреждения, показываем их как warning
                    warnings = [line for line in error_lines if "warning" in line.lower()]
                    if warnings:
                        self.print_warning(f"Найдено {len(warnings)} предупреждений TypeScript (не критично)")
                        return True
                    else:
                        self.print_error("Ошибка проверки TypeScript (см. вывод выше)")
                
                return False
                
        except FileNotFoundError:
            self.print_warning("npm не найден, пропускаю проверку TypeScript")
            return True
        except subprocess.TimeoutExpired:
            self.print_error("Таймаут при проверке TypeScript (более 60 секунд)")
            return False
        except Exception as e:
            self.print_warning(f"Ошибка при проверке TypeScript: {e}")
            # Не критично, продолжаем
            return True
    
    def check_ports(self) -> bool:
        """Проверяет и при необходимости освобождает порты."""
        import socket
        
        ports_ok = True
        
        # Проверяем и освобождаем backend порт
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('localhost', self.backend_port))
            if result == 0:
                self.print_warning(f"Порт {self.backend_port} занят, освобождаю...")
                if self._kill_process_on_port(self.backend_port):
                    self.print_success(f"Порт {self.backend_port} освобождён")
                else:
                    ports_ok = False
        except Exception:
            pass
        finally:
            sock.close()
        
        # Проверяем и освобождаем frontend порт
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex(('localhost', self.frontend_port))
            if result == 0:
                self.print_warning(f"Порт {self.frontend_port} занят, освобождаю...")
                if self._kill_process_on_port(self.frontend_port):
                    self.print_success(f"Порт {self.frontend_port} освобождён")
                else:
                    ports_ok = False
        except Exception:
            pass
        finally:
            sock.close()
        
        if ports_ok:
            self.print_success("Порты готовы")
        
        return ports_ok
    
    def start_backend(self) -> bool:
        """Запускает backend сервер с проверкой что процесс запустился.
        
        Returns:
            True если backend успешно запущен, False в случае ошибки
        """
        self.print_info("Запускаю backend...")
        
        try:
            self.backend_process = subprocess.Popen(
                [
                    self.python_executable, "-m", "uvicorn",
                    "backend.api:app",
                    "--reload",
                    "--reload-exclude", "output/*",
                    "--reload-exclude", "logs/*",
                    "--reload-exclude", "temp/*",
                    "--reload-exclude", "*.jsonl",
                    "--port", str(self.backend_port),
                    "--host", "0.0.0.0"
                ],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Проверяем что процесс запустился (не завершился сразу)
            time.sleep(0.5)  # Даём время на запуск
            if self.backend_process.poll() is not None:
                # Процесс уже завершился - ошибка
                error_output = ""
                try:
                    if self.backend_process.stdout:
                        # Пробуем прочитать доступный вывод (неблокирующий способ)
                        # Используем threading для кроссплатформенности
                        output_queue: queue.Queue[str] = queue.Queue()
                        
                        def read_output():
                            try:
                                for line in iter(self.backend_process.stdout.readline, ''):
                                    if line:
                                        output_queue.put(line)
                            except Exception:
                                pass
                        
                        reader_thread = threading.Thread(target=read_output, daemon=True)
                        reader_thread.start()
                        reader_thread.join(timeout=0.2)  # Ждём максимум 200ms
                        
                        # Собираем доступный вывод
                        while not output_queue.empty():
                            error_output += output_queue.get()
                except Exception:
                    pass
                
                if error_output:
                    error_preview = error_output[:500].replace('\n', ' ')
                    self.print_error(
                        f"Backend процесс завершился сразу после запуска: {error_preview}"
                    )
                else:
                    self.print_error(
                        f"Backend процесс завершился сразу после запуска "
                        f"(код возврата: {self.backend_process.returncode})"
                    )
                return False
            
            # Запускаем поток для чтения логов
            threading.Thread(
                target=self._read_backend_logs,
                daemon=True
            ).start()
            
            self.print_success(f"Backend процесс запущен на порту {self.backend_port}")
            return True
        except Exception as e:
            self.print_error(f"Ошибка при запуске backend: {e}")
            return False
    
    def start_frontend(self) -> bool:
        """Запускает frontend сервер с проверкой что процесс запустился.
        
        Returns:
            True если frontend успешно запущен, False в случае ошибки
        """
        self.print_info("Запускаю frontend...")
        
        frontend_dir = self.project_root / "frontend"
        
        # Проверяем что node_modules установлены
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            self.print_error("node_modules не найдены. Запустите: cd frontend && npm install")
            return False
        
        try:
            # Используем переменные окружения для указания порта Vite и backend URL
            env = os.environ.copy()
            env["PORT"] = str(self.frontend_port)
            env["VITE_BACKEND_URL"] = self.backend_url
            
            self.frontend_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            
            # Проверяем что процесс запустился
            time.sleep(0.5)  # Даём время на запуск
            if self.frontend_process.poll() is not None:
                # Процесс уже завершился - ошибка
                error_output = ""
                try:
                    if self.frontend_process.stdout:
                        # Пробуем прочитать доступный вывод (неблокирующий способ)
                        output_queue: queue.Queue[str] = queue.Queue()
                        
                        def read_output():
                            try:
                                for line in iter(self.frontend_process.stdout.readline, ''):
                                    if line:
                                        output_queue.put(line)
                            except Exception:
                                pass
                        
                        reader_thread = threading.Thread(target=read_output, daemon=True)
                        reader_thread.start()
                        reader_thread.join(timeout=0.2)  # Ждём максимум 200ms
                        
                        # Собираем доступный вывод
                        while not output_queue.empty():
                            error_output += output_queue.get()
                except Exception:
                    pass
                
                if error_output:
                    error_preview = error_output[:500].replace('\n', ' ')
                    self.print_error(
                        f"Frontend процесс завершился сразу после запуска: {error_preview}"
                    )
                else:
                    self.print_error(
                        f"Frontend процесс завершился сразу после запуска "
                        f"(код возврата: {self.frontend_process.returncode})"
                    )
                return False
            
            # Запускаем поток для чтения логов
            threading.Thread(
                target=self._read_frontend_logs,
                daemon=True
            ).start()
            
            self.print_success(f"Frontend процесс запущен на порту {self.frontend_port}")
            return True
        except Exception as e:
            self.print_error(f"Ошибка при запуске frontend: {e}")
            return False
    
    def _read_backend_logs(self) -> None:
        """Читает логи backend."""
        if not self.backend_process or not self.backend_process.stdout:
            return
        
        for line in iter(self.backend_process.stdout.readline, ''):
            if not line:
                break
            
            line = line.strip()
            if line:
                self.backend_log.append(line)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Проверяем на ошибки
                if any(keyword in line.lower() for keyword in ['error', 'exception', 'traceback', 'failed']):
                    self.print_error(f"[Backend {timestamp}] {line}")
                elif 'uvicorn running' in line.lower() or 'application startup complete' in line.lower():
                    self.print_success(f"[Backend {timestamp}] Сервер готов")
                else:
                    print(f"{Colors.BLUE}[Backend {timestamp}]{Colors.RESET} {line}")
    
    def _read_frontend_logs(self) -> None:
        """Читает логи frontend."""
        if not self.frontend_process or not self.frontend_process.stdout:
            return
        
        for line in iter(self.frontend_process.stdout.readline, ''):
            if not line:
                break
            
            line = line.strip()
            if line:
                self.frontend_log.append(line)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Проверяем на ошибки
                if any(keyword in line.lower() for keyword in ['error', 'failed', 'cannot', 'unable']):
                    self.print_error(f"[Frontend {timestamp}] {line}")
                elif 'localhost' in line.lower() and '5173' in line:
                    self.print_success(f"[Frontend {timestamp}] Сервер готов")
                else:
                    print(f"{Colors.CYAN}[Frontend {timestamp}]{Colors.RESET} {line}")
    
    def check_backend_health(self, max_retries: int = 15) -> bool:
        """Проверяет здоровье backend с валидацией статуса.
        
        Проверяет не только HTTP доступность, но и статус сервисов через /health endpoint.
        
        Args:
            max_retries: Максимальное количество попыток
            
        Returns:
            True если backend здоров и готов к работе
        """
        endpoints_to_try = ["/health", "/"]  # Пробуем оба endpoint
        
        for i in range(max_retries):
            for endpoint in endpoints_to_try:
                try:
                    response = requests.get(
                        f"{self.backend_url}{endpoint}",
                        timeout=3
                    )
                    if response.status_code == 200:
                        # Если это /health endpoint, проверяем статус сервисов
                        if endpoint == "/health":
                            try:
                                health_data = response.json()
                                status = health_data.get("status", "unknown")
                                services = health_data.get("services", {})
                                
                                if status == "ok":
                                    self.print_success("Backend health check пройден (все сервисы OK)")
                                    return True
                                elif status == "degraded":
                                    # Backend работает, но некоторые сервисы недоступны
                                    degraded_services = [
                                        name for name, svc_status in services.items()
                                        if svc_status not in ["ok", "unknown"]
                                    ]
                                    if degraded_services:
                                        self.print_warning(
                                            f"Backend работает в degraded режиме. "
                                            f"Проблемы с: {', '.join(degraded_services)}"
                                        )
                                    else:
                                        self.print_warning("Backend работает в degraded режиме")
                                    # Разрешаем запуск, но предупреждаем
                                    return True
                                else:
                                    self.print_error(f"Backend health check не пройден: статус {status}")
                                    return False
                            except (ValueError, KeyError) as e:
                                # Не удалось распарсить JSON, но HTTP 200 - считаем OK
                                self.print_warning(f"Не удалось распарсить health check ответ: {e}")
                                self.print_success("Backend доступен (HTTP 200)")
                                return True
                        else:
                            # Для корневого endpoint просто проверяем доступность
                            self.print_success("Backend доступен")
                            return True
                except requests.exceptions.ConnectionError:
                    # Продолжаем попытки
                    break
                except requests.exceptions.Timeout:
                    # Продолжаем попытки
                    break
                except requests.exceptions.RequestException:
                    # Продолжаем попытки
                    break
            
            if i < max_retries - 1:
                time.sleep(1)
            else:
                # Последняя попытка - выводим детальную ошибку
                try:
                    response = requests.get(
                        f"{self.backend_url}/health",
                        timeout=3
                    )
                    if response.status_code == 200:
                        try:
                            health_data = response.json()
                            status = health_data.get("status", "unknown")
                            self.print_error(f"Backend health check не пройден: статус {status}")
                        except (ValueError, KeyError):
                            self.print_error(f"Backend health check не пройден: статус {response.status_code}")
                    else:
                        self.print_error(f"Backend health check не пройден: статус {response.status_code}")
                except requests.exceptions.ConnectionError as e:
                    self.print_error(f"Backend health check не пройден: не удалось подключиться")
                    self.print_info(f"Проверьте, что backend запущен на {self.backend_url}")
                except requests.exceptions.Timeout:
                    self.print_error("Backend health check не пройден: таймаут")
                except requests.exceptions.RequestException as e:
                    self.print_error(f"Backend health check не пройден: {e}")
                return False
        
        return False
    
    def _wait_for_backend_ready(self, max_wait: int = 30) -> bool:
        """Ожидает готовности backend с адаптивным polling.
        
        Использует экспоненциальный backoff для оптимизации времени ожидания.
        
        Args:
            max_wait: Максимальное время ожидания в секундах
            
        Returns:
            True если backend готов, False если превышено время ожидания
        """
        wait_time = 1  # Начинаем с 1 секунды
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                response = requests.get(f"{self.backend_url}/health", timeout=2)
                if response.status_code == 200:
                    try:
                        health_data = response.json()
                        status = health_data.get("status", "unknown")
                        if status in ["ok", "degraded"]:
                            if elapsed > 0:
                                self.print_success(f"Backend готов через {elapsed:.1f}с")
                            return True
                    except (ValueError, KeyError):
                        # Если не удалось распарсить, но HTTP 200 - считаем готовым
                        if elapsed > 0:
                            self.print_success(f"Backend доступен через {elapsed:.1f}с")
                        return True
            except requests.exceptions.RequestException:
                # Backend ещё не готов, продолжаем ожидание
                pass
            
            time.sleep(wait_time)
            elapsed += wait_time
            # Экспоненциальный backoff: 1s -> 1.5s -> 2.25s -> ... (макс 5s)
            wait_time = min(wait_time * 1.5, 5)
        
        # Последняя попытка с детальной проверкой
        return self.check_backend_health(max_retries=3)
    
    def check_frontend_health(self, max_retries: int = 15) -> bool:
        """Проверяет здоровье frontend."""
        for i in range(max_retries):
            try:
                response = requests.get(
                    self.frontend_url,
                    timeout=3
                )
                if response.status_code == 200:
                    self.print_success("Frontend health check пройден")
                    return True
            except requests.exceptions.ConnectionError as e:
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    self.print_error(f"Frontend health check не пройден: не удалось подключиться ({e})")
                    return False
            except requests.exceptions.Timeout:
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    self.print_error("Frontend health check не пройден: таймаут")
                    return False
            except requests.exceptions.RequestException as e:
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    self.print_error(f"Frontend health check не пройден: {e}")
                    return False
        
        return False
    
    def monitor_errors(self) -> None:
        """Мониторит ошибки в логах."""
        while self.running:
            time.sleep(5)
            
            # Проверяем процессы
            if self.backend_process and self.backend_process.poll() is not None:
                self.print_error("Backend процесс завершился неожиданно")
                self.running = False
                break
            
            if self.frontend_process and self.frontend_process.poll() is not None:
                self.print_error("Frontend процесс завершился неожиданно")
                self.running = False
                break
    
    def cleanup(self) -> None:
        """Корректно завершает все процессы."""
        self.print_info("Завершаю процессы...")
        
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
                self.print_success("Backend остановлен")
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
                self.print_warning("Backend принудительно остановлен")
            except Exception as e:
                self.print_error(f"Ошибка при остановке backend: {e}")
        
        if self.frontend_process:
            try:
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
                self.print_success("Frontend остановлен")
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()
                self.print_warning("Frontend принудительно остановлен")
            except Exception as e:
                self.print_error(f"Ошибка при остановке frontend: {e}")
    
    def run(self) -> int:
        """Запускает весь проект.
        
        Последовательность:
        1. Проверка окружения (команды, версии, зависимости)
        2. Проверка синтаксиса (Python и TypeScript файлы)
        3. Проверка и освобождение портов
        4. Запуск сервисов (backend, frontend)
        5. Проверка здоровья сервисов
        6. Мониторинг ошибок
        
        Для расширения добавьте новые проверки в соответствующие секции.
        
        Returns:
            Код возврата: 0 - успех, 1 - ошибка
        """
        self.print_header("🚀 Cursor Killer - Запуск проекта")
        
        # Шаг 1: Проверка окружения
        self.print_header("📋 Проверка окружения")
        
        checks_passed = True
        
        # Проверяем команды
        if not self.check_command("python3", "Python 3"):
            checks_passed = False
        if not self.check_command("node", "Node.js"):
            checks_passed = False
        if not self.check_command("npm", "npm"):
            checks_passed = False
        
        # Проверяем версии
        if not self.check_python_version():
            checks_passed = False
        if not self.check_node_version():
            checks_passed = False
        
        # Проверяем Ollama
        ollama_ok = self.check_ollama()
        if self.require_ollama and not ollama_ok:
            self.print_error("Ollama требуется, но недоступен. Используйте --require-ollama для строгой проверки.")
            checks_passed = False
        
        # Проверяем зависимости
        if not self.check_dependencies():
            checks_passed = False
        
        # Проверяем синтаксис кода (если не пропущено)
        if not self.skip_checks:
            self.print_header("🔍 Проверка синтаксиса")
            if not self.check_python_syntax():
                checks_passed = False
            if not self.check_typescript_syntax():
                checks_passed = False
        else:
            self.print_warning("Проверка синтаксиса пропущена (--skip-checks)")
        
        # Проверяем и освобождаем порты
        if not self.check_ports():
            self.print_error("Не удалось освободить порты")
            return 1
        
        if not checks_passed:
            self.print_error("Проверки не пройдены. Исправьте ошибки и попробуйте снова.")
            return 1
        
        # Шаг 2: Запуск сервисов
        self.print_header("🚀 Запуск сервисов")
        
        if not self.no_backend:
            if not self.start_backend():
                return 1
            # Даём backend время на запуск
            time.sleep(2)
        else:
            self.print_info("Backend пропущен (--no-backend)")
        
        if not self.no_frontend:
            if not self.start_frontend():
                self.cleanup()
                return 1
        else:
            self.print_info("Frontend пропущен (--no-frontend)")
        
        # Шаг 3: Проверка здоровья
        self.print_header("🏥 Проверка здоровья сервисов")
        
        backend_ok = True
        frontend_ok = True
        
        if not self.no_backend:
            # Адаптивное ожидание готовности backend с экспоненциальным backoff
            self.print_info("Ожидание готовности backend...")
            backend_ok = self._wait_for_backend_ready(max_wait=30)
            
            if not backend_ok:
                self.print_error("Backend не готов после ожидания")
                self.cleanup()
                return 1
        
        if not self.no_frontend:
            # Проверяем frontend (обычно быстрее запускается)
            self.print_info("Ожидание готовности frontend...")
            frontend_ok = self.check_frontend_health()
            
            if not frontend_ok:
                self.print_error("Frontend не прошёл health check")
                self.cleanup()
                return 1
        
        # Шаг 4: Информация для пользователя
        self.print_header("✅ Проект запущен успешно!")
        
        if not self.no_backend:
            print(f"\n{Colors.GREEN}{Colors.BOLD}Backend:{Colors.RESET}")
            print(f"  URL: {self.backend_url}")
            print(f"  API Docs: {self.backend_url}/docs")
            print(f"  Health: {self.backend_url}/health")
        
        if not self.no_frontend:
            print(f"\n{Colors.CYAN}{Colors.BOLD}Frontend:{Colors.RESET}")
            print(f"  URL: {self.frontend_url}")
        
        print(f"\n{Colors.YELLOW}Нажмите Ctrl+C для остановки{Colors.RESET}\n")
        
        # Шаг 5: Мониторинг
        try:
            self.monitor_errors()
        except KeyboardInterrupt:
            pass
        
        self.cleanup()
        
        if self.errors_detected:
            return 1
        
        return 0


def parse_args() -> tuple[int, int, bool, bool, bool, bool]:
    """Парсит аргументы командной строки.
    
    Returns:
        tuple[backend_port, frontend_port, no_backend, no_frontend, skip_checks, require_ollama]
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Запускает Cursor Killer проект с проверками и мониторингом",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python run.py --backend-port 8080 # Изменить порт backend
  python run.py --frontend-port 3000 # Изменить порт frontend
  python run.py --backend-port 8080 --frontend-port 3000 # Оба порта
  python run.py --no-frontend # Запустить только backend
  python run.py --no-backend # Запустить только frontend
  python run.py --skip-checks # Пропустить проверки (не рекомендуется)
  python run.py --require-ollama # Требовать наличие Ollama
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Порт для backend сервера (по умолчанию: 8000)"
    )
    
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Порт для frontend сервера (по умолчанию: 5173)"
    )
    
    parser.add_argument(
        "--no-backend",
        action="store_true",
        help="Не запускать backend сервер"
    )
    
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Не запускать frontend сервер"
    )
    
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Пропустить проверки синтаксиса (не рекомендуется)"
    )
    
    parser.add_argument(
        "--require-ollama",
        action="store_true",
        help="Требовать наличие Ollama (иначе ошибка)"
    )
    
    args = parser.parse_args()
    
    # Валидация портов
    if not (1024 <= args.backend_port <= 65535):
        print(f"❌ Ошибка: backend-port должен быть в диапазоне 1024-65535")
        sys.exit(1)
    
    if not (1024 <= args.frontend_port <= 65535):
        print(f"❌ Ошибка: frontend-port должен быть в диапазоне 1024-65535")
        sys.exit(1)
    
    if args.backend_port == args.frontend_port:
        print(f"❌ Ошибка: backend и frontend не могут использовать один порт")
        sys.exit(1)
    
    if args.no_backend and args.no_frontend:
        print(f"❌ Ошибка: нельзя отключить и backend, и frontend одновременно")
        sys.exit(1)
    
    return (
        args.backend_port,
        args.frontend_port,
        args.no_backend,
        args.no_frontend,
        args.skip_checks,
        args.require_ollama
    )


def main() -> int:
    """Точка входа."""
    backend_port, frontend_port, no_backend, no_frontend, skip_checks, require_ollama = parse_args()
    runner = ProjectRunner(
        backend_port=backend_port,
        frontend_port=frontend_port,
        no_backend=no_backend,
        no_frontend=no_frontend,
        skip_checks=skip_checks,
        require_ollama=require_ollama
    )
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
