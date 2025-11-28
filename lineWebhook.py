import base64
import hashlib
import hmac
import json
import os
from typing import List, Dict, Any, Optional, Tuple

def validateLineSignature(headers: Dict[str, Any], bodyBytes: bytes) -> bool:
    channelSecret = os.environ.get("LINE_CHANNEL_SECRET")
    if channelSecret is None:
        return False
        
    signature = headers.get("x-line-signature")
    if signature is None:
        return False
        
    hashObj = hmac.new(channelSecret.encode("utf-8"), bodyBytes, hashlib.sha256)
    calculatedSignature = base64.b64encode(hashObj.digest()).decode("utf-8")
    
    return signature == calculatedSignature

def parseLineEvents(bodyBytes: bytes) -> List[Dict[str, Any]]:
    try:
        bodyStr = bodyBytes.decode("utf-8")
        bodyJson = json.loads(bodyStr)
        return bodyJson.get("events", [])
    except:
        return list()

def extractMessageFromEvent(event: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    eventType = event.get("type")
    if eventType != "message":
        return None
        
    messageObj = event.get("message", {})
    messageType = messageObj.get("type")
    if messageType != "text":
        return None
        
    text = messageObj.get("text", "")
    replyToken = event.get("replyToken", "")
    source = event.get("source", {})
    userId = source.get("userId", "")
    
    return (text, replyToken, userId)