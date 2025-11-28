# Line Bot: ドンピシャ | Donpsha (Perfect Match)

A LINE bot that acts as an intelligent travel navigator for Japan.

Utilizing **Google Gemini 2.0 Flash** to interpret natural language requests (like "cheap dinner date spots"), this bot works as a logic layer between the user and a local station database (`stations.json`). It validates user intent against real geography to suggest accessible train-based destinations.

## Key Features

* **Natural Language Understanding**
    * Uses Gemini 2.0 to extract specific constraints (budget, time windows, and mood) from casual conversation.
    * Handles both English and Japanese inputs.
* **Geographic Logic**
    * **Fuzzy Matching:** Uses `thefuzz` algorithms to map specific landmarks (e.g., "Dotonbori") or vague inputs to the nearest valid rail station.
    * **Dynamic Search Radius:** Contextually expands or contracts the search area based on the request type.
        * "Walking distance" sets a 1.5 km limit.
        * "Dinner/Drinks" sets a 5.0 km limit.
        * "Day trip" sets a 20.0+ km limit.
* **Stateful Context**
    * Keeps conversation history for each user. If a suggestion is rejected ("too far"), the bot checks previous context to provide a better alternative.
* **System Resilience**
    * Includes auto-retry logic with exponential backoff to manage API rate limits (429 errors).
    * Uses `json_repair` to fix formatting errors in AI outputs to ensure the application stays stable.
* **User Experience**
    * Generates direct **Google Maps Search Links** for every recommendation to help with navigation.

## Architecture

1.  **`main.py` (Server):** Handles the FastAPI lifecycle and checks LINE Webhook signatures.
2.  **`tripFlow.py` (Logic Core):** Manages session state, connects with the Gemini API, and controls the recommendation flow.
3.  **`stationService.py` (Geospatial Layer):** Loads station data into memory and runs Haversine distance calculations and fuzzy string matching.

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
    Create a `.env` file with these values:
    ```ini
    LINE_CHANNEL_ACCESS_TOKEN=...
    LINE_CHANNEL_SECRET=...
    GEMINI_API_KEY=...
    ALLOWED_USER_IDS=Uxxxxxxxx...
    ```
4.  **Deployment**
    ```bash
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env
    ```

## Credits

* **Station Data:** The `stations.json` dataset comes from the [open-data-jp-railway-stations](https://github.com/piuccio/open-data-jp-railway-stations) repository.
* **Primary Sources:** Data comes from Ekidata and the Association for Open Data of Public Transportation (ODPT).