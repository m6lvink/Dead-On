# ドンピシャ | Bingo

A LINE Messaging API bot that suggests train day trips in the Kyoto / Kansai area from natural-language prompts in English or Japanese.

Example:

> I'm at Kyoto Station, I have around 6000 yen, where can I go for a few hours? I've already been to Fushimi Inari and Arashiyama.

The bot parses the message, picks candidate stations from a static dataset, and returns 1–2 simple itineraries with rough cost and time.

---

## Core Features

- **Natural-language input (EN / JP)**  
  Accepts a single free-text message in English or Japanese. No rigid command format required.

- **Trip parsing via OpenAI (optional)**  
  Extracts:
  - `startStation`
  - `totalBudgetYen`
  - `timeWindowHours`
  - `moodLabel` (e.g., `food`, `sightseeing`, `nature`, `shopping`)
  - `avoidPlaces` (stations/areas the user has already visited)
  - `userLanguage` (`en` or `ja`)

- **Destination filtering**  
  Uses a small static station dataset (`stationDataset.json`) and filters by:
  - Budget (keeps train cost under a fraction of the budget)
  - Time window (limits total travel time)
  - Avoid list (skips places the user says they’ve already been)

- **Itinerary generation**  
  Builds 1–2 itineraries with:
  - Station stops
  - Activities at each stop
  - Estimated total cost and travel time

- **Bilingual replies**  
  Replies in the same language as the user input (EN or JP).

---

## Dev Mode vs API Mode

This project has a simple **dev mode** controlled by the `DEV_MODE` environment variable.

### Dev Mode Enabled (default)

When dev mode is **enabled** (either `DEV_MODE=true` or `DEV_MODE` unset/empty):

- `tripParser.parseTripFromNaturalText`:
  - Returns a stub `TripRequest` object (e.g., Kyoto, sightseeing, fixed budget).
- `itineraryGenerator.createItineraryOptions`:
  - Builds an itinerary using only `stationDataset.json` without calling OpenAI.

This lets you test the full LINE → webhook → reply pipeline without consuming OpenAI quota.

### Dev Mode Disabled

When dev mode is **disabled** (`DEV_MODE=false`):

- Real OpenAI calls are used for:
  - Parsing the user’s message into `TripRequest`.
  - Generating itinerary options from candidate stations.

You must have:

- A valid `OPENAI_API_KEY`
- Sufficient quota / billing on the OpenAI account

If quota is exhausted, the bot responds with a friendly error instead of crashing.

---

## Project Structure

    ├── main.py                # FastAPI app entrypoint + LINE webhook handler
    ├── lineWebhook.py         # LINE signature validation + event parsing helpers
    ├── tripParser.py          # Natural-language → TripRequest (with dev mode)
    ├── destinationSelector.py # Filters candidate stations from dataset
    ├── itineraryGenerator.py  # Builds itineraries (OpenAI or dev mode)
    ├── messageFormatter.py    # Formats replies + calls LINE Reply API
    ├── tripModels.py          # Dataclasses (TripRequest, StationInfo, Itinerary, etc.)
    ├── stationDataset.json    # Static station + POI dataset (Kyoto / Kansai)
    ├── README.md              # Project overview + generic quickstart
    ├── personalREADME.md      # Machine-specific setup notes (not for git)
    ├── .env.example           # Example env vars
    └── .gitignore             # Ignores venv, .env, caches, personal notes


---

## Prerequisites

- Python **3.11**
- A LINE **Messaging API** channel with:
  - Channel Secret
  - Channel Access Token
- **ngrok** (or equivalent tunneling tool) to expose `localhost:8000` as HTTPS
- (Optional but recommended) OpenAI API key with quota (`OPENAI_API_KEY`)

---

## Environment Variables

Create a `.env` file in the project root (same directory as `main.py`):

    # LINE credentials
    LINE_CHANNEL_SECRET=your_line_channel_secret
    LINE_CHANNEL_ACCESS_TOKEN=your_long_channel_access_token

    # OpenAI (required only when DEV_MODE=false)
    OPENAI_API_KEY=sk-...

    # Dev mode:
    # - true or empty/unset → dev mode enabled (no real OpenAI calls)
    # - false               → real OpenAI calls (requires quota)
    DEV_MODE=true

Notes:

