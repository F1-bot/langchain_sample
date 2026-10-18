"""
Тести до лабораторної роботи №3 — БЕЗ виклику моделі та без мережі.

Інструмент агента — звичайна функція, і саме її треба покривати
тестами. LLM у CI не ганяють: вона повільна, недетермінована і
коштує грошей.

    pytest -q
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ключі-заглушки: конфіг вимагає їх наявності, але жоден тест
# нікуди не ходить.
os.environ.setdefault("GOOGLE_API_KEY", "test-stub")
os.environ.setdefault("TAVILY_API_KEY", "test-stub")

from app.config import safe_output_path, settings  # noqa: E402
from app.agents.estimator_agent import (  # noqa: E402
    VAT_RATE, calculate_estimate, write_report,
)


def call(tool, **kwargs):
    """Викликає інструмент у обхід декоратора LangChain."""
    fn = getattr(tool, "func", None) or getattr(tool, "fn", None) or tool
    return fn(**kwargs)


# ══════════════════════════════════════════════════════════════════
# 1. safe_output_path — ім'я файлу приходить ВІД МОДЕЛІ
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("hostile", [
    "../../../etc/passwd",
    "..\\..\\Windows\\System32\\drivers\\etc\\hosts",
    "/absolute/unix/path.txt",
    "C:\\Windows\\System32\\evil.txt",
    "sub/dir/nested.txt",
    "....//....//escape.txt",
])
def test_hostile_filename_stays_inside(tmp_path, hostile):
    """
    Попередня версія write_report передавала ім'я прямо в open().
    Перевірено: "../../escaped.txt" і абсолютний шлях спрацьовували,
    файл з'являвся поза проєктом.
    """
    result = safe_output_path(hostile, base_dir=tmp_path)
    assert result.parent == tmp_path.resolve(), f"вийшли за межі: {result}"


@pytest.mark.parametrize("bad", ["", "   ", ".", "..", "\x00x"])
def test_degenerate_filenames_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        safe_output_path(bad, base_dir=tmp_path)


@pytest.mark.parametrize("reserved", ["CON", "nul.txt", "com1.txt", "LPT9"])
def test_windows_device_names_rejected(tmp_path, reserved):
    with pytest.raises(ValueError):
        safe_output_path(reserved, base_dir=tmp_path)


def test_plain_name_kept_and_suffix_added(tmp_path):
    assert safe_output_path("estimate.txt", base_dir=tmp_path).name == "estimate.txt"
    assert safe_output_path("estimate", base_dir=tmp_path).name == "estimate.txt"


# ══════════════════════════════════════════════════════════════════
# 2. write_report
# ══════════════════════════════════════════════════════════════════
def test_write_report_refuses_escape(tmp_path, monkeypatch):
    import app.agents.estimator_agent as mod
    monkeypatch.setattr(mod, "safe_output_path",
                        lambda f, **kw: safe_output_path(f, base_dir=tmp_path))

    out = call(write_report, filename="../../pwned.txt", content="дані")
    assert out.startswith("Відмовлено") or (tmp_path / "pwned.txt").exists()
    assert not (tmp_path.parent / "pwned.txt").exists()


def test_write_report_writes_utf8(tmp_path, monkeypatch):
    import app.agents.estimator_agent as mod
    monkeypatch.setattr(mod, "safe_output_path",
                        lambda f, **kw: safe_output_path(f, base_dir=tmp_path))

    out = call(write_report, filename="звіт.txt", content="Бетон М300 — 50 м³")
    assert "збережено" in out.lower()
    written = (tmp_path / "звіт.txt").read_text(encoding="utf-8")
    assert "Бетон М300" in written


# ══════════════════════════════════════════════════════════════════
# 3. Кошторис рахується ЦІЛКОМ, ПДВ — рівно один раз
# ══════════════════════════════════════════════════════════════════
def test_estimate_sums_all_lines_once():
    """
    Торішній calculate_material_cost рахував ОДНУ позицію, а підсумок
    складала модель. На двох позиціях вона плуталась: що вже враховано,
    а що ні. Тепер підсумок рахує інструмент.
    """
    out = json.loads(call(calculate_estimate, items=[
        {"material": "бетон М300", "quantity": 50, "unit": "м3", "price_per_unit": 3000},
        {"material": "цегляна кладка", "quantity": 200, "unit": "м2", "price_per_unit": 450},
    ]))
    assert out["subtotal_no_vat"].startswith("240000")
    assert out["vat_20_percent"].startswith("48000")
    assert out["GRAND_TOTAL_with_vat"].startswith("288000")
    assert "345600" not in json.dumps(out), "ПДВ нараховано двічі"


def test_estimate_returns_every_line():
    out = json.loads(call(calculate_estimate, items=[
        {"material": "пісок", "quantity": 10, "unit": "т", "price_per_unit": 800},
        {"material": "арматура", "quantity": 2, "unit": "т", "price_per_unit": 42000},
        {"material": "цегла", "quantity": 100, "unit": "шт", "price_per_unit": 12},
    ]))
    assert len(out["lines"]) == 3
    # 8000 + 84000 + 1200 = 93200
    assert out["subtotal_no_vat"].startswith("93200")


def test_estimate_single_item():
    out = json.loads(call(calculate_estimate, items=[
        {"material": "бетон", "quantity": 1, "unit": "м3", "price_per_unit": 1000},
    ]))
    assert out["GRAND_TOTAL_with_vat"].startswith("1200")


def test_vat_rate_is_twenty_percent():
    assert VAT_RATE == 0.20


def test_estimate_accepts_models_and_dicts():
    """Pydantic може віддати і модель, і dict — приймаємо обидва."""
    from app.agents.estimator_agent import LineItem

    as_model = call(calculate_estimate, items=[
        LineItem(material="бетон", quantity=2, unit="м3", price_per_unit=100)])
    as_dict = call(calculate_estimate, items=[
        {"material": "бетон", "quantity": 2, "unit": "м3", "price_per_unit": 100}])
    assert json.loads(as_model)["GRAND_TOTAL_with_vat"] == \
           json.loads(as_dict)["GRAND_TOTAL_with_vat"]


@pytest.mark.parametrize("bad", [
    {"material": "x", "quantity": 0, "unit": "шт", "price_per_unit": 10},
    {"material": "x", "quantity": -5, "unit": "шт", "price_per_unit": 10},
    {"material": "x", "quantity": 1, "unit": "шт", "price_per_unit": -10},
])
def test_estimate_schema_rejects_nonpositive(bad):
    """Схема сама відкидає від'ємні значення — перевіряти в коді не треба."""
    from pydantic import ValidationError

    from app.agents.estimator_agent import EstimateArgs

    with pytest.raises(ValidationError):
        EstimateArgs(items=[bad])


