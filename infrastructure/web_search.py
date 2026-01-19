"""Веб-поиск с приоритетом AI-native сервисов.

Порядок приоритета:
1. Tavily API (AI-native, возвращает готовый текст для LLM)
2. DuckDuckGo HTML (приватный, без API ключа)
3. Google (fallback, может блокировать)

Tavily предпочтительнее потому что:
- Возвращает чистый текст, оптимизированный для LLM
- Не требует парсинга HTML
- 1000 бесплатных запросов/месяц
"""
from typing import List, Dict, Optional
from urllib.parse import quote as url_quote
import os

from utils.logger import get_logger
from infrastructure.cache import cached

logger = get_logger()

# Опциональные импорты
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("⚠️ requests недоступен. Веб-поиск будет отключен.")

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    logger.warning("⚠️ beautifulsoup4 недоступен. HTML парсинг будет отключен.")


# === Конфигурация ===

def _get_tavily_api_key() -> Optional[str]:
    """Получает Tavily API ключ из переменных окружения или .env файла."""
    # Сначала проверяем переменную окружения
    api_key = os.environ.get("TAVILY_API_KEY")
    if api_key:
        return api_key
    
    # Пробуем загрузить из .env файла
    try:
        from pathlib import Path
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TAVILY_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    
    return None


def _create_robust_session() -> "requests.Session":
    """Создаёт сессию с retry и настройками."""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


# === Tavily Search (Primary) ===

def tavily_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Выполняет поиск через Tavily API.
    
    Tavily — AI-native поисковик, возвращающий готовый текст для LLM.
    https://tavily.com/ — 1000 бесплатных запросов/месяц.
    
    Args:
        query: Текст поискового запроса
        max_results: Максимальное количество результатов
        timeout: Таймаут запроса в секундах
        
    Returns:
        Список словарей с полями: title, url, snippet (content).
        Пустой список если API недоступен или ошибка.
    """
    if not REQUESTS_AVAILABLE:
        return []
    
    api_key = _get_tavily_api_key()
    if not api_key:
        logger.debug("Tavily API ключ не найден, пропускаем")
        return []
    
    if not query.strip():
        return []
    
    try:
        session = _create_robust_session()
        
        response = session.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",  # basic быстрее, advanced глубже
                "max_results": max_results,
                "include_answer": True,  # Включает готовый ответ от AI
                "include_raw_content": False,  # Экономим трафик
            },
            timeout=timeout
        )
        
        if response.status_code == 401:
            logger.warning("⚠️ Tavily API: неверный ключ")
            return []
        
        if response.status_code == 429:
            logger.warning("⚠️ Tavily API: лимит запросов исчерпан")
            return []
        
        response.raise_for_status()
        data = response.json()
        
        results: List[Dict[str, str]] = []
        
        # Если есть готовый AI-ответ, добавляем его первым
        if data.get("answer"):
            results.append({
                "title": "AI Summary",
                "url": "",
                "snippet": data["answer"]
            })
        
        # Добавляем результаты поиска
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")  # Tavily возвращает content, не snippet
            })
        
        logger.info(f"✅ Tavily вернул {len(results)} результатов")
        return results
        
    except requests.exceptions.Timeout:
        logger.warning("⏱️ Tavily API таймаут")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Tavily API ошибка: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Tavily неожиданная ошибка: {e}", error=e)
        return []


# === DuckDuckGo Search (Secondary) ===

def duckduckgo_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Выполняет поиск через DuckDuckGo HTML версию.
    
    Не требует API ключа, приватный, но нужен парсинг HTML.
    
    Args:
        query: Текст поискового запроса
        max_results: Максимальное количество результатов
        timeout: Таймаут запроса в секундах
        
    Returns:
        Список словарей с полями: title, url, snippet.
    """
    if not REQUESTS_AVAILABLE or not BEAUTIFULSOUP_AVAILABLE:
        return []
    
    if not query.strip():
        return []
    
    try:
        session = _create_robust_session()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        url = f"https://html.duckduckgo.com/html/?q={url_quote(query)}"
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, str]] = []
        
        # DuckDuckGo HTML результаты
        for result_div in soup.find_all("div", class_="result")[:max_results]:
            title_elem = result_div.find("a", class_="result__a")
            snippet_elem = result_div.find("a", class_="result__snippet")
            
            if title_elem:
                title = title_elem.get_text().strip()
                href_attr = title_elem.get("href", "")
                href: str = str(href_attr) if href_attr else ""
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                
                if title and href:
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })
        
        if results:
            logger.info(f"✅ DuckDuckGo вернул {len(results)} результатов")
        return results
        
    except requests.exceptions.Timeout:
        logger.warning("⏱️ DuckDuckGo таймаут")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ DuckDuckGo ошибка: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ DuckDuckGo неожиданная ошибка: {e}", error=e)
        return []


