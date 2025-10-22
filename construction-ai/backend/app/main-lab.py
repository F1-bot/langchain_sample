import asyncio
import os
from typing import Type

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Крок 1: Налаштування конфігурації ---
# Переконайтесь, що у вас є .env файл з GOOGLE_API_KEY та TAVILY_API_KEY
from dotenv import load_dotenv

load_dotenv()

print("Ініціалізація LLM (Gemini)...")
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", convert_system_message_to_human=True)


# --- Крок 2: Створення кастомного інструмента ---
class MaterialCostArgs(BaseModel):
    """Схема вхідних даних для калькулятора."""
    price_per_unit: float = Field(description="Ціна за одну одиницю матеріалу.")
    quantity: float = Field(description="Кількість одиниць матеріалу.")


@tool(args_schema=MaterialCostArgs)
def calculate_material_cost(price_per_unit: float, quantity: float) -> str:
    """
    Обчислює загальну вартість будівельних матеріалів.
    Використовуй цей інструмент, коли потрібно виконати точний розрахунок вартості.
    """
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


print("Створення інструментів...")
search_tool = TavilySearch(max_results=2)
all_tools = [search_tool, calculate_material_cost, write_report]

# --- Крок 3: Створення та конфігурація агента ---
print("Створення агента 'АІ-Кошторисник'...")

# Створюємо агент за допомогою LangGraph
# Йому не потрібен системний промпт, оскільки create_react_agent використовує стандартний,
# але він аналізує описи інструментів (docstrings), щоб зрозуміти, як ними користуватися.
agent_executor = create_react_agent(llm, tools=all_tools)


# --- Крок 4: Запуск агента та перевірка результату ---
async def main():
    task = (
        "Пошукай середню ціну на бетон марки М300 в Україні. "
        "Потім розрахуй вартість 50 кубометрів, виходячи з ціни 3100 грн за кубометр. "
        "Збережи фінальний розрахунок у файл 'estimate.txt'."
    )

    print(f"\n🚀 Запускаю агента із завданням: '{task}'\n")

    # verbose=True не підтримується напряму, але можна використовувати LangSmith для трасування
    # Для лабораторної роботи ми будемо аналізувати результат
    response = await agent_executor.ainvoke({"messages": [("user", task)]})

    final_response = response['messages'][-1].content

    print("\n✅ Завдання виконано!")
    print(f"💬 Фінальна відповідь агента: {final_response}")

    report_path = 'estimate.txt'
    if os.path.exists(report_path):
        print(f"\n📄 Звіт знайдено в '{report_path}'. Його вміст:")
        with open(report_path, 'r', encoding='utf-8') as f:
            print("---")
            print(f.read().strip())
            print("---")
    else:
        print(f"❌ Звітний файл '{report_path}' не було створено.")


if __name__ == "__main__":
    asyncio.run(main())