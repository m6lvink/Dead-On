import os
import re
import random
from typing import Optional, Tuple
from tripModels import TripConstraints
from stationService import getStationByName, findNearbyStations
import json_repair

from llm.client import UnifiedLLMClient

llm_client = UnifiedLLMClient(
    gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
    deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL"),
    max_chat_sessions=int(os.environ.get("MAX_CHAT_SESSIONS", "1000"))
)

if not llm_client.is_available():
    print("CRITICAL WARNING: No LLM providers are available. Check your API keys.")

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "2000"))

BLOCKED_PATTERNS = [
    r'ignore\s+(all\s+)?(previous\s+)?instructions?',
    r'system\s+prompt',
    r'you\s+are\s+now',
    r'dan\s+mode',
    r'jailbreak',
    r'do\s+anything\s+now',
    r'ignore\s+constraints',
    r'developer\s+mode',
    r'root\s+access',
]

PARSING_SYSTEM_PROMPT = (
    "Extract travel constraints.\n\n"
    "1. startStationName: \n"
    "   - Landmark (e.g. 'Dotonbori') -> NEAREST STATION (Kanji).\n"
    "   - 'Osaka' (city) -> isVague=True.\n"
    "   - 'Kyoto' -> '京都'.\n"
    "2. moodLabel: 'food', 'nature', 'shopping', 'date', 'drinking'.\n"
    "3. totalBudgetYen: Default 3000.\n"
    "4. timeWindowHours: Default 3.0.\n"
    "5. searchRadiusKm: \n"
    "   - 'stay in', 'don't leave', 'walking' -> 1.5.\n"
    "   - 'food'/'drinking' -> max 5.0.\n"
    "   - Default 20.0.\n"
    "6. userLanguage: 'en' or 'ja'.\n"
    "Output strictly valid JSON."
)

CHAT_SYSTEM_PROMPT = (
    "You are a helpful Japanese Travel Conductor. "
    "You remember previous messages. "
    "If the user rejects a location, suggest a DIFFERENT option. "
    "CRITICAL FORMATTING RULES:\n"
    "1. Do NOT use markdown bolding (**text**) or italics. Output plain text only.\n"
    "2. At the very end of your response, output a Google Maps Search link for the recommended place.\n"
    "   Format: https://www.google.com/maps/search/?api=1&query=PlaceName"
)

def sanitizeUserInput(messageText: str) -> str:
    if not messageText:
        raise ValueError("Empty message")

    if len(messageText) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message too long: {len(messageText)} chars")

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, messageText, re.IGNORECASE):
            print(f"SECURITY: Blocked potential prompt injection: {pattern}")
            raise ValueError("Potentially malicious input detected")

    return messageText.strip()


def parseUserMessage(messageText: str) -> Tuple[Optional[TripConstraints], float]:
    if not llm_client.is_available():
        raise Exception("No LLM providers are available")

    try:
        response = llm_client.generate_content(
            model="gemini-2.5-flash",
            contents=messageText,
            system_instruction=PARSING_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
            retries=3,
            delay=2
        )

        data = json_repair.loads(response.text)

        constraints = TripConstraints(
            startStationName=data.get("startStationName", ""),
            totalBudgetYen=int(data.get("totalBudgetYen", 3000)),
            timeWindowHours=float(data.get("timeWindowHours", 3.0)),
            moodLabel=data.get("moodLabel", "exploration"),
            userLanguage=data.get("userLanguage", "en"),
            isVague=bool(data.get("isVague", False))
        )
        radiusKm = float(data.get("searchRadiusKm", 20.0))
        return constraints, radiusKm

    except Exception as e:
        print(f"DEBUG: Parse Error: {e}")
        return None, 20.0


def generateTripResponse(userId: str, messageText: str) -> str:
    print(f"DEBUG: Processing message for {userId}: {messageText}")

    try:
        messageText = sanitizeUserInput(messageText)
    except ValueError as e:
        print(f"SECURITY: Blocked message: {e}")
        return "Sorry, I cannot process that message. Please try a different request."

    constraints, radiusKm = parseUserMessage(messageText)

    chat = llm_client.get_or_create_chat(
        user_id=userId,
        model="gemini-2.5-flash",
        system_instruction=CHAT_SYSTEM_PROMPT,
        temperature=0.3
    )

    if constraints is None:
        try:
            resp = llm_client.send_chat_message(
                user_id=userId,
                message=messageText,
                model="gemini-2.5-flash",
                system_instruction=CHAT_SYSTEM_PROMPT,
                temperature=0.3
            )
            return resp.text.replace("**", "").replace("__", "")
        except Exception as e:
            print(f"Chat Error: {e}")
            return "I'm a bit overloaded right now. Please try again in a moment."

    contextInfo = ""

    if constraints.startStationName and not constraints.isVague:
        startRecord = getStationByName(constraints.startStationName)
        if startRecord:
            print(f"DEBUG: Search Radius: {radiusKm}km around {startRecord.name}")
            candidates = findNearbyStations(startRecord, radiusKm)

            if len(candidates) > 8:
                candidates = random.sample(candidates, 8)

            if candidates:
                contextInfo = (
                    f"\n[SYSTEM DATA: User is at {startRecord.name}. "
                    f"Valid stations within {radiusKm}km: {', '.join(candidates)}. "
                    "Recommend a specific spot near one of these.]"
                )
            else:
                contextInfo = f"\n[SYSTEM DATA: No stations found within {radiusKm}km of {startRecord.name}. Warn the user.]"

    fullPrompt = f"{messageText}\n{contextInfo}"

    try:
        response = llm_client.send_chat_message(
            user_id=userId,
            message=fullPrompt,
            model="gemini-2.5-flash",
            system_instruction=CHAT_SYSTEM_PROMPT,
            temperature=0.3
        )
        return response.text.replace("**", "").replace("__", "")
    except Exception as e:
        print(f"Chat Error: {e}")
        return "I'm a bit overloaded right now. Please try again in a moment."