- Leaving `DEV_MODE` empty or not setting it at all results in dev mode being treated as enabled.
- Set `DEV_MODE=false` only when you are ready to use real OpenAI requests.

---

## Generic Local Setup

### 1. Create and Activate Virtual Environment

From the project folder:

    cd /path/to/Train\ Roulette\ Line\ Bot
    python -m venv .venv

Activate:

- **Windows (PowerShell)**

    .\.venv\Scripts\Activate.ps1

- **macOS / Linux**

    source .venv/bin/activate

### 2. Install Dependencies

Inside the activated venv:

    python -m pip install --upgrade pip
    python -m pip install fastapi uvicorn "openai>=1.40.0" python-dotenv requests

### 3. Run the Server

    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env

You should see:

    INFO:     Loading environment from '.env'
    INFO:     Started server process [...]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

### 4. Health Check

Open a browser and visit:

    http://localhost:8000/health

Expected response:

    {"status": "healthy"}

---

## Expose to LINE via ngrok

1. In a **separate** terminal (server must stay running):

       ngrok http 8000

2. ngrok will show a forwarding URL similar to:

       Forwarding    https://example-subdomain.ngrok-free.dev -> http://localhost:8000

3. In **LINE Developers Console**:

   - Go to your **Messaging API** channel.
   - Open the **Messaging API** tab.
   - Set **Webhook URL** to:

         https://example-subdomain.ngrok-free.dev/webhook

   - Click **Verify** (should succeed if server + ngrok are running).
   - Turn **Use webhook** = **ON**.

4. In **LINE Official Account Manager**:

   - Disable:
     - Auto-reply messages
     - Greeting messages

So only this webhook responds to messages.

---

## Basic Interaction Flow

1. User sends a message (EN or JP) to the bot in LINE, for example:

       I'm at Kyoto Station, I have around 6000 yen, where can I go for a few hours? I've already been to Fushimi Inari and Arashiyama.

2. LINE sends a POST request to the `/webhook` endpoint on your server (via ngrok).

3. `main.py`:

   - Validates the request using `LINE_CHANNEL_SECRET`.
   - Extracts the text message and `replyToken`.
   - Logs:

         IncomingMessage: ...
         ParsedTripRequest: TripRequest(...)

   - Calls:
     - `parseTripFromNaturalText` → returns a `TripRequest`
     - `selectCandidateStations` → returns a list of `StationInfo`
     - `createItineraryOptions` → returns an `ItineraryResponse`
     - `formatItineraryForLine` → formats the reply as text
     - `createLineReply` → sends the reply back to LINE

4. The user sees 1–2 itineraries in the chat (dev-mode or real, depending on `DEV_MODE` and your OpenAI quota).

If OpenAI quota is exhausted (and dev mode is off), the bot sends a clear error message about API credit instead of crashing.

---

## Stopping and Restarting

- To stop the FastAPI server:

      Ctrl + C

  in the terminal where `uvicorn` is running.

- To stop ngrok:

      Ctrl + C

  in the terminal where `ngrok http 8000` is running.

- Closing the terminal window also kills the process, but using Ctrl+C is cleaner and avoids half-written logs.

To restart everything:

1. Open a new terminal, then:

       cd /path/to/Train\ Roulette\ Line\ Bot
       .\.venv\Scripts\Activate.ps1    # Windows, adjust if on macOS/Linux
       python -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env

2. Open another terminal:

       ngrok http 8000

3. Update the Webhook URL in LINE Developers if the ngrok HTTPS URL changed.

---

## Common Issues

**Webhook verify fails**

- Check:
  - Server is running (`uvicorn` shows "Application startup complete").
  - ngrok is running and forwarding to `http://localhost:8000`.
  - Webhook URL in LINE uses the current ngrok HTTPS URL and ends with `/webhook`.

**Bot not replying**

- Check the `uvicorn` terminal for:

      POST /webhook

  and any exception trace.
- Confirm `LINE_CHANNEL_SECRET` and `LINE_CHANNEL_ACCESS_TOKEN` are correct.
- Make sure you are using a **Messaging API** channel, not just a LINE Login channel.

**OpenAI errors**

- If quota is exhausted or the key is invalid and `DEV_MODE=false`, the bot responds with a human-readable error message.
- Set `DEV_MODE=true` to continue testing the LINE flow without OpenAI.
