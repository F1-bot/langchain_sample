"""
main-lab.py — шаблон для лабораторної роботи №3.

Автономний скрипт: агент отримує завдання, сам вирішує, якими
інструментами скористатись, і доводить справу до кінця.

ЗАПУСК
    python app/main-lab.py
    python app/main-lab.py --task "своє завдання"

ПОТРІБНІ КЛЮЧІ
    GOOGLE_API_KEY  — обов'язково, aistudio.google.com (безкоштовний тариф)
    TAVILY_API_KEY  — для веб-пошуку, tavily.com (безкоштовно 1000 запитів/міс)
    LANGSMITH_API_KEY — НЕ обов'язковий, лише для трейсингу

Ключі кладіть у .env поряд із requirements.txt (зразок — .env.example).
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

load_dotenv()

# Куди агентові дозволено писати. Усе поза цією текою — заборонено.
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
VAT_RATE = 0.20


def setup_console() -> None:
    """UTF-8 на виводі: інакше український текст падає з UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


setup_console()


# ══════════════════════════════════════════════════════════════════
# КРОК 1. Модель
# ══════════════════════════════════════════════════════════════════
def build_llm():
    """
    Ініціалізація Gemini.

    Назву моделі беремо з .env, щоб не правити код. Типове значення —
    gemini-3.5-flash-lite: безкоштовний тариф, швидка, для цієї задачі
    більш ніж достатня.

    УВАГА: не беріть gemini-2.0-flash-exp. Ця модель вимкнена ще
    9 грудня 2025, хоча саме вона стояла в старому .env.example.
    Симптом — 404 NOT_FOUND на першому ж виклику.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        print("  [!] Немає GOOGLE_API_KEY. Візьміть безкоштовний ключ на")
        print("      https://aistudio.google.com/apikey і покладіть у .env")
        sys.exit(1)

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=key,
        temperature=0.3,       # для агента передбачуваність важливіша за творчість
        max_output_tokens=2048,
    )


# ══════════════════════════════════════════════════════════════════
# КРОК 2. Кастомний інструмент
# ══════════════════════════════════════════════════════════════════
class LineItem(BaseModel):
    """Одна позиція кошторису."""

    material: str = Field(description="Назва матеріалу, напр. 'бетон М300'")
    quantity: float = Field(gt=0, description="Кількість одиниць")
    unit: str = Field(default="од.", description="Одиниця виміру: м3, м2, кг, шт")
    price_per_unit: float = Field(gt=0, description="Ціна за одиницю, грн, без ПДВ")


class EstimateArgs(BaseModel):
    """Усі позиції кошторису за один виклик."""

    items: list[LineItem] = Field(description="ВСІ позиції одразу, а не по одній")


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
        "vat_20_percent": f"{vat:.2f} грн",
        "GRAND_TOTAL_with_vat": f"{subtotal + vat:.2f} грн",
        "note": "ПДВ нараховано ОДИН раз на підсумок. Не додавай його повторно.",
    }, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════
# Безпечний шлях для файлів, імена яких вигадує модель
# ══════════════════════════════════════════════════════════════════
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL",
                 *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


def safe_output_path(filename: str) -> Path:
    """
    Перетворює ім'я від LLM на безпечний шлях усередині ARTIFACTS_DIR.

    Без цієї перевірки агент запише файл куди завгодно: "../../x.txt"
    або "C:/Windows/evil.txt" спрацюють. А ім'я приходить від моделі,
    яка читала веб — тобто це недовірений ввід.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("порожнє ім'я файлу")
    if "\x00" in filename:
        raise ValueError("нульовий байт в імені файлу")

    name = re.split(r"[\\/]", filename.strip())[-1]
    name = re.sub(r"^[A-Za-z]:", "", name).strip(". ")
    if not name or name in {".", ".."}:
        raise ValueError(f"некоректне ім'я файлу: {filename!r}")
    if name.split(".")[0].upper() in _WIN_RESERVED:
        raise ValueError(f"зарезервоване ім'я Windows: {name!r}")
    if not Path(name).suffix:
        name += ".txt"

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    base = ARTIFACTS_DIR.resolve()
    target = (base / name).resolve()
    if base not in target.parents:
        raise ValueError(f"шлях виходить за межі {base}: {filename!r}")
    return target


