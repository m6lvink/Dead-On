import os
import re
import random
import unicodedata
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse
from tripModels import TripConstraints
from stationService import getStationByName, findNearbyStations
import json_repair

from llm.client import UnifiedLLMClient

# Configure logging
logger = logging.getLogger(__name__)

llm_client = UnifiedLLMClient(
    gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
    deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL"),
    max_chat_sessions=int(os.environ.get("MAX_CHAT_SESSIONS", "1000"))
)


def clear_chat_sessions():
    """Clear all chat sessions from the LLM client."""
    llm_client.clear_chat_sessions()

if not llm_client.is_available():
    logger.warning("CRITICAL: No LLM providers are available. Check your API keys.")

MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "2000"))

# Expanded blocked patterns for prompt injection detection
BLOCKED_PATTERNS = [
    # Original patterns
    r'ignore\s+(all\s+)?(previous\s+)?instructions?',
    r'system\s+prompt',
    r'you\s+are\s+now',
    r'dan\s+mode',
    r'jailbreak',
    r'do\s+anything\s+now',
    r'ignore\s+constraints',
    r'developer\s+mode',
    r'root\s+access',
    # Additional patterns for enhanced protection
    r'(?i)(?:ignore|disregard|forget)\s+(?:previous|above|all)',
    r'(?i)(?:system|admin|developer|operator)\s+(?:prompt|instruction|mode)',
    r'(?i)(?:bypass|override|disable)\s+(?:filter|restriction|constraint)',
    r'(?i)(?:pretend|act\s+as|roleplay|simulate)\s+(?:hacker|admin|developer)',
    r'(?i)(?:DAN|STAN|DUDE|Mongo\s+Tom|Developer\s+Mode)',  # Known jailbreak personas
    r'<\s*/?\s*system\s*>',  # XML-style injection
    r'\{\{.*?\}\}',  # Template injection patterns
    r'(?:```|`)[\s\S]*?(?:system|prompt|instruction)',  # Code block injection
    r'(?i)(?:new|different)\s+(?:instructions|persona|role)',
    r'(?i)(?:translate|convert)\s+(?:to|into)\s+(?:hex|base64|binary)',
]

# Google Maps URL validation pattern
GOOGLE_MAPS_PATTERN = re.compile(
    r'^https://www\.google\.com/maps/search/\?api=1&query=[\w\s\-%]+$'
)

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


def normalize_for_security(text: str) -> str:
    """
    Normalize text to prevent bypass via Unicode tricks.
    Normalizes Unicode (NFKC) and removes zero-width characters.
    """
    # Normalize Unicode (NFKC)
    text = unicodedata.normalize('NFKC', text)
    # Remove zero-width characters
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    # Convert common homoglyphs (Cyrillic to Latin)
    text = text.replace('\u0430', 'a')  # Cyrillic 'а' -> Latin 'a'
    text = text.replace('\u043E', 'o')  # Cyrillic 'о' -> Latin 'o'
    text = text.replace('\u0435', 'e')  # Cyrillic 'е' -> Latin 'e'
    text = text.replace('\u0441', 'c')  # Cyrillic 'с' -> Latin 'c'
    text = text.replace('\u0440', 'p')  # Cyrillic 'р' -> Latin 'p'
    text = text.replace('\u0445', 'x')  # Cyrillic 'х' -> Latin 'x'
    return text


def validate_google_maps_url(url: str) -> bool:
    """
    Validate that URL is a legitimate Google Maps search URL.
    Prevents malicious redirects in LLM output.
    """
    if not url:
        return True  # No URL is acceptable
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            return False
        if parsed.netloc not in ('www.google.com', 'google.com'):
            return False
        return bool(GOOGLE_MAPS_PATTERN.match(url))
    except Exception:
        return False


def sanitize_llm_output(text: str) -> str:
    """
    Sanitize LLM output by validating any URLs.
    Removes or replaces invalid/malicious URLs.
    """
    # Extract URLs and validate them
    url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
    
    def replace_invalid_url(match):
        url = match.group(0)
        if validate_google_maps_url(url):
            return url
        logger.warning(f"SECURITY: Removed invalid URL from LLM output: {url[:50]}...")
        return '[Link removed for security]'
    
    return url_pattern.sub(replace_invalid_url, text)


def sanitizeUserInput(messageText: str) -> str:
    """
    Sanitize and validate user input.
    Checks for prompt injection attempts and validates length.
    """
    if not messageText:
        raise ValueError("Empty message")

    if len(messageText) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message too long: {len(messageText)} chars")

    # Normalize text to prevent Unicode bypass
    normalized = normalize_for_security(messageText)

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            logger.warning(f"SECURITY: Blocked potential prompt injection attempt")
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

    except Exception:
        logger.debug("Parse Error in user message", exc_info=True)
        return None, 20.0


def generateTripResponse(userId: str, messageText: str) -> str:
    logger.debug(f"Processing message for user")

    try:
        messageText = sanitizeUserInput(messageText)
    except ValueError:
        logger.warning(f"SECURITY: Blocked message due to validation failure")
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
            # Sanitize LLM output before returning
            output = resp.text.replace("**", "").replace("__", "")
            return sanitize_llm_output(output)
        except Exception:
            logger.error("Chat error in fallback response", exc_info=True)
            return "I'm a bit overloaded right now. Please try again in a moment."

    contextInfo = ""

    if constraints.startStationName and not constraints.isVague:
        startRecord = getStationByName(constraints.startStationName)
        if startRecord:
            logger.debug(f"Search Radius: {radiusKm}km around {startRecord.name}")
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
        # Sanitize LLM output before returning
        output = response.text.replace("**", "").replace("__", "")
        return sanitize_llm_output(output)
    except Exception:
        logger.error("Chat error in main response", exc_info=True)
        return "I'm a bit overloaded right now. Please try again in a moment."
