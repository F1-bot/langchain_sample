"""
Агент-кошторисник: приклад, на якому видно межу інструмента.

ГОЛОВНЕ, ЩО ТУТ ЗМІНИЛОСЬ ПРОТИ ТОРІШНЬОЇ ВЕРСІЇ
────────────────────────────────────────────────────────────────────
1. calculate_material_cost рахував ОДНУ позицію, а підсумок по
   кошторису складала сама модель. Арифметика кожного рядка була
   правильна, помилявся «шов» між інструментом і моделлю: на
   кількох позиціях LLM плутала, що вже враховано, а що ні.

   Тепер calculate_estimate приймає СПИСОК позицій і повертає
   підсумок, ПДВ і разом — моделі нічого складати.

   Правило, яке варто винести: якщо дія складається з кількох
   кроків, інструмент має віддавати результат УСІЄЇ дії, а не
   напівфабрикат.

2. write_report писав за будь-яким шляхом, який назве модель.
   Перевірено на старій версії: "../../escaped.txt" і абсолютний
   шлях спрацьовували — файл з'являвся поза проєктом. Тепер ім'я
   проходить через config.safe_output_path().

3. create_react_agent застарів. Сам LangGraph каже про це прямо:
   "create_react_agent has been moved to langchain.agents. Please
   update your import to `from langchain.agents import create_agent`.
   Deprecated in LangGraph V1.0 to be removed in V2.0."
"""
import json
from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import ARTIFACTS_DIR, load_google_llm, safe_output_path

VAT_RATE = 0.20


# ══════════════════════════════════════════════════════════════════
# ІНСТРУМЕНТ 1: кошторис цілком
# ══════════════════════════════════════════════════════════════════
class LineItem(BaseModel):
    """Одна позиція кошторису."""

    material: str = Field(description="Назва матеріалу, напр. 'бетон М300'")
    quantity: float = Field(gt=0, description="Кількість одиниць")
    unit: str = Field(default="од.", description="Одиниця виміру: м3, м2, кг, шт")
    price_per_unit: float = Field(gt=0, description="Ціна за одиницю, грн, без ПДВ")


class EstimateArgs(BaseModel):
    """Усі позиції кошторису за один виклик."""

    items: list[LineItem] = Field(
        description="ВСІ позиції одразу, а не по одній")


# Pydantic тримає list[LineItem] як відкладене посилання і резолвить
# його за іменем модуля. При імпорті під іншим іменем (тести) резолв
# падає з "EstimateArgs is not fully defined". Один явний виклик знімає
# питання.
EstimateArgs.model_rebuild()


@tool(args_schema=EstimateArgs)
def calculate_estimate(items: list[LineItem]) -> str:
    """Рахує ПОВНИЙ кошторис: кожну позицію плюс підсумок із ПДВ.

    Передавай УСІ позиції за ОДИН виклик. Не складай рядки самостійно —
    інструмент уже повертає підсумок, ПДВ і загальну суму.
    """
    lines, subtotal = [], 0.0
    for raw in items:
        item = raw if isinstance(raw, dict) else raw.model_dump()
        line_total = item["price_per_unit"] * item["quantity"]
        subtotal += line_total
        lines.append({
            "material": item["material"],
            "quantity": f"{item['quantity']:g} {item.get('unit', 'од.')}",
            "price_per_unit": f"{item['price_per_unit']:.2f} грн",
            "line_total_no_vat": f"{line_total:.2f} грн",
        })

    vat = subtotal * VAT_RATE
    return json.dumps({
        "lines": lines,
        "subtotal_no_vat": f"{subtotal:.2f} грн",
        f"vat_{int(VAT_RATE * 100)}_percent": f"{vat:.2f} грн",
        "GRAND_TOTAL_with_vat": f"{subtotal + vat:.2f} грн",
        "note": "ПДВ нараховано ОДИН раз на підсумок. Не додавай його повторно.",
    }, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════
# ІНСТРУМЕНТ 2: збереження звіту
# ══════════════════════════════════════════════════════════════════
@tool
def write_report(filename: str, content: str) -> str:
    """Зберігає готовий звіт у текстовий файл. Викликай один раз, у кінці.

    Args:
        filename: просте ім'я файлу, напр. 'estimate.txt' (без тек і шляхів)
        content: повний текст звіту
    """
    try:
        target = safe_output_path(filename)      # ім'я вигадала модель
    except ValueError as exc:
        return (f"Відмовлено: {exc}. "
                "Передай просте ім'я файлу, наприклад 'estimate.txt'.")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(f"Кошторис\n{stamp}\n{'=' * 52}\n\n{content}\n",
                      encoding="utf-8")
    return (f"Звіт збережено: {target.name} "
            f"({len(content.split())} слів). Завдання виконано.")


# ══════════════════════════════════════════════════════════════════
# АГЕНТ
# ══════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Ти «AI-Кошторисник» — помічник будівельного кошторисника.

ЖОРСТКІ ПРАВИЛА:
1. НІКОЛИ не рахуй самостійно — навіть не додавай. Виклич calculate_estimate
   з УСІМА позиціями за ОДИН раз; інструмент поверне підсумок, ПДВ і разом.
2. Називай числа так, як їх повернув інструмент. Не нараховуй ПДВ удруге.
3. Якщо потрібні актуальні ринкові ціни — спершу скористайся пошуком.
   Якщо ціни дав користувач, бери їх як є.
4. Якщо просять зберегти — ОБОВ'ЯЗКОВО виклич write_report, перш ніж
   відповідати. Сказати «файл збережено», не викликавши інструмент, — це
   помилка: нічого не записано, а користувач вважає, що все гаразд.
5. Відповідай мовою користувача, стисло.
"""


def build_tools():
    """Інструменти агента. Пошук підключаємо, лише якщо є ключ Tavily."""
    from langchain_tavily import TavilySearch

    from app.config import settings

    tools = [calculate_estimate, write_report]
    if settings.tavily_api_key:
        tools.insert(0, TavilySearch(max_results=3))
    return tools


def create_estimator_agent():
    """Створює агента-кошторисника."""
    # create_agent із пакета langchain, а НЕ create_react_agent з
    # langgraph.prebuilt: друга функція застаріла. Відмінність у
    # сигнатурі — system_prompt замість prompt.
    from langchain.agents import create_agent

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return create_agent(
        model=load_google_llm(),
        tools=build_tools(),
        system_prompt=SYSTEM_PROMPT,
    )
