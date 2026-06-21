# Line Bot: ドンピシャ | Donpsha (Dead On)

A LINE bot that acts as an intelligent travel navigator for Japan.

Uses **Google Gemini** as the primary LLM with **Deepseek** as a fallback for interpreting natural language requests (like "cheap dinner date spots"). The bot validates user intent against real geography to suggest accessible train-based destinations.

## Key Features

* **Natural Language Understanding**
    * Extracts specific constraints (budget, time windows, mood) from casual conversation.
    * Handles both English and Japanese inputs.
* **Geographic Logic**
    * **Dynamic Search Radius:** Contextually expands or contracts search area based on request type.
        * "Walking distance" sets a 1.5 km limit.
        * "Dinner/Drinks" sets a 5.0 km limit.
        * "Day trip" sets a 20.0+ km limit.
* **Stateful Context**
    * Keeps conversation history per user. If a suggestion is rejected ("too far"), the bot uses previous context to provide a better alternative.
* **System Resilience**
    * Auto-retry with exponential backoff for API rate limits (429 errors).
    * Automatic fallback from Gemini to Deepseek if the primary LLM fails.
    * Uses `json_repair` to fix formatting errors in AI outputs.
* **User Experience**
    * Generates direct **Google Maps Search Links** for every recommendation.

## Architecture

Core files:

1.  **`main.py`** (Server)
    * Entry point for the application.
    * Handles FastAPI server and validates LINE Webhook signatures.
    * Enforces security by checking User IDs against the allowlist.
2.  **`tripFlow.py`** (Logic Core)
    * Manages chat sessions and connects to LLMs via the unified client.
    * Handles retry logic, formatting responses, and generating Google Maps links.
3.  **`stationService.py`** (Geospatial Layer)
    * Loads `stations.json` into memory.
    * Performs Haversine distance calculations to find nearby stations.
4.  **`lineWebhook.py`** (Utility)
    * Handles cryptographic validation required by LINE.
    * Parses raw request bodies into usable event objects.
5.  **`tripModels.py`** (Data Structures)
    * Defines Python dataclasses for data consistency.
6.  **`messageFormatter.py`** (Response Formatter)
    * Formats itinerary responses for LINE messages.
    * Supports both English and Japanese output.
7.  **`llm/`** (LLM Client Package)
    * Unified client for multiple LLM providers.
    * `client.py` - Main client with fallback logic.
    * `gemini_provider.py` - Gemini implementation.
    * `deepseek_provider.py` - Deepseek implementation.

## Setup

1.  **Environment Setup**
    ```bash
    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate
    ```
2.  **Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configuration**
    Create a `.env` file:
    ```ini
    LINE_CHANNEL_ACCESS_TOKEN=...
    LINE_CHANNEL_SECRET=...
    GEMINI_API_KEY=...
    DEEPSEEK_API_KEY=...
    ALLOWED_USER_IDS=Uxxxxxxxx...
    ```
4.  **Deployment**
    ```bash
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env
    ```

## Credits

* **Station Data:** The `stations.json` dataset comes from the [open-data-jp-railway-stations](https://github.com/piuccio/open-data-jp-railway-stations) repository.
* **Primary Sources:** Data comes from Ekidata and the Association for Open Data of Public Transportation (ODPT).
