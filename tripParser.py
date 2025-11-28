import json
import os

from openai import OpenAI

from tripModels import TripRequest

devModeValue = os.environ.get("DEV_MODE", "").lower()
isDevModeEnabled = True if devModeValue == "" else devModeValue == "true"

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def parseTripFromNaturalText(messageText: str) -> TripRequest:
    print(f"ParseTripInput: {messageText}")

    if isDevModeEnabled:
        print("ParseTripFromNaturalText: Dev mode enabled, returning stub TripRequest")
        return TripRequest(
            startStation="Kyoto",
            totalBudgetYen=5000,
            timeWindowHours=4.0,
            moodLabel="sightseeing",
            avoidPlaces=[],
            userLanguage="en"
        )

    systemPrompt = (
        "You receive a single message in English or Japanese about a train day trip in Japan. "
        "Extract the following information and output ONLY valid JSON with these exact keys: "
        "{"
        "\"startStation\": \"station name (string, empty if not found)\", "
        "\"totalBudgetYen\": 0, "
        "\"timeWindowHours\": 4.0, "
        "\"moodLabel\": \"sightseeing\", "
        "\"avoidPlaces\": [], "
        "\"userLanguage\": \"en\""
        "}. "
        "If any item is missing in the message, use reasonable defaults: "
        "timeWindowHours=4.0, moodLabel=\"sightseeing\", avoidPlaces=[]. "
        "userLanguage must be \"en\" or \"ja\"."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": messageText}
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )

    contentText = response.choices[0].message.content
    print(f"ParseTripRawJson: {contentText}")

    parsedJson = json.loads(contentText)

    tripRequest = TripRequest(
        startStation=parsedJson.get("startStation", ""),
        totalBudgetYen=parsedJson.get("totalBudgetYen", 0),
        timeWindowHours=float(parsedJson.get("timeWindowHours", 4.0)),
        moodLabel=parsedJson.get("moodLabel", "sightseeing"),
        avoidPlaces=parsedJson.get("avoidPlaces", []),
        userLanguage=parsedJson.get("userLanguage", "en")
    )

    print(f"ParseTripResult: {tripRequest}")
    return tripRequest
