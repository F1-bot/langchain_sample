# Construction AI Agent Backend

**[EN]** This repository contains the code for a lab project on developing an AI assistant for the construction industry. The agent is built on the FastAPI framework, uses LangChain for orchestration, the Google Gemini model as its core "brain," and Tavily for specialized web research.

**[UA]** Цей репозиторій містить код для лабораторної роботи з розробки AI-асистента для будівельної галузі. Агент побудований на базі фреймворку FastAPI, використовує LangChain для оркестрації, модель Google Gemini як "мозок" та Tavily для спеціалізованого веб-пошуку.

## 🚀 Key Features

-   **AI Agent Chat**
    Implements an interactive chat based on the ReAct (Reasoning and Acting) architecture, allowing the agent to autonomously plan and execute actions to achieve a goal.

-   **Structured Text Analysis**
    Analyzes text documents (reports, specifications) and returns structured data in JSON format, powered by LangChain's Pydantic parsers.

-   **Image Analysis (OCR + AI)**
    Leverages Gemini's multimodal capabilities to extract text from images (blueprints, plans, report photos) for subsequent intelligent analysis.

-   **Specialized Web Research**
    Uses the Tavily Search API to find up-to-date information from specialized construction sources (RAG approach).

-   **Bilingual Support**
    The system of prompts and chains is configured to support both English and French.

## 🛠️ Tech Stack

| Technology         | Purpose                  | Why We Chose It                                                 |
| ------------------ | ------------------------ | --------------------------------------------------------------- |
| **FastAPI**        | Backend framework        | Fast, modern, and provides automatic API documentation.         |
| **LangChain**      | AI orchestration         | Easily chain AI operations and manage agents.                   |
| **Google Gemini**  | AI Model                 | High performance, multimodal capabilities (text + vision).      |
| **Tavily AI**      | Research search engine   | High-quality search results optimized for AI agents.            |
| **Pydantic**       | Data validation          | Ensures type safety and automatic validation for requests/responses. |
| **Python 3.11+**   | Programming language     | Modern syntax and an extensive ecosystem of libraries.          |

## 🔄 What changed in the 2026 update

**[EN]** This project was audited and brought up to date against LangChain 1.x.
**[UA]** Проєкт перевірено й оновлено під LangChain 1.x. Нижче — що саме
й чому; кожен пункт відтворювався запуском, а не припущенням.

| Було | Стало | Чому |
|---|---|---|
| `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` | бібліотека сама друкує: *"Deprecated in LangGraph V1.0 to be removed in V2.0"* |
| `calculate_material_cost` рахував одну позицію | `calculate_estimate` рахує весь кошторис | підсумок складала модель і плуталась; тепер рахує інструмент |
| `write_report` писав за будь-яким шляхом | через `safe_output_path()` | перевірено: `../../x.txt` і абсолютний шлях спрацьовували |
| `langchain_api_key` обов'язковий | LangSmith необов'язковий | без ключа застосунок не стартував |
| `gemini-2.0-flash-exp` у `.env.example` | `gemini-3.5-flash-lite` | стару модель вимкнено 09.12.2025 |
| агенти створювались на імпорті | ліниво, при першому запиті | помилка конфігурації валила весь сервер, включно з `/health` |
| файл визначався пошуком підрядка | порівнянням вмісту теки | модель могла сказати «збережено», не викликавши інструмент |
| залежності без версій | усе закріплено | проєкт ламався від чужого релізу, а не від своїх змін |
| `services/tavily_service.py` імпортував пакет `tavily` | через `langchain-tavily` | пакета не було в `requirements.txt`: у чистому venv сервер падав на старті з `ModuleNotFoundError` |
| `tavily_service` і `gemini_service` створювались на імпорті | ліниво | те саме, що з агентами: помилка валила весь застосунок |
| промпти в `gemini_service` просили «Patient information», «Doctor's notes» | промпти про будівельну документацію | залишок медичного шаблону, з якого робили проєкт |
| `temperature` передавалась завжди | лише моделям, які її читають | `gemini-3.5-flash-lite` її ігнорує й на кожному запуску друкував `UserWarning: ... uses fixed sampling defaults` |
| `Pillow` у залежностях | прибрано | ніде не імпортується |
| `max_results` передавався в `invoke()` Tavily | задається при створенні інструмента | інакше `/api/research` віддавав 500: Tavily приймає цей параметр лише в конструкторі |
| наявність артефакту визначалась за новими ІМЕНАМИ файлів | за розміром і часом зміни | при повторному записі в той самий `estimate.txt` нове ім'я не з'являється, і API повертав `artifact_path: null` |
| тестів не було | 46 тестів | без моделі й без мережі, ~2 с |

Детальніше про `create_agent` і межу інструмента — у матеріалах Лекції 6.

### Tests

