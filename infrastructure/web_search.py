"""Минимальный безопасный веб-поиск через Google."""
from typing import List, Dict

from utils.logger import get_logger

logger = get_logger()

# Опциональные импорты для веб-поиска
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("⚠️ requests недоступен. Веб-поиск будет отключен.")

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    logger.warning("⚠️ beautifulsoup4 недоступен. Веб-поиск будет отключен.")


def simple_google_search(query: str, max_results: int = 3, timeout: int = 10) -> List[Dict[str, str]]:
    """Выполняет простой поиск через Google и возвращает результаты.
    
    Args:
        query: Текст поискового запроса
        max_results: Максимальное количество результатов (3-4 по правилам)
        timeout: Таймаут запроса в секундах (10 по правилам)
        
    Returns:
        Список словарей с полями: title, url, snippet.
        Пустой список в случае ошибки или если зависимости недоступны.
    """
    if not REQUESTS_AVAILABLE or not BEAUTIFULSOUP_AVAILABLE:
        logger.debug("Веб-поиск недоступен: отсутствуют необходимые зависимости")
        return []
    
    if not query.strip():
        return []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={max_results + 2}"
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, str]] = []
        
        # Ищем результаты поиска (различные селекторы для надёжности)
        search_results = soup.find_all("div", class_="g")[:max_results]
        
        for result_div in search_results:
            title_elem = result_div.find("h3")
            link_elem = result_div.find("a")
            
            # Ищем snippet различными способами
            snippet_elem = (
                result_div.find("div", {"data-sncf": "1"}) or
                result_div.find("span", class_="st") or
                result_div.find("div", class_="VwiC3b") or
                result_div.find("span", class_="aCOpRe")
            )
            
            if title_elem and link_elem:
                title = title_elem.get_text().strip()
                href = link_elem.get("href", "")
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""
                
                # Очищаем URL (Google иногда добавляет префикс /url?q=)
                if href.startswith("/url?q="):
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = parsed.get("q", [href])[0]
                
                if title and href:
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })
        
        return results[:max_results]
        
    except requests.exceptions.Timeout as e:
        logger.warning(f"⏱️ Таймаут веб-поиска для запроса: {query[:50]}...", error=e)
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка веб-поиска: {e}", error=e)
        return []
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при веб-поиске: {e}", error=e)
        return []
