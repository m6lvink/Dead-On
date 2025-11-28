import hmac
import hashlib
import base64
import json
import os
from typing import Dict, List, Optional
from tripModels import TripRequest

def validateLineSignature(headers: Dict[str, str], bodyBytes: bytes) -> bool:
    lineChannelSecret = os.environ.get("LINE_CHANNEL_SECRET")
    signatureHeader = headers.get("x-line-signature", "")
    
    hash = hmac.new(
        lineChannelSecret.encode("utf-8"),
        bodyBytes,
        hashlib.sha256
    )
    expectedSignature = base64.b64encode(hash.digest()).decode("utf-8")
    
    return hmac.compare_digest(signatureHeader, expectedSignature)

def parseLineEvents(bodyBytes: bytes) -> List[Dict]:
    bodyData = json.loads(bodyBytes.decode("utf-8"))
    return bodyData.get("events", [])

def extractMessageFromEvent(event: Dict) -> Optional[tuple]:
    if event.get("type") != "message":
        return None
    
    if event.get("message", {}).get("type") != "text":
        return None
    
    messageText = event.get("message", {}).get("text", "")
    replyToken = event.get("replyToken", "")
    userId = event.get("source", {}).get("userId", "")
    
    if not messageText or not replyToken:
        return None
    
    return (messageText, replyToken, userId)

def handleLineWebhook(headers: Dict[str, str], bodyBytes: bytes) -> Dict:
    isValidSignature = validateLineSignature(headers, bodyBytes)
    if not isValidSignature:
        return {"status": "error", "message": "Invalid signature"}
    
    eventList = parseLineEvents(bodyBytes)
    
    processedCount = 0
    for event in eventList:
        extractedData = extractMessageFromEvent(event)
        if extractedData is None:
            continue
        
        messageText, replyToken, userId = extractedData
        processedCount += 1
    
    return {"status": "ok", "processed": processedCount}