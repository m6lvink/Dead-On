import base64
import hashlib
import hmac
import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Maximum field lengths for input validation
MAX_FIELD_LENGTHS = {
    "text": 10000,
    "replyToken": 256,
    "userId": 256,
}


def validateLineSignature(headers: Dict[str, Any], bodyBytes: bytes) -> bool:
    """
    Validate LINE webhook signature using HMAC-SHA256.
    Uses constant-time comparison to prevent timing attacks.
    """
    channelSecret = os.environ.get("LINE_CHANNEL_SECRET")
    if channelSecret is None:
        return False
        
    signature = headers.get("x-line-signature")
    if signature is None:
        return False
        
    hashObj = hmac.new(channelSecret.encode("utf-8"), bodyBytes, hashlib.sha256)
    calculatedSignature = base64.b64encode(hashObj.digest()).decode("utf-8")
    
    # Use constant-time compare to prevent timing attacks
    return hmac.compare_digest(signature, calculatedSignature)


def parseLineEvents(bodyBytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse LINE webhook event body.
    Returns empty list on any parsing errors.
    """
    try:
        bodyStr = bodyBytes.decode("utf-8")
        bodyJson = json.loads(bodyStr)
        events = bodyJson.get("events", [])
        # Validate events is a list
        if not isinstance(events, list):
            logger.warning("Invalid LINE events format: events is not a list")
            return list()
        return events
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug(f"Failed to parse LINE events: {e}")
        return list()
    except Exception as e:
        logger.error(f"Unexpected error parsing LINE events: {e}")
        return list()


def extractMessageFromEvent(event: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    """
    Extract message text, reply token, and user ID from a LINE event.
    Validates field lengths to prevent potential issues.
    Returns None if event is not a text message or validation fails.
    """
    # Validate event is a dictionary
    if not isinstance(event, dict):
        logger.debug("Invalid event format: not a dictionary")
        return None
        
    eventType = event.get("type")
    if eventType != "message":
        return None
        
    messageObj = event.get("message", {})
    if not isinstance(messageObj, dict):
        logger.debug("Invalid message format: not a dictionary")
        return None
        
    messageType = messageObj.get("type")
    if messageType != "text":
        return None
        
    text = messageObj.get("text", "")
    if not isinstance(text, str):
        logger.debug("Invalid text format: not a string")
        return None
        
    # Validate text length
    if len(text) > MAX_FIELD_LENGTHS["text"]:
        logger.warning(f"Message text exceeds max length: {len(text)} > {MAX_FIELD_LENGTHS['text']}")
        return None
        
    replyToken = event.get("replyToken", "")
    if not isinstance(replyToken, str):
        logger.debug("Invalid replyToken format: not a string")
        return None
        
    # Validate replyToken length
    if len(replyToken) > MAX_FIELD_LENGTHS["replyToken"]:
        logger.warning(f"Reply token exceeds max length: {len(replyToken)}")
        return None
        
    source = event.get("source", {})
    if not isinstance(source, dict):
        logger.debug("Invalid source format: not a dictionary")
        return None
        
    userId = source.get("userId", "")
    if not isinstance(userId, str):
        logger.debug("Invalid userId format: not a string")
        return None
        
    # Validate userId length
    if len(userId) > MAX_FIELD_LENGTHS["userId"]:
        logger.warning(f"User ID exceeds max length: {len(userId)}")
        return None
        
    return (text, replyToken, userId)
