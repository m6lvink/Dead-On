import os
import requests
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from lineWebhook import validateLineSignature, parseLineEvents, extractMessageFromEvent
from tripFlow import generateTripResponse, chatSessions

# Fail Close security setup
allowed_env = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USERS = [x.strip() for x in allowed_env.split(",") if x.strip()]

if not ALLOWED_USERS:
    print("CRITICAL SECURITY WARNING: ALLOWED_USER_IDS is empty!")
    print("The bot will BLOCK ALL REQUESTS until you add your User ID to .env.")

# Scheduler
scheduler = BackgroundScheduler()

# Rate limiter (30 requests per minute per IP)
limiter = Limiter(key_func=get_remote_address)

def clear_chat_history():
    print(f"[{datetime.now()}] MAINTENANCE: Clearing all chat history...")
    chatSessions.clear()
    print("MAINTENANCE: Memory wiped.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(clear_chat_history, 'interval', hours=6)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - restrict to LINE domains only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://line.me", "https://api.line.me"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Logic for the linebot
def sendLineReply(replyToken: str, messageText: str) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/reply"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "replyToken": replyToken,
        "messages": [{"type": "text", "text": messageText}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"ERROR: Failed to send LINE reply: {e}")
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
        raise HTTPException(status_code=403, detail="Invalid signature")

    eventList = parseLineEvents(bodyBytes)

    for event in eventList:
        data = extractMessageFromEvent(event)
        if data is None:
            continue

        userText, replyToken, userId = data
        print(f"Received from {userId}: {userText}")

        # If list is empty OR user not in list, BLOCK. Prevent unauthorized access and costs
        if not ALLOWED_USERS or userId not in ALLOWED_USERS:
            print(f"SECURITY: Blocked unauthorized user {userId}")
            continue

        try:
            aiResponse = generateTripResponse(userId, userText)
            sendLineReply(replyToken, aiResponse)
            
        except Exception as e:
            print(f"Error: {str(e)}")
            sendLineReply(replyToken, "Sorry, I encountered an error processing your request.")

    return {"status": "ok"}