# ══════════════════════════════════════════════════════════════════
# 4. Конфігурація
# ══════════════════════════════════════════════════════════════════
def test_app_starts_without_langsmith_key():
    """
    Раніше langchain_api_key було обов'язковим полем, і застосунок не
    стартував без ключа LangSmith — хоча трейсинг до роботи агента
    стосунку не має.
    """
    assert settings.langsmith_api_key == "" or isinstance(settings.langsmith_api_key, str)
    assert settings.tracing_enabled is False or bool(settings.langsmith_api_key)


def test_default_model_is_alive():
    """
    gemini-2.0-flash-exp вимкнено 9 грудня 2025, а саме воно стояло
    в торішньому .env.example.
    """
    assert settings.gemini_model != "gemini-2.0-flash-exp"
    assert settings.gemini_model.startswith("gemini-")


def test_env_example_has_no_dead_model():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    live = [ln for ln in text.splitlines()
            if ln.strip().startswith("GEMINI_MODEL=")]
    assert live, "у .env.example немає GEMINI_MODEL"
    assert "gemini-2.0-flash-exp" not in live[0]


def test_requirements_are_pinned():
    """Непіновані залежності ламаються при черговому релізі, а не при зміні коду."""
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pkgs = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    unpinned = [p for p in pkgs if "==" not in p]
    assert not unpinned, f"без піна: {unpinned}"


# ══════════════════════════════════════════════════════════════════
# 5. Актуальність API, на якому тримається проєкт
# ══════════════════════════════════════════════════════════════════
def test_create_agent_is_the_current_api():
    from langchain.agents import create_agent

    import inspect
    params = inspect.signature(create_agent).parameters
    assert "system_prompt" in params, "сигнатура змінилась"
    assert "checkpointer" in params


def test_create_react_agent_is_deprecated():
    """Якщо цей тест впаде — LangGraph або прибрав функцію, або зняв попередження."""
    from langgraph.prebuilt import create_react_agent

    assert "deprecated" in (create_react_agent.__doc__ or "").lower()


