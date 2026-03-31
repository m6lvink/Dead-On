import os
import requests
import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from lineWebhook import validateLineSignature, parseLineEvents, extractMessageFromEvent
from tripFlow import generateTripResponse, clear_chat_sessions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Fail Close security setup
allowed_env = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USERS = [x.strip() for x in allowed_env.split(",") if x.strip()]

if not ALLOWED_USERS:
    logger.warning("CRITICAL SECURITY WARNING: ALLOWED_USER_IDS is empty!")
    logger.warning("The bot will BLOCK ALL REQUESTS until you add your User ID to .env.")

# Scheduler
scheduler = BackgroundScheduler()

# Rate limiter (30 requests per minute per IP)
limiter = Limiter(key_func=get_remote_address)

def clear_chat_history():
    logger.info("MAINTENANCE: Clearing all chat history...")
    clear_chat_sessions()
    logger.info("MAINTENANCE: Memory wiped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(clear_chat_history, 'interval', hours=6)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# CORS - restrict to LINE domains only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://line.me", "https://api.line.me"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=[
        "Content-Type",
        "X-Line-Signature",
        "User-Agent",
        "Accept",
        "Accept-Encoding",
        "Connection",
    ],
)

# Constants for sanitization
MAX_LINE_MESSAGE_LENGTH = 5000  # LINE's max is higher but we limit for safety

def sanitizeLineMessage(text: str) -> str:
    """
    Sanitize message text for LINE API.
    Removes control characters and limits length.
    """
    if not text:
        return ""
    # Remove null bytes and most control characters, keep newlines/tabs
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    # Limit length
    return text[:MAX_LINE_MESSAGE_LENGTH]

def sendLineReply(replyToken: str, messageText: str) -> bool:
    """
    Send a reply message to LINE.
    Message text is sanitized before sending.
    """
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/reply"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Sanitize message before sending
    safe_message = sanitizeLineMessage(messageText)
    
    payload = {
        "replyToken": replyToken,
        "messages": [{"type": "text", "text": safe_message}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("Failed to send LINE reply", exc_info=True)
        return False

@app.api_route("/health", methods=["GET", "HEAD"])
async def healthCheck():
    return {"status": "healthy"}

@app.post("/webhook")
@limiter.limit("30/minute")
async def webhookEndpoint(request: Request):
    headers = dict(request.headers)
    bodyBytes = await request.body()
    
    # Body size limit (1MB)
    if len(bodyBytes) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")

    if not validateLineSignature(headers, bodyBytes):
        logger.warning("SECURITY: Invalid LINE signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")

    eventList = parseLineEvents(bodyBytes)

    for event in eventList:
        data = extractMessageFromEvent(event)
        if data is None:
            continue

        userText, replyToken, userId = data
        logger.info(f"Received message from user")

        # If list is empty OR user not in list, BLOCK. Prevent unauthorized access and costs
        if not ALLOWED_USERS or userId not in ALLOWED_USERS:
            logger.warning(f"SECURITY: Blocked unauthorized user access attempt")
            continue

        try:
            aiResponse = generateTripResponse(userId, userText)
            sendLineReply(replyToken, aiResponse)
            
        except Exception:
            # Log full error internally but don't expose details to user
            logger.error("Error processing user request", exc_info=True)
            sendLineReply(replyToken, "Sorry, I encountered an error processing your request.")

    return {"status": "ok"}