@tool
def write_report(filename: str, content: str) -> str:
    """Зберігає готовий звіт у текстовий файл. Викликай один раз, у кінці.

    Args:
        filename: просте ім'я файлу, напр. 'estimate.txt' (без тек і шляхів)
        content: повний текст звіту
    """
    try:
        target = safe_output_path(filename)
    except ValueError as exc:
        return (f"Відмовлено: {exc}. "
                "Передай просте ім'я файлу, наприклад 'estimate.txt'.")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    target.write_text(f"Кошторис\n{stamp}\n{'=' * 52}\n\n{content}\n",
                      encoding="utf-8")
    return f"Звіт збережено: {target.name}. Завдання виконано."


# ══════════════════════════════════════════════════════════════════
# КРОК 3. Агент
# ══════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Ти «AI-Кошторисник» — помічник будівельного кошторисника.

ЖОРСТКІ ПРАВИЛА:
1. НІКОЛИ не рахуй самостійно — навіть не додавай. Виклич calculate_estimate
   з УСІМА позиціями за ОДИН раз.
2. Називай числа так, як їх повернув інструмент. ПДВ удруге не нараховуй.
3. Для актуальних ринкових цін спершу скористайся пошуком. Якщо ціни дав
   користувач — бери їх як є.
4. Якщо просять зберегти — ОБОВ'ЯЗКОВО виклич write_report, перш ніж
   відповідати. Сказати «збережено», не викликавши інструмент, — помилка.
5. Відповідай українською, стисло.
"""


def build_agent():
    """
    Збирає агента.

    create_agent із пакета langchain, а НЕ create_react_agent з
    langgraph.prebuilt: друга функція застаріла, і LangGraph друкує на
    неї попередження «Deprecated in LangGraph V1.0 to be removed in V2.0».
    Відмінність у сигнатурі — system_prompt замість prompt.
    """
    from langchain.agents import create_agent

    tools = [calculate_estimate, write_report]

    if os.getenv("TAVILY_API_KEY"):
        from langchain_tavily import TavilySearch
        tools.insert(0, TavilySearch(max_results=3))
    else:
        print("  [i] TAVILY_API_KEY не заданий — працюємо без веб-пошуку.")

    return create_agent(model=build_llm(), tools=tools,
                        system_prompt=SYSTEM_PROMPT)


# ══════════════════════════════════════════════════════════════════
# КРОК 4. Запуск
# ══════════════════════════════════════════════════════════════════
DEFAULT_TASK = (
    "Порахуй кошторис: 50 м³ бетону М300 по 3000 грн/м³ і 200 м² цегляної "
    "кладки по 450 грн/м². Збережи результат у файл 'estimate.txt'."
)


async def run(task: str) -> None:
    agent = build_agent()
    print(f"\n  Завдання: {task}\n" + "─" * 62)

    final = ""
    # stream замість invoke: видно кожен крок агента, а не лише підсумок.
    # Саме цей вивід потрібен для скріншота у звіті.
    async for chunk in agent.astream({"messages": [HumanMessage(content=task)]},
                                     stream_mode="updates"):
        for node, payload in chunk.items():
            for msg in payload.get("messages", []):
                for call in getattr(msg, "tool_calls", None) or []:
                    args = json.dumps(call["args"], ensure_ascii=False)
                    print(f"  [{node}] -> {call['name']}({args[:120]})")
                if msg.__class__.__name__ == "ToolMessage":
                    text = str(msg.content).replace("\n", " ")
                    print(f"  [{node}] <- {text[:150]}")
                elif getattr(msg, "content", "") and not getattr(msg, "tool_calls", None):
                    final = msg.text if hasattr(msg, "text") else str(msg.content)

    print("─" * 62)
    print(f"\n  ПІДСУМОК:\n{final}\n")

    if ARTIFACTS_DIR.exists():
        files = sorted(ARTIFACTS_DIR.glob("*"))
        if files:
            newest = max(files, key=lambda p: p.stat().st_mtime)
            print(f"  Створено файл: {newest}")
            print("  " + newest.read_text(encoding="utf-8")[:400].replace("\n", "\n  "))
        else:
            print("  Файлів не створено — агент не викликав write_report.")


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-Кошторисник: шаблон ЛР №3")
    ap.add_argument("--task", default=DEFAULT_TASK, help="завдання для агента")
    args = ap.parse_args()

    print("=" * 62)
    print("  AI-Кошторисник — лабораторна робота №3")
    print("=" * 62)

    try:
        asyncio.run(run(args.task))
    except KeyboardInterrupt:
        print("\n  Скасовано.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
