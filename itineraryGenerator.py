import json
import os
from typing import List

from openai import OpenAI

from tripModels import TripRequest, StationInfo, ItineraryResponse, ItineraryOption, StopDetail, ActivityDetail

devModeValue = os.environ.get("DEV_MODE", "").lower()
isDevModeEnabled = True if devModeValue == "" else devModeValue == "true"

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def buildDevModeItinerary(tripRequest: TripRequest, candidateStations: List[StationInfo]) -> ItineraryResponse:
    if len(candidateStations) == 0:
        return ItineraryResponse(itineraries=[])

    stopList = []
    selectedStations = candidateStations[:2]

    for stationInfo in selectedStations:
        activityList = []
        poiPreviewList = stationInfo.poiList[:2]
        for poiInfo in poiPreviewList:
            descriptionEn = f"Visit {poiInfo.poiName} ({poiInfo.poiType}) near {stationInfo.stationName}."
            descriptionJp = f"{stationInfo.stationName}周辺の{poiInfo.poiType}スポット「{poiInfo.poiName}」を訪れます。"
            activityList.append(ActivityDetail(
                poiName=poiInfo.poiName,
                descriptionEn=descriptionEn,
                descriptionJp=descriptionJp
            ))
        stopList.append(StopDetail(
            stationName=stationInfo.stationName,
            activities=activityList
        ))

    estimatedCost = 0
    estimatedTimeMinutes = 0
    for stationInfo in selectedStations:
        estimatedCost += stationInfo.approxRoundTripCost
        estimatedTimeMinutes += stationInfo.approxTravelMinutesTotal

    itineraryOption = ItineraryOption(
        label="Dev mode sample itinerary",
        stops=stopList,
        estimatedTotalCostYen=estimatedCost,
        estimatedTotalTimeMinutes=estimatedTimeMinutes
    )

    return ItineraryResponse(itineraries=[itineraryOption])


def createItineraryOptions(tripRequest: TripRequest, candidateStations: List[StationInfo]) -> ItineraryResponse:
    if isDevModeEnabled:
        print("CreateItineraryOptions: Dev mode enabled, building local itinerary")
        return buildDevModeItinerary(tripRequest, candidateStations)

    candidateData = []
    for stationInfo in candidateStations:
        poiDataList = []
        for poiInfo in stationInfo.poiList:
            poiDataList.append({
                "poiName": poiInfo.poiName,
                "poiType": poiInfo.poiType
            })
        candidateData.append({
            "stationName": stationInfo.stationName,
            "approxRoundTripCost": stationInfo.approxRoundTripCost,
            "approxTravelMinutesTotal": stationInfo.approxTravelMinutesTotal,
            "poiList": poiDataList
        })

    requestPayload = {
        "tripRequest": {
            "startStation": tripRequest.startStation,
            "totalBudgetYen": tripRequest.totalBudgetYen,
            "timeWindowHours": tripRequest.timeWindowHours,
            "moodLabel": tripRequest.moodLabel,
            "avoidPlaces": tripRequest.avoidPlaces,
            "userLanguage": tripRequest.userLanguage
        },
        "candidateStations": candidateData
    }

    systemPrompt = (
        "You are a day-trip planner for train journeys in Japan. "
        "You will receive a JSON object with a tripRequest and a list of candidateStations. "
        "You must select up to two itineraries that respect: "
        "1) totalBudgetYen (stay within budget, but you can be slightly under), "
        "2) timeWindowHours (keep estimatedTotalTimeMinutes within that window), "
        "3) Only use stations and POIs from candidateStations. "
        "Output ONLY valid JSON with this exact format: "
        "{"
        "\"itineraries\": ["
        "{"
        "\"label\": \"short title\", "
        "\"stops\": ["
        "{"
        "\"stationName\": \"string\", "
        "\"activities\": ["
        "{"
        "\"poiName\": \"string\", "
        "\"descriptionEn\": \"string\", "
        "\"descriptionJp\": \"string\""
        "}"
        "]"
        "}"
        "], "
        "\"estimatedTotalCostYen\": 0, "
        "\"estimatedTotalTimeMinutes\": 0"
        "}"
        "]"
        "}. "
        "Descriptions must be concise but vivid, and descriptions should match the poiType where possible."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": json.dumps(requestPayload)}
        ],
        response_format={"type": "json_object"},
        temperature=0.6
    )

    contentText = response.choices[0].message.content
    print(f"ItineraryRawJson: {contentText}")

    parsedJson = json.loads(contentText)
    itineraryDataList = parsedJson.get("itineraries", [])

    itineraryList = []

    for itineraryData in itineraryDataList:
        stopList = []
        for stopData in itineraryData.get("stops", []):
            activityList = []
            for activityData in stopData.get("activities", []):
                activityList.append(ActivityDetail(
                    poiName=activityData.get("poiName", ""),
                    descriptionEn=activityData.get("descriptionEn", ""),
                    descriptionJp=activityData.get("descriptionJp", "")
                ))
            stopList.append(StopDetail(
                stationName=stopData.get("stationName", ""),
                activities=activityList
            ))

        itineraryOption = ItineraryOption(
            label=itineraryData.get("label", "Itinerary"),
            stops=stopList,
            estimatedTotalCostYen=int(itineraryData.get("estimatedTotalCostYen", 0)),
            estimatedTotalTimeMinutes=int(itineraryData.get("estimatedTotalTimeMinutes", 0))
        )
        itineraryList.append(itineraryOption)

    return ItineraryResponse(itineraries=itineraryList)
