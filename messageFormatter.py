import os
import requests
from tripModels import ItineraryResponse

def formatItineraryForLine(itineraryResponse: ItineraryResponse, userLanguage: str) -> str:
    if len(itineraryResponse.itineraries) == 0:
        if userLanguage == "ja":
            return "申し訳ございません。条件に合う目的地が見つかりませんでした。予算や時間を調整してみてください。"
        else:
            return "Sorry, I couldn't find any destinations matching your criteria. Try adjusting your budget or time window."
    
    replyLines = []
    
    for idx, itinerary in enumerate(itineraryResponse.itineraries):
        if idx > 0:
            replyLines.append("\n" + "="*30 + "\n")
        
        replyLines.append(f"{itinerary.label}\n")
        
        routeStations = [stop.stationName for stop in itinerary.stops]
        routeString = " → ".join(routeStations)
        replyLines.append(f"Route: {routeString}\n")
        
        if userLanguage == "ja":
            replyLines.append(f"予算: 約{itinerary.estimatedTotalCostYen}円\n")
            replyLines.append(f"所要時間: 約{itinerary.estimatedTotalTimeMinutes}分\n\n")
        else:
            replyLines.append(f"Budget: ~¥{itinerary.estimatedTotalCostYen}\n")
            replyLines.append(f"Time: ~{itinerary.estimatedTotalTimeMinutes} mins\n\n")
        
        for stop in itinerary.stops:
            replyLines.append(f"{stop.stationName}\n")
            for activity in stop.activities:
                description = activity.descriptionJp if userLanguage == "ja" else activity.descriptionEn
                replyLines.append(f"• {activity.poiName}: {description}\n")
            replyLines.append("\n")
    
    return "".join(replyLines).strip()

def createLineReply(replyToken: str, replyText: str) -> bool:
    lineChannelAccessToken = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    lineReplyUrl = "https://api.line.me/v2/bot/message/reply"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {lineChannelAccessToken}"
    }
    
    payload = {
        "replyToken": replyToken,
        "messages": [
            {
                "type": "text",
                "text": replyText
            }
        ]
    }
    
    response = requests.post(lineReplyUrl, headers=headers, json=payload)
    return response.status_code == 200