def test_project_does_not_use_deprecated_agent_api():
    """
    Жоден файл застосунку не має ІМПОРТУВАТИ чи ВИКЛИКАТИ
    create_react_agent.

    Перевіряємо по дереву розбору, а не пошуком підрядка: у коментарях
    і докстрінгах ця назва згадується навмисно — там пояснюється, чому
    від неї відмовились.
    """
    import ast

    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "create_react_agent":
                        offenders.append(f"{path.name}:{node.lineno} import")
            elif isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "create_react_agent":
                    offenders.append(f"{path.name}:{node.lineno} виклик")
    assert not offenders, offenders


def test_agents_are_built_lazily():
    """
    Імпорт маршрутів не має створювати агента: інакше будь-яка помилка
    конфігурації валить увесь застосунок ще до старту, і навіть /health
    стає недоступним.
    """
    import time

    started = time.time()
    import app.routes.analysis  # noqa: F401
    assert time.time() - started < 10.0


# ══════════════════════════════════════════════════════════════════
# 6. Застосунок мусить ІМПОРТУВАТИСЬ цілком
# ══════════════════════════════════════════════════════════════════
def test_whole_app_imports():
    """
    Найдешевший тест у наборі й найкорисніший.

    Попередня версія падала на старті сервера:

        File "app/services/tavily_service.py", line 1
        ModuleNotFoundError: No module named 'tavily'

    Модуль tavily_service імпортується з routes/research.py, той — з
    main.py. Тести ж імпортували лише routes/analysis.py і цього не
    бачили. Імпортуємо застосунок повністю — тоді будь-яка поломка на
    рівні модуля видно одразу, а не під час демонстрації.
    """
    import app.main

    # openapi() обходить і вкладені роутери, і заразом перевіряє, що
    # схеми відповідей коректні — саме її показує /docs.
    paths = app.main.app.openapi()["paths"]
    assert "/api/health" in paths
    assert "/api/run-estimator" in paths
    assert "/api/research" in paths


def test_importing_app_does_not_build_llm(monkeypatch):
    """Імпорт не має створювати модель: інакше він повільний і ламкий."""
    import app.config as cfg

    cfg.load_google_llm.cache_clear()
    cfg.load_google_vision_llm.cache_clear()
    assert cfg.load_google_llm.cache_info().currsize == 0

    import app.services.gemini_service as gs  # noqa: F401
    import app.services.tavily_service as ts  # noqa: F401

    assert cfg.load_google_vision_llm.cache_info().currsize == 0, \
        "створення моделі на імпорті"
    assert ts._search_tool.cache_info().currsize == 0, \
        "створення клієнта Tavily на імпорті"


# ══════════════════════════════════════════════════════════════════
# 7. requirements.txt мусить покривати ВСЕ, що імпортує app/
# ══════════════════════════════════════════════════════════════════
def test_requirements_cover_every_import():
    """
    Пакет tavily-python був у коді, але не в requirements.txt. У моєму
    оточенні він лишився від попередньої установки, тож усе працювало;
    у студента в чистому venv сервер не стартував.

    Тому звіряємо не «чи імпортується», а «чи записано в requirements».
    """
    import ast
    from importlib.metadata import packages_distributions

    imported = set()
    for path in (ROOT / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party = imported - set(sys.stdlib_module_names) - {"app"}

    def canon(name: str) -> str:
        """PEP 503: langchain_core і langchain-core — той самий пакет."""
        return re.sub(r"[-_.]+", "-", name).lower()

    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    listed = {canon(ln.split("==")[0]) for ln in req.splitlines()
              if ln.strip() and not ln.strip().startswith("#")}

    # packages_distributions() знає неочевидні відповідності (dotenv ->
    # python-dotenv), але на частині пакетів повертає None. Тому до неї
    # додаємо найпростіший здогад: ім'я модуля і є ім'ям пакета.
    mapping = packages_distributions()
    missing = []
    for mod in sorted(third_party):
        candidates = {canon(d) for d in (mapping.get(mod) or [])} | {canon(mod)}
        if not candidates & listed:
            missing.append(f"{mod} (шукали {sorted(candidates)})")
    assert not missing, f"імпортується, але немає в requirements.txt: {missing}"


# ══════════════════════════════════════════════════════════════════
# 8. temperature передаємо лише тим моделям, які її читають
# ══════════════════════════════════════════════════════════════════
def test_temperature_dropped_for_fixed_sampling_model(monkeypatch):
    """
    gemini-3.5-flash-lite ігнорує temperature, і бібліотека попереджає
    про це на кожному виклику. Попередження лякає студента, хоча
    поведінка правильна. Простіше не передавати те, що все одно
    викинуть.
    """
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "gemini_model", "gemini-3.5-flash-lite")
    assert cfg.model_honours_temperature("gemini-3.5-flash-lite") is False
    assert "temperature" not in cfg._llm_kwargs(0.3)