# === Google Search (Fallback) ===

def google_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Выполняет поиск через Google (scraping).
    
    ВНИМАНИЕ: Google активно блокирует scraping. Используйте как последний fallback.
    
    Args:
        query: Текст поискового запроса
        max_results: Максимальное количество результатов
        timeout: Таймаут запроса в секундах
        
    Returns:
        Список словарей с полями: title, url, snippet.
    """
    if not REQUESTS_AVAILABLE or not BEAUTIFULSOUP_AVAILABLE:
        return []
    
    if not query.strip():
        return []
    
    try:
        session = _create_robust_session()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        }
        
        url = f"https://www.google.com/search?q={url_quote(query)}&num={max_results + 2}"
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, str]] = []
        
        for result_div in soup.find_all("div", class_="g")[:max_results]:
            title_elem = result_div.find("h3")
            link_elem = result_div.find("a")
            snippet_elem = (
                result_div.find("div", {"data-sncf": "1"}) or
                result_div.find("div", class_="VwiC3b")
            )
            
            if title_elem and link_elem:
                title = title_elem.get_text().strip()
                href_attr = link_elem.get("href", "")
                href: str = str(href_attr) if href_attr else ""
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                
                # Очищаем URL от Google редиректа
                if href.startswith("/url?q="):
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    q_values = parsed.get("q", [href])
                    href = str(q_values[0]) if q_values else href
                
                if title and href and not href.startswith("/"):
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })
        
        if results:
            logger.info(f"✅ Google вернул {len(results)} результатов")
        return results
        
    except requests.exceptions.SSLError:
        logger.warning("⚠️ Google SSL ошибка (блокировка)")
        return []
    except requests.exceptions.Timeout:
        logger.warning("⏱️ Google таймаут")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Google ошибка: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Google неожиданная ошибка: {e}", error=e)
        return []


# === Unified Search API ===

@cached(ttl=1800)  # Кэш на 30 минут — веб-результаты не меняются часто
def web_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Выполняет веб-поиск с автоматическим fallback и кэшированием.
    
    Порядок приоритета:
    1. Tavily (AI-native, лучшее качество)
    2. DuckDuckGo (приватный, без API)
    3. Google (fallback, может блокировать)
    
    Результаты кэшируются на 30 минут для экономии API запросов.
    
    Args:
        query: Текст поискового запроса
        max_results: Максимальное количество результатов (3-4 по правилам)
        timeout: Таймаут запроса в секундах (10 по правилам)
        
    Returns:
        Список словарей с полями: title, url, snippet.
        Пустой список если все источники недоступны.
    """
    if not query.strip():
        return []
    
    # 1. Пробуем Tavily (лучшее качество)
    results = tavily_search(query, max_results, timeout)
    if results:
        return results
    
    # 2. Пробуем DuckDuckGo (приватный, без API)
    results = duckduckgo_search(query, max_results, timeout)
    if results:
        return results
    
    # 3. Fallback на Google
    results = google_search(query, max_results, timeout)
    if results:
        return results
    
    logger.warning("⚠️ Все источники веб-поиска недоступны")
    return []


# === Backward Compatibility ===

def simple_google_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Обратная совместимость со старым API.
    
    Теперь использует unified web_search с fallback chain.
    """
    return web_search(query, max_results, timeout)
