    # Weather-Advisory Support Bot

    A chatbot that gives outdoor activity safety advice using live weather data and predefined safety policies (SOPs). Built with LangGraph, FastAPI. 

   **Live Demo: https://weather-advisory-bot.up.railway.app**

    ## Screenshots

    ![Screenshot 1](assests/Screenshot%202026-10-02%20154116.png)
    ![Screenshot 2](assests/Screenshot%202026-10-02%20155151.png)
    ![Screenshot 3](assests/Screenshot%202026-10-02%20155210.png)
    ![Screenshot 4](assests/Screenshot%202026-10-02%20160223.png)

    ## Setup

    ```bash
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env
    # Edit .env and add your FIREWORKS_API_KEY
    ```

    ## Run

    ```bash
    uvicorn backend.main:app --reload --port 8000
    ```

    Open http://localhost:8000

    ## Run Evals

    ```bash
    python -m evals.eval_suite
    ```

    ## How It Works

    The bot uses a LangGraph pipeline with 6 nodes:

    1. **parse_query** — LLM extracts location, activity, keywords from user message
    2. **fetch_weather** — Calls Open-Meteo API (geocode + forecast)
    3. **match_sops** — Checks weather against SOP thresholds (no LLM, pure code)
    4. **generate_response** — LLM writes a response grounded in the matched SOP
    5. **handle_weather_error** — Returns error message if API fails
    6. **handle_no_match** — Returns honest "no guidance" if no SOP applies

    The graph has two conditional branches: one after weather fetch (success vs failure) and one after SOP matching (match found vs no match).

    Threshold checks like `wind > 40 km/h` are done in code, not by the LLM. The LLM only handles intent extraction and natural language generation.

    ## SOPs

    13 policies defined in `sops/policies.yaml` covering outdoor exercise, travel, vulnerable groups, and severe weather. Adding a new SOP is just adding a YAML block — no code changes needed.

    ## Project Structure

    ```
    ├── backend/
    │   ├── main.py           — FastAPI server
    │   ├── graph.py          — LangGraph pipeline
    │   ├── weather.py        — Open-Meteo API client
    │   ├── sop_engine.py     — SOP matching engine
    │   └── state.py          — State type definitions
    ├── frontend/
    │   ├── index.html
    │   ├── style.css
    │   └── script.js
    ├── evals/
    │   ├── eval_suite.py     — 8 test cases
    │   └── results.md
    ├── sops/
    │   └── policies.yaml
    └── requirements.txt
    ```