def test_temperature_kept_for_normal_model(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "gemini_model", "gemini-3.8-flash")
    assert cfg.model_honours_temperature("gemini-3.8-flash") is True
    assert cfg._llm_kwargs(0.3)["temperature"] == 0.3


def test_no_sampling_warning_for_default_model():
    """Типова модель із .env.example не має сипати попередженнями."""
    import warnings

    import app.config as cfg

    cfg.load_google_llm.cache_clear()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg.load_google_llm()
    noisy = [w for w in caught if "sampling" in str(w.message).lower()]
    assert not noisy, [str(w.message) for w in noisy]


# ══════════════════════════════════════════════════════════════════
# 9. Аргументи, які шлемо в Tavily, мусять збігатися з його схемою
# ══════════════════════════════════════════════════════════════════
def test_search_payload_matches_tool_schema():
    """
    max_results у TavilySearch задається ЛИШЕ при створенні. Переданий
    у invoke(), він не падає винятком, а повертає

        {"error": "The parameter 'max_results' can only be set during
         instantiation, not during invocation."}

    — і /api/research віддає 500. Звіряємо ключі, які шлемо, зі схемою
    інструмента: мережа для цього не потрібна.
    """
    from langchain_tavily.tavily_search import TavilySearchInput

    from app.services.tavily_service import search_payload

    sent = set(search_payload("цемент М500"))
    allowed = set(TavilySearchInput.model_fields)
    assert sent <= allowed, f"інструмент не приймає: {sorted(sent - allowed)}"
    assert "max_results" not in allowed, \
        "max_results знову став параметром виклику — спростіть код"


def test_search_tool_is_built_per_max_results(monkeypatch):
    """Різним max_results потрібні різні інструменти, бо значення вшите."""
    import app.services.tavily_service as ts

    monkeypatch.setattr(ts.settings, "tavily_api_key", "stub")
    ts._search_tool.cache_clear()
    try:
        assert ts._search_tool(3).max_results == 3
        assert ts._search_tool(7).max_results == 7
    finally:
        ts._search_tool.cache_clear()


def test_search_without_key_explains_itself(monkeypatch):
    import app.services.tavily_service as ts

    monkeypatch.setattr(ts.settings, "tavily_api_key", "")
    ts._search_tool.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
            ts.tavily_service.search_construction_research("бетон")
    finally:
        ts._search_tool.cache_clear()


# ══════════════════════════════════════════════════════════════════
# 10. Визначення артефакту: створення І перезапис
# ══════════════════════════════════════════════════════════════════
def test_overwritten_artifact_is_detected(tmp_path, monkeypatch):
    """
    Перший варіант порівнював лише ІМЕНА файлів. На другому запуску з
    тим самим estimate.txt нове ім'я не з'являється, і API повертав
    artifact_path: null, хоча агент файл зберіг. Відтворено запуском.
    """
    import time

    import app.routes.analysis as mod

    monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
    existing = tmp_path / "estimate.txt"
    existing.write_text("старий кошторис", encoding="utf-8")

    before = mod._artifact_snapshot()
    time.sleep(0.01)
    existing.write_text("новий кошторис, інший розмір", encoding="utf-8")
    after = mod._artifact_snapshot()

    assert mod._newest_touched(before, after) == "estimate.txt"


def test_new_artifact_is_detected(tmp_path, monkeypatch):
    import app.routes.analysis as mod

    monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
    before = mod._artifact_snapshot()
    (tmp_path / "pwned.txt").write_text("x", encoding="utf-8")
    assert mod._newest_touched(before, mod._artifact_snapshot()) == "pwned.txt"


def test_untouched_artifacts_report_nothing(tmp_path, monkeypatch):
    """Агент нічого не зберігав — API не має вигадувати файл."""
    import app.routes.analysis as mod

    monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
    (tmp_path / "old.txt").write_text("лежить собі", encoding="utf-8")

    before = mod._artifact_snapshot()
    assert mod._newest_touched(before, mod._artifact_snapshot()) is None