```bash
cd construction-ai/backend
pytest -q          # 46 passed — ні моделі, ні мережі не потрібно
```

Тести навмисно не торкаються LLM: вона повільна, недетермінована й
коштує грошей. Перевіряються інструменти, схеми й конфігурація —
тобто рівно те, що ви пишете самі.

## ⚙️ Setup & Installation

Follow these steps to set up and run the project.

### 1. Prerequisites

Ensure you have the following installed:
-   Python 3.11+
-   `pip` (Python package manager)
-   **API Keys (free tiers available):**
    -   **Google Gemini API key** — required: [get it here](https://aistudio.google.com/apikey)
    -   **Tavily API key** — required for web search: [get it here](https://app.tavily.com/)
    -   **LangSmith API key** — **optional**, tracing only: [get it here](https://smith.langchain.com/)

> **[UA]** Ключ LangSmith НЕ обов'язковий. Раніше застосунок без нього
> взагалі не стартував (`langchain_api_key` було обов'язковим полем і
> Pydantic падав із ValidationError ще до запуску сервера). Тепер без
> нього все працює, просто трейси нікуди не йдуть.

### 2. Clone and Set Up the Environment

```bash
# Clone the repository
git clone [YOUR_GITHUB_REPOSITORY_URL]
cd [PROJECT_FOLDER_NAME]/backend

# Create a virtual environment
python -m venv venv

# Activate the environment
# On Windows
# venv\Scripts\activate
# On macOS/Linux
# source venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `backend/` directory. You can copy the contents of `.env.example` as a template and fill in your API keys.

```env
GOOGLE_API_KEY=AIzaSy...your_gemini_key
TAVILY_API_KEY=tvly-...your_tavily_key

# Model. gemini-3.5-flash-lite is free-tier and fast enough for this lab.
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional — tracing only. Note the names: LANGCHAIN_* were renamed to LANGSMITH_*.
# LANGSMITH_API_KEY=lsv2_pt_...
# LANGSMITH_TRACING=true
```

**⚠️ Do NOT use `gemini-2.0-flash-exp`.** That value was in last year's
`.env.example`, and the model was shut down on 9 December 2025. The symptom
is a `404 NOT_FOUND` on the agent's very first call. Current model list:
<https://ai.google.dev/gemini-api/docs/models>

**IMPORTANT:** `.env` is already in `.gitignore` — keep it that way.

## ▶️ Running the Application

1.  Make sure your virtual environment is activated.
2.  From the `backend/` directory, start the server:
    ```bash
    uvicorn app.main:app --reload
    ```
3.  The server will be available at `http://127.0.0.1:8000`.
4.  Open the interactive API documentation in your browser: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**.
5.  Use the Swagger UI to test all endpoints (`/chat`, `/analyze-text`, `/analyze-image`, etc.).
6.  **Analyze your agent's traces** on the [**LangSmith website**](https://smith.langchain.com/) to see its "thoughts" and the tool selection process.

## 📚 Individual Assignment Variants

The goal is to extend the agent's functionality by creating a new, unique tool and integrating it into the application. Below are some example ideas for inspiration.

<details>
<summary>Click to expand the list of assignment variants</summary>

| Variant | Agent/Tool Idea | Key Tools | Key Requirement |
|:---:|---|---|---|
| 1 | **AI Engineering Consultant** | `convert_units(value, from, to)` | The agent must be able to convert units of length (feet ↔ meters) and pressure (PSI ↔ Pascals). |
| 2 | **AI Safety Inspector** | `get_safety_checklist(work_type)` | The agent must combine a base checklist (from an "internal database") with results from a web search. |
| 3 | **AI Project Planner**| `add_plan_step(step, duration)` | The agent must autonomously break down a large task (e.g., "build a foundation") into 3-4 steps and add them sequentially to a report. |
| 4 | **AI Materials Analyst**| `get_material_density(material)` | The agent must find the density of a material and then calculate the weight for a given volume. |
| 5 | **AI Code Compliance Checker** | `check_code_compliance(parameter, value)` | The agent must check input data (e.g., minimum wall thickness) against predefined rules. |
| 6 | **AI Archivist** | `archive_report(report_text)` | The agent must create a report and automatically add the current date and a unique ID. |
| 7 | **AI Logistics Coordinator** | `find_supplier_info(material)` | The agent must find 2-3 material suppliers online and extract their contact information. |
| 8 | **AI Surveyor** | `get_coordinates(address)` | The agent must use an external service (e.g., via the `requests` tool) to get coordinates for a given address. |
| 9 | **AI Ecologist** | `calculate_carbon_footprint(material, quantity)` | The agent must calculate the carbon footprint based on coefficients for various materials. |
| 10 | **AI Report Generator** | `format_daily_summary(tasks_done, problems)` | The agent must take a list of completed tasks and problems and format them into a standardized daily report. |

</details>