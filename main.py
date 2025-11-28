import json
from typing import List

from fastapi import FastAPI, Request, HTTPException

from lineWebhook import validateLineSignature, parseLineEvents, extractMessageFromEvent
from tripParser import parseTripFromNaturalText
from tripModels import StationInfo, POIInfo
from destinationSelector import selectCandidateStations
from itineraryGenerator import createItineraryOptions
from messageFormatter import formatItineraryForLine, createLineReply

app = FastAPI()


def loadStationDataset() -> List[StationInfo]:
    stationList = []
    with open("stationDataset.json", "r", encoding="utf-8") as stationFile:
        dataList = json.load(stationFile)
    for stationData in dataList:
        poiList = []
        for poiData in stationData.get("poiList", []):
            poiList.append(POIInfo(
                poiName=poiData.get("poiName", ""),
                poiType=poiData.get("poiType", "")
            ))
        stationInfo = StationInfo(
            stationName=stationData.get("stationName", ""),
            linkedStations=stationData.get("linkedStations", []),
            approxRoundTripCost=stationData.get("approxRoundTripCost", 0),
            approxTravelMinutesTotal=stationData.get("approxTravelMinutesTotal", 0),
            poiList=poiList
        )
        stationList.append(stationInfo)
    return stationList


stationDataset = loadStationDataset()


def findStationByName(stationName: str) -> bool:
    stationNameLower = stationName.lower()
    for stationInfo in stationDataset:
        if stationInfo.stationName.lower() == stationNameLower:
            return True
    return False


@app.post("/webhook")
async def webhookEndpoint(request: Request):
    headers = dict(request.headers)
    bodyBytes = await request.body()

    isValidSignature = validateLineSignature(headers, bodyBytes)
    if not isValidSignature:
        raise HTTPException(status_code=403, detail="Invalid signature")

    eventList = parseLineEvents(bodyBytes)

    for event in eventList:
        extractedData = extractMessageFromEvent(event)
        if extractedData is None:
            continue

        messageText, replyToken, userId = extractedData

        print(f"IncomingMessage: {messageText}")

        tripRequest = None

        try:
            tripRequest = parseTripFromNaturalText(messageText)

            print(f"ParsedTripRequest: {tripRequest}")

            if not tripRequest.startStation:
                englishMessage = "Please tell me your starting station (for example: I am at Kyoto Station)."
                japaneseMessage = "出発駅を教えてください（例：京都駅にいます）。"
                replyText = englishMessage if tripRequest.userLanguage == "en" else japaneseMessage
                createLineReply(replyToken, replyText)
                continue

            hasStation = findStationByName(tripRequest.startStation)
            if not hasStation:
                englishMessage = f"Start station '{tripRequest.startStation}' is not supported yet in this demo."
                japaneseMessage = f"出発駅「{tripRequest.startStation}」はこのデモではまだサポートされていません。"
                replyText = englishMessage if tripRequest.userLanguage == "en" else japaneseMessage
                createLineReply(replyToken, replyText)
                continue

            candidateStations = selectCandidateStations(tripRequest, stationDataset)
            if len(candidateStations) == 0:
                englishMessage = "No destinations found within your budget or time window. Try increasing your budget or time."
                japaneseMessage = "予算や時間の範囲内で行ける場所が見つかりませんでした。予算や時間を増やしてみてください。"
                replyText = englishMessage if tripRequest.userLanguage == "en" else japaneseMessage
                createLineReply(replyToken, replyText)
                continue

            itineraryResponse = createItineraryOptions(tripRequest, candidateStations)
            replyText = formatItineraryForLine(itineraryResponse, tripRequest.userLanguage)
            createLineReply(replyToken, replyText)

        except Exception as error:
            errorMessage = str(error)
            isJapaneseLanguage = any(ord(character) > 127 for character in messageText)

            if "insufficient_quota" in errorMessage:
                englishMessage = "Our planning engine is out of API credit right now. Please try again later."
                japaneseMessage = "現在APIの利用上限に達しています。時間をおいて再度お試しください。"
                replyText = japaneseMessage if isJapaneseLanguage else englishMessage
            else:
                englishMessage = f"Sorry, an error occurred: {errorMessage}"
                japaneseMessage = f"エラーが発生しました: {errorMessage}"
                replyText = japaneseMessage if isJapaneseLanguage else englishMessage

            print(f"ErrorInWebhook: {errorMessage}")
            createLineReply(replyToken, replyText)

    return {"status": "ok"}


@app.get("/health")
async def healthCheck():
    return {"status": "healthy"}
