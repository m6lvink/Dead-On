import os
import re
import time
import random
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Tuple
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from tripModels import TripConstraints
from stationService import getStationByName, findNearbyStations
import json_repair

# Setup Gemini
apiKey = os.environ.get("GEMINI_API_KEY")
client = None
if apiKey is not None and len(apiKey) > 0:
    client = genai.Client(api_key=apiKey)
else:
    print("CRITICAL WARNING: GEMINI_API_KEY is missing")

# Config
MAX_CHAT_SESSIONS = int(os.environ.get("MAX_CHAT_SESSIONS", "1000"))
MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "2000"))

# Blocked patterns for prompt injection protection
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

# Retry helper
def retry_api_call(func, *args, retries=3, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"DEBUG: Hit Rate Limit (429). Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                raise e
    raise Exception("API Failed after max retries")

# Input sanitization to prevent prompt injection
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

# Conversation Memory with LRU eviction
chatSessions: OrderedDict[str, object] = OrderedDict()

def evictOldestSession():
    if len(chatSessions) > 0:
        oldestKey = next(iter(chatSessions))
        del chatSessions[oldestKey]
        print(f"DEBUG: Evicted oldest chat session: {oldestKey}")

def get_or_create_chat(userId: str):
    if client is None: 
        raise Exception("Gemini API Key missing")
    
    # Evict oldest if at limit
    if len(chatSessions) >= MAX_CHAT_SESSIONS:
        evictOldestSession()
    
    if userId not in chatSessions:
        chatSessions[userId] = client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=(
                    "You are a helpful Japanese Travel Conductor. "
                    "You remember previous messages. "
                    "If the user rejects a location, suggest a DIFFERENT option. "
                    "CRITICAL FORMATTING RULES:\n"
                    "1. Do NOT use markdown bolding (**text**) or italics. Output plain text only.\n"
                    "2. At the very end of your response, output a Google Maps Search link for the recommended place.\n"
                    "   Format: https://www.google.com/maps/search/?api=1&query=PlaceName"
                )
            )
        )
    
    # Move to end (most recently used)
    chatSessions.move_to_end(userId)
    return chatSessions[userId]

def parseUserMessage(messageText: str) -> Tuple[Optional[TripConstraints], float]:
    if client is None: 
        raise Exception("API Key missing")

    systemPrompt = (
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
    
    try:
        response = retry_api_call(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=messageText,
            config=types.GenerateContentConfig(
                system_instruction=systemPrompt,
                response_mime_type="application/json",
                temperature=0.1
            )
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
    
    # Sanitize input before processing
    try:
        messageText = sanitizeUserInput(messageText)
    except ValueError as e:
        print(f"SECURITY: Blocked message: {e}")
        return "Sorry, I cannot process that message. Please try a different request."
    
    chat = get_or_create_chat(userId)
    constraints, radiusKm = parseUserMessage(messageText)

    if constraints is None:
        resp = retry_api_call(chat.send_message, messageText)
        return resp.text.replace("**", "")

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
        response = retry_api_call(chat.send_message, fullPrompt)
        return response.text.replace("**", "").replace("__", "")
    except Exception as e:
        print(f"Chat Error: {e}")
        return "I'm a bit overloaded right now. Please try again in a moment."
