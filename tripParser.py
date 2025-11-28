import json
import os

from openai import OpenAI

from tripModels import TripRequest
from allowedStations import allowedStationNames

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

devModeValue = os.environ.get("DEV_MODE", "").lower()
isDevModeEnabled = True if devModeValue == "" else devModeValue == "true"


def parseTripFromNaturalText(messageText: str) -> TripRequest:
    if isDevModeEnabled:
        isJapaneseMessage = any(ord(character) > 127 for character in messageText)
        userLanguage = "ja" if isJapaneseMessage else "en"

        return TripRequest(
            startStation="Kyoto Station",
            totalBudgetYen=6000,
            timeWindowHours=4.0,
            moodLabel="sightseeing",
            avoidPlaces=[],
            userLanguage=userLanguage
        )

    stationListLines = "\n".join(f"- {stationName}" for stationName in allowedStationNames)

    systemPrompt = (
        "You receive a single free-form message in English or Japanese. "
        "The user is in Japan and is asking about going somewhere by train and what to do there. "
        "Your job is ONLY to normalize this into a structured trip request. "
        "You must respond with a single JSON object and nothing else.\n\n"
        "Allowed starting stations (canonical names) are:\n"
        f"{stationListLines}\n\n"
        "Rules for startStation:\n"
        "- If the user clearly indicates they are at or near one of these places, set startStation to that exact string.\n"
        "- Map variants (e.g. 'Kyoto', 'Kyoto eki', '京都', '京都駅') to 'Kyoto Station' if it is in the allowed list.\n"
        "- If a variant clearly refers to some other allowed station, map it to that allowed station.\n"
        "- If you cannot reasonably map the message to any allowed station, set startStation to an empty string \"\".\n"
        "- If the user is not asking about going somewhere or about a trip at all, set startStation to \"\".\n\n"
        "Rules for totalBudgetYen:\n"
        "- Infer the approximate budget for the whole outing in yen.\n"
        "- If the user says nothing about money, assume 6000.\n"
        "- If the user explicitly wants something as cheap as possible, you can choose a small budget like 1000–3000.\n\n"
        "Rules for timeWindowHours:\n"
        "- Infer how many hours they roughly have.\n"
        "- 'A few hours' → about 3.0 or 4.0.\n"
        "- 'Half day' → about 4.0.\n"
        "- 'Whole day' → about 8.0.\n"
        "- If not stated at all, default to 4.0.\n\n"
        "Rules for moodLabel:\n"
        "- Choose ONE of: 'sightseeing', 'nature', 'food', 'shopping', 'mixed', 'chaos'.\n"
        "- Temples, shrines, classic views → 'sightseeing'.\n"
        "- Parks, mountains, hiking, rivers → 'nature'.\n"
        "- Cafes, food, eating, drinking → 'food'.\n"
        "- Malls, shopping streets → 'shopping'.\n"
        "- If they want variety or do not care → 'mixed'.\n"
        "- If they explicitly want something wild, crowded, or chaotic → 'chaos'.\n\n"
        "Rules for avoidPlaces:\n"
        "- List stations or areas (by name) they say they already went to or want to avoid.\n"
        "- If they say 'I've already been to Fushimi Inari and Arashiyama', use ['Fushimi Inari', 'Arashiyama'].\n"
        "- If no avoid list is given, use an empty list [].\n\n"
        "Rules for userLanguage:\n"
        "- 'en' if the message is mostly English.\n"
        "- 'ja' if the message is mostly Japanese.\n\n"
        "Output format (IMPORTANT):\n"
        "- Output ONLY a single JSON object, no explanation, no markdown.\n"
        "- Use exactly these keys: startStation, totalBudgetYen, timeWindowHours, moodLabel, avoidPlaces, userLanguage.\n"
        "- avoidPlaces must always be a JSON array (possibly empty).\n"
    )

    userContent = f"User message:\n{messageText}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": userContent}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )

    parsedJson = json.loads(response.choices[0].message.content)

    return TripRequest(
        startStation=parsedJson.get("startStation", ""),
        totalBudgetYen=int(parsedJson.get("totalBudgetYen", 0)),
        timeWindowHours=float(parsedJson.get("timeWindowHours", 4.0)),
        moodLabel=parsedJson.get("moodLabel", "sightseeing"),
        avoidPlaces=parsedJson.get("avoidPlaces", []),
        userLanguage=parsedJson.get("userLanguage", "en")
    )
