from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from app.config import load_google_llm


# --- Інструменти для агента ---

class MaterialCostArgs(BaseModel):
    price_per_unit: float = Field(description="Ціна за одну одиницю матеріалу.")
    quantity: float = Field(description="Кількість одиниць матеріалу.")


@tool(args_schema=MaterialCostArgs)
def calculate_material_cost(price_per_unit: float, quantity: float) -> str:
    """Обчислює загальну вартість будівельних матеріалів."""
    total_cost = price_per_unit * quantity
    return f"Загальна вартість для {quantity} одиниць за ціною {price_per_unit} за одиницю становить {total_cost:.2f}."


@tool
def write_report(filename: str, content: str) -> str:
    """Записує фінальний звіт у текстовий файл."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Звіт успішно збережено у файл {filename}"
    except Exception as e:
        return f"Помилка при збереженні звіту: {e}"


# --- Функція для створення агента ---

def create_estimator_agent():
    """Створює та повертає екземпляр агента-кошторисника."""
    llm = load_google_llm()
    search_tool = TavilySearch(max_results=2)

    # Агент отримує всі необхідні інструменти
    all_tools = [search_tool, calculate_material_cost, write_report]

    agent_executor = create_react_agent(llm, tools=all_tools)
    return agent_executor