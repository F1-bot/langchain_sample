"""
Агент для вкладки «AI Agent»: чат із пам'яттю та веб-пошуком.
"""
from app.config import load_google_llm, settings


def create_agent_executor():
    """
    Створює ReAct-агента з пошуком і пам'яттю розмови.

    Про create_agent. Раніше тут стояв create_react_agent із
    langgraph.prebuilt. Він ще працює, але LangGraph друкує на нього
    попередження:

        LangGraphDeprecatedSinceV10: create_react_agent has been moved
        to `langchain.agents`. Please update your import to
        `from langchain.agents import create_agent`.
        Deprecated in LangGraph V1.0 to be removed in V2.0.

    «To be removed in V2.0» — тобто це питання часу, а не стилю.
    Відмінність у сигнатурі: system_prompt замість prompt.

    Про пам'ять. MemorySaver тримає історію розмов У ПАМ'ЯТІ процесу:
    перезапустили сервер — усі діалоги зникли. Для лабораторної цього
    досить. Для чогось довговічнішого беріть SqliteSaver із
    langgraph-checkpoint-sqlite: той самий інтерфейс, але стан лежить
    у файлі й переживає перезапуск.
    """
    from langchain.agents import create_agent
    from langchain_tavily import TavilySearch
    from langgraph.checkpoint.memory import MemorySaver

    tools = []
    if settings.tavily_api_key:
        tools.append(TavilySearch(max_results=3))

    return create_agent(
        model=load_google_llm(),
        tools=tools,
        system_prompt=(
            "Ти — Construction AI, помічник у будівельній галузі. "
            "Для питань про актуальні дані, ціни чи норми користуйся пошуком, "
            "а не пам'яттю. Ти НЕ інженер і НЕ архітектор: не давай остаточних "
            "технічних висновків, радь звіритися з фахівцем. "
            "Відповідай мовою користувача."
        ),
        checkpointer=MemorySaver(),
    )
