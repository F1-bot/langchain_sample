"""
Пошук по будівельних джерелах через Tavily.

ЩО ТУТ БУЛО НЕ ТАК
────────────────────────────────────────────────────────────────────
1. Модуль імпортував `from tavily import TavilyClient` — це окремий
   пакет tavily-python, якого немає серед залежностей проєкту. У
   чистому venv після `pip install -r requirements.txt` сервер падав
   ще на старті:

       ModuleNotFoundError: No module named 'tavily'

   Тепер пошук іде через langchain-tavily — той самий пакет, яким
   користується агент. Один клієнт Tavily на проєкт, а не два.

2. Клієнт створювався на рівні модуля (`tavily_service = TavilyService()`),
   тобто при імпорті застосунку. Будь-яка проблема з ключем валила
   увесь сервер, включно з /api/health. Тепер клієнт створюється при
   першому пошуку.
"""
from functools import lru_cache

from app.config import settings

# Галузеві джерела: звужуємо видачу, щоб у відповідь не потрапляли
# випадкові блоги.
CONSTRUCTION_DOMAINS = [
    "construction.com",
    "forconstructionpros.com",
    "constructiondive.com",
    "constructconnect.com",
    "engineering.com",
    "architecturaldigest.com",
    "buildings.com",
]


@lru_cache(maxsize=8)
def _search_tool(max_results: int = 5):
    """
    Створює інструмент пошуку при першому зверненні й кешує його.

    УВАГА на max_results. Його можна задати ЛИШЕ при створенні
    інструмента. Якщо передати його в invoke(), Tavily поверне:

        The parameter 'max_results' can only be set during
        instantiation, not during invocation.

    Тому кешуємо по значенню max_results, а не один інструмент на всіх.
    """
    from langchain_tavily import TavilySearch
    from langchain_tavily._utilities import TavilySearchAPIWrapper

    if not settings.tavily_api_key:
        raise RuntimeError(
            "Немає TAVILY_API_KEY. Безкоштовний ключ — https://app.tavily.com, "
            "покладіть його у .env поряд із requirements.txt."
        )

    return TavilySearch(
        api_wrapper=TavilySearchAPIWrapper(tavily_api_key=settings.tavily_api_key),
        max_results=max_results,
        search_depth="advanced",
        include_domains=CONSTRUCTION_DOMAINS,
    )


def search_payload(query: str) -> dict:
    """
    Аргументи, які передаємо в invoke().

    Винесено окремо, щоб тест міг звірити їх зі схемою інструмента, не
    ходячи в мережу: саме зайвий ключ у цьому словнику й ламав пошук.
    """
    return {"query": f"construction research {query}"}


class TavilyService:
    """Тонка обгортка: решта коду не знає, яким саме пакетом ми шукаємо."""

    def search_construction_research(self, query: str, max_results: int = 5):
        raw = _search_tool(max_results).invoke(search_payload(query))
        # TavilySearch на помилці повертає {"error": ...}, а не кидає виняток.
        if isinstance(raw, dict) and raw.get("error"):
            raise RuntimeError(f"Помилка пошуку Tavily: {raw['error']}")
        return raw

    def format_results(self, raw_results):
        formatted = []
        for result in (raw_results or {}).get("results", []):
            formatted.append({
                "title": result.get("title", "Untitled"),
                "url": result.get("url", ""),
                "content": (result.get("content") or "")[:500],
                "score": result.get("score", 0.0),
            })
        return formatted


tavily_service = TavilyService()   # сам об'єкт легкий, мережі не чіпає
