"""
Конфігурація проєкту: ключі, модель, безпечні шляхи.

Єдина точка, де налаштовується LLM. Усе інше імпортує звідси.
"""
import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# ══════════════════════════════════════════════════════════════════
# НАЛАШТУВАННЯ
# ══════════════════════════════════════════════════════════════════
# Тека, куди агент має право писати файли. Усе за її межами —
# заборонено (див. safe_output_path нижче).
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"


class Settings(BaseSettings):
    # ── Обов'язкові ключі ─────────────────────────────────────────
    google_api_key: str = Field(..., description="Google Gemini API key")
    tavily_api_key: str = Field(..., description="Tavily API key")

    # ── LangSmith: НЕОБОВ'ЯЗКОВИЙ ─────────────────────────────────
    # Раніше langchain_api_key був обов'язковим полем, і застосунок
    # не стартував без ключа LangSmith — хоча трейсинг потрібен лише
    # для спостереження. Студент із ключами Google і Tavily впирався
    # у ValidationError на самому старті. Тепер поле порожнє за
    # замовчуванням, а трейсинг вмикається тільки якщо ключ заданий.
    #
    # Імена змінних теж змінились: LANGCHAIN_* перейменовано на
    # LANGSMITH_*. Старі ще читаються (див. _sync_langsmith_env),
    # але в нових проєктах пишіть LANGSMITH_.
    langsmith_api_key: str = Field(default="")
    langsmith_tracing: bool = Field(default=False)
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com")
    langsmith_project: str = Field(default="construction-ai")

    # ── Сервер ────────────────────────────────────────────────────
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:8000,http://127.0.0.1:8000")

    # ── Модель ────────────────────────────────────────────────────
    # gemini-3.5-flash-lite: безкоштовний тариф, швидка, достатня для
    # цієї лабораторної. Перевірено за документацією Google 18.10.2026.
    #
    # НЕ беріть gemini-2.0-flash-exp — цю модель вимкнено 9 грудня 2025,
    # а саме вона стояла в старому .env.example. Якщо агент раптом
    # відповідає 404 NOT_FOUND — почніть перевірку звідси.
    gemini_model: str = Field(default="gemini-3.5-flash-lite")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=100, le=8192)
    max_file_size: int = Field(default=10 * 1024 * 1024)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",          # щоб старі LANGCHAIN_* не валили старт
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tracing_enabled(self) -> bool:
        """Трейсинг має сенс лише тоді, коли є ключ."""
        return bool(self.langsmith_api_key) and self.langsmith_tracing


def _read_legacy_env() -> None:
    """
    Підхоплює старі імена змінних LANGCHAIN_*.

    У проєктів, зроблених торік, у .env лежить LANGCHAIN_API_KEY.
    Щоб вони не ламались, переносимо значення у нові імена — але
    лише якщо нових немає.
    """
    for old, new in (("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"),
                     ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"),
                     ("LANGCHAIN_ENDPOINT", "LANGSMITH_ENDPOINT"),
                     ("LANGCHAIN_PROJECT", "LANGSMITH_PROJECT")):
        if os.getenv(old) and not os.getenv(new):
            os.environ[new] = os.environ[old]


_read_legacy_env()
settings = Settings()


def _apply_tracing() -> None:
    """Вмикає або явно вимикає трейсинг LangSmith."""
    if settings.tracing_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    else:
        # Вимикаємо ЯВНО: інакше бібліотека намагатиметься слати трейси
        # й кожен виклик чекатиме на таймаут.
        os.environ["LANGSMITH_TRACING"] = "false"


_apply_tracing()


# ══════════════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════════════
# Частина нових моделей Gemini має ФІКСОВАНІ параметри семплювання:
# temperature, top_p і top_k вони просто ігнорують. Якщо передати
# temperature такій моделі, langchain-google-genai викине значення і
# попередить:
#
#   UserWarning: Model 'gemini-3.5-flash-lite' uses fixed sampling
#   defaults; the sampling parameter(s) temperature will be ignored.
#
# Поведінка від цього не змінюється, але студент бачить попередження
# на кожному запуску й не розуміє, чи все гаразд. Тому temperature
# передаємо лише тим моделям, які її насправді читають.
#
# Перелік таких моделей не виводиться з номера версії: gemini-3.5-flash
# параметри читає, а gemini-3.5-flash-lite — ні. Тож питаємо саму
# бібліотеку, а власний список лишаємо тільки як запасний варіант.
_FIXED_SAMPLING_MODELS = frozenset({"gemini-3.5-flash-lite", "gemini-3.6-flash"})


def model_honours_temperature(model: str) -> bool:
    """Чи вплине temperature на цю модель."""
    try:
        from langchain_google_genai.chat_models import (
            _uses_fixed_sampling_and_disallows_prefill as _fixed,
        )
    except ImportError:          # приватну функцію прибрали або перейменували
        return model.rsplit("/", 1)[-1].lower() not in _FIXED_SAMPLING_MODELS
    return not _fixed(model)


def _llm_kwargs(temperature: float) -> dict:
    """Аргументи для ChatGoogleGenerativeAI без параметрів, які модель ігнорує."""
    kwargs = {
        "model": settings.gemini_model,
        "google_api_key": settings.google_api_key,
        "max_output_tokens": settings.max_tokens,
    }
    if model_honours_temperature(settings.gemini_model):
        kwargs["temperature"] = temperature
    return kwargs


@lru_cache()
def load_google_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(**_llm_kwargs(settings.temperature))


@lru_cache()
def load_google_vision_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(**_llm_kwargs(0.2))


# ══════════════════════════════════════════════════════════════════
# БЕЗПЕЧНІ ШЛЯХИ ДЛЯ ФАЙЛІВ, ЯКІ СТВОРЮЄ АГЕНТ
# ══════════════════════════════════════════════════════════════════
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL",
                 *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


def safe_output_path(filename: str, base_dir: Path | None = None,
                     default_suffix: str = ".txt") -> Path:
    """
    Перетворює ім'я файлу, яке ВИГАДАЛА МОДЕЛЬ, на безпечний шлях.

    Чому це обов'язково. Інструмент write_report приймає filename від
    LLM. А LLM у цьому проєкті читає веб через Tavily — тобто в її
    контекст потрапляє текст, який написали сторонні люди. Якщо
    передати таке ім'я прямо в open(), агент запише файл будь-куди:

        write_report("../../../etc/passwd", ...)
        write_report("C:/Windows/System32/evil.txt", ...)

    Перевірено на попередній версії цього коду: обидва варіанти
    спрацьовували, файл з'являвся за межами проєкту. У бекенді,
    доступному по HTTP, це вже не теоретична вада.

    Функція зрізає теки й літеру диска, відкидає порожні та
    зарезервовані імена Windows і гарантує, що результат лежить
    усередині base_dir.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("порожнє ім'я файлу")
    if "\x00" in filename:
        raise ValueError("нульовий байт в імені файлу")

    name = re.split(r"[\\/]", filename.strip())[-1]   # лишаємо тільки ім'я
    name = re.sub(r"^[A-Za-z]:", "", name)            # прибираємо літеру диска
    name = name.strip(". ")
    if not name or name in {".", ".."}:
        raise ValueError(f"некоректне ім'я файлу: {filename!r}")
    if name.split(".")[0].upper() in _WIN_RESERVED:
        raise ValueError(f"зарезервоване ім'я Windows: {name!r}")
    if not Path(name).suffix:
        name += default_suffix

    base = (base_dir or ARTIFACTS_DIR).resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / name).resolve()
    if base not in target.parents:
        raise ValueError(f"шлях виходить за межі {base}: {filename!r}")
    return target
