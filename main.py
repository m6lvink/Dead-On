import os
import requests
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from lineWebhook import validateLineSignature, parseLineEvents, extractMessageFromEvent
from tripFlow import generateTripResponse, chatSessions

# Fail CLose security setup
allowed_env = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USERS = [x.strip() for x in allowed_env.split(",") if x.strip()]

if not ALLOWED_USERS:
    print("CRITICAL SECURITY WARNING: ALLOWED_USER_IDS is empty!")
    print("The bot will BLOCK ALL REQUESTS until you add your User ID to .env.")

# Schecduler
scheduler = BackgroundScheduler()

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

# Logic for the linebot
def sendLineReply(replyToken: str, messageText: str):
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
    
    requests.post(url, headers=headers, json=payload)

@app.api_route("/health", methods=["GET", "HEAD"])
async def healthCheck():
    return {"status": "healthy"}

@app.post("/webhook")
async def webhookEndpoint(request: Request):
    headers = dict(request.headers)
    bodyBytes = await request.body()

    if not validateLineSignature(headers, bodyBytes):
        raise HTTPException(status_code=403, detail="Invalid signature")

    eventList = parseLineEvents(bodyBytes)

    for event in eventList:
        data = extractMessageFromEvent(event)
        if data is None:
            continue

        userText, replyToken, userId = data
        print(f"Received from {userId}: {userText}")

        #  If list is empty OR user not in list, BLOCK. --> to prevent unauthorized access and it costs money
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
