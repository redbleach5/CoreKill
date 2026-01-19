#!/usr/bin/env python3
"""Скрипт для запуска всего проекта с проверками и мониторингом.

Запускает backend и frontend, проверяет их здоровье и логирует ошибки.
Поддерживает расширение для добавления новых проверок.
"""
import sys
import subprocess
import signal
import time
import shutil
import os
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
    
    def __init__(self) -> None:
        """Инициализация runner."""
        self.project_root = Path(__file__).parent.absolute()
        self.backend_port = 8000
        self.frontend_port = 5173
        self.backend_url = f"http://localhost:{self.backend_port}"
        self.frontend_url = f"http://localhost:{self.frontend_port}"
        
        # Определяем Python из виртуального окружения, если оно есть
        venv_python = self.project_root / ".venv" / "bin" / "python3"
        if venv_python.exists():
            self.python_executable = str(venv_python)
        else:
            self.python_executable = sys.executable
        
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
                    # Обновляем путь к Python
                    self.python_executable = str(venv_path / "bin" / "python3")
                else:
                    self.print_warning("Не удалось создать venv, продолжаю с системным Python")
            except Exception as e:
                self.print_warning(f"Ошибка создания venv: {e}")
        
        # Проверяем Python зависимости используя правильный Python
        pip_cmd = str(Path(self.python_executable).parent / "pip3")
        if not Path(pip_cmd).exists():
            pip_cmd = "pip3"
        
        try:
            # Пробуем импортировать с помощью правильного Python
            result = subprocess.run(
                [self.python_executable, "-c", "import fastapi, uvicorn, ollama, chromadb"],
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
        """Убивает процесс, занимающий указанный порт.
        
        Args:
            port: Номер порта
            
        Returns:
            True если порт освобождён, False если не удалось
        """
        try:
            # Получаем PID текущего процесса и его родителя (чтобы не убить себя)
            current_pid = os.getpid()
            parent_pid = os.getppid()
            safe_pids = {str(current_pid), str(parent_pid)}
            
            # Получаем PID процесса на порту
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                # Порт свободен или lsof не нашёл процесс
                return True
            
            pids = result.stdout.strip().split('\n')
            killed_any = False
            
            for pid in pids:
                pid = pid.strip()
                if pid and pid not in safe_pids:
                    try:
                        subprocess.run(
                            ["kill", "-9", pid],
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
        """Запускает backend сервер."""
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
            
            # Запускаем поток для чтения логов
            threading.Thread(
                target=self._read_backend_logs,
                daemon=True
            ).start()
            
            self.print_success(f"Backend запущен на порту {self.backend_port}")
            return True
        except Exception as e:
            self.print_error(f"Ошибка при запуске backend: {e}")
            return False
    
    def start_frontend(self) -> bool:
        """Запускает frontend сервер."""
        self.print_info("Запускаю frontend...")
        
        frontend_dir = self.project_root / "frontend"
        
        try:
            self.frontend_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Запускаем поток для чтения логов
            threading.Thread(
                target=self._read_frontend_logs,
                daemon=True
            ).start()
            
            self.print_success(f"Frontend запущен на порту {self.frontend_port}")
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
        """Проверяет здоровье backend."""
        endpoints_to_try = ["/health", "/"]  # Пробуем оба endpoint
        
        for i in range(max_retries):
            for endpoint in endpoints_to_try:
                try:
                    response = requests.get(
                        f"{self.backend_url}{endpoint}",
                        timeout=3
                    )
                    if response.status_code == 200:
                        self.print_success("Backend health check пройден")
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
        1. Проверка окружения (команды, версии, зависимости, порты)
        2. Запуск сервисов (backend, frontend)
        3. Проверка здоровья сервисов
        4. Мониторинг ошибок
        
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
        
        # Проверяем Ollama (не критично, но желательно)
        self.check_ollama()
        
        # Проверяем зависимости
        if not self.check_dependencies():
            checks_passed = False
        
        # Проверяем и освобождаем порты
        if not self.check_ports():
            self.print_error("Не удалось освободить порты")
            return 1
        
        if not checks_passed:
            self.print_error("Проверки не пройдены. Исправьте ошибки и попробуйте снова.")
            return 1
        
        # Шаг 2: Запуск сервисов
        self.print_header("🚀 Запуск сервисов")
        
        if not self.start_backend():
            return 1
        
        # Даём backend время на запуск
        time.sleep(2)
        
        if not self.start_frontend():
            self.cleanup()
            return 1
        
        # Шаг 3: Проверка здоровья
        self.print_header("🏥 Проверка здоровья сервисов")
        
        # Даём сервисам больше времени на запуск (особенно backend с инициализацией агентов)
        self.print_info("Ожидание готовности сервисов...")
        time.sleep(5)  # Увеличено время ожидания для инициализации агентов
        
        backend_ok = self.check_backend_health()
        frontend_ok = self.check_frontend_health()
        
        if not backend_ok or not frontend_ok:
            self.print_error("Некоторые сервисы не прошли health check")
            self.cleanup()
            return 1
        
        # Шаг 4: Информация для пользователя
        self.print_header("✅ Проект запущен успешно!")
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}Backend:{Colors.RESET}")
        print(f"  URL: {self.backend_url}")
        print(f"  API Docs: {self.backend_url}/docs")
        print(f"  Health: {self.backend_url}/health")
        
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


def main() -> int:
    """Точка входа."""
    runner = ProjectRunner()
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
