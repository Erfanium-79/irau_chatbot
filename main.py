# =================================================================
# main.py (FINAL PRODUCTION VERSION v9.1 with Robust Handoff)
# =================================================================
import uvicorn
import os
import httpx
import logging
import redis
import json
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from chatbot import chatbot_response

# Configure logging
logging.basicConfig(level=logging.INFO)

# =================================================================
# 1. APP INITIALIZATION & CONFIGURATION
# =================================================================
app = FastAPI(
    title="Chatbot API for Goftino",
    description="An API for a stateful chatbot with automated transfer to/from human operators.",
    version="9.1.0"
)

# CORS middleware
origins = [
    "http://localhost", "http://localhost:3000",
    "https://www.iran-australia.com", "https://iran-australia.com",
    "https://www.goftino.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Goftino Configuration
GOFTINO_API_KEY = os.environ.get("GOFTINO_API_KEY")
OPERATOR_ID = os.environ.get("GOFTINO_OPERATOR_ID")  # The Chatbot's Operator ID
SECOND_OPERATOR_ID = "687c9153c7b2788949dda73c"      # The Human Operator's ID

# API URLs
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"
GOFTINO_TYPING_API_URL = "https://api.goftino.com/v1/operator_typing"
GOFTINO_TRANSFER_API_URL = "https://api.goftino.com/v1/transfer_chat"

# Redis Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

# =================================================================
# 2. HELPER FUNCTIONS
# =================================================================
async def transfer_chat(chat_id: str, from_operator: str, to_operator: str):
    if not all([GOFTINO_API_KEY, from_operator, to_operator]):
        logging.error("API Key or Operator IDs are missing for transfer!")
        return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "from_operator": from_operator, "to_operator": to_operator}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_TRANSFER_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Successfully initiated transfer for chat {chat_id} from {from_operator} to {to_operator}.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error transferring chat: {e.response.status_code} - {e.response.text}")

async def set_typing_status(chat_id: str, is_typing: bool):
    if not GOFTINO_API_KEY or not OPERATOR_ID: return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "operator_id": OPERATOR_ID, "typing_status": "true" if is_typing else "false"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(GOFTINO_TYPING_API_URL, json=payload, headers=headers)
        except httpx.HTTPStatusError as e:
            logging.error(f"Error setting typing status: {e.response.status_code}")

async def send_reply_to_goftino(chat_id: str, message: str):
    if not GOFTINO_API_KEY or not OPERATOR_ID: return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "message": message, "operator_id": OPERATOR_ID}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_SEND_API_URL, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logging.error(f"Error sending message to Goftino: {e.response.status_code} - {e.response.text}")

# =================================================================
# 3. MAIN WEBHOOK ENDPOINT (REFACTORED)
# =================================================================
@app.post("/chat/")
async def chat_with_bot(request: Request, background_tasks: BackgroundTasks):
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")
    event = webhook_data.get("event")
    
    # **KEY CHANGE**: Assume the webhook provides the current operator_id.
    # This key might be different (e.g., 'assigned_operator'); please check Goftino API docs.
    current_operator_id = data.get("operator_id")

    if not chat_id:
        return Response(status_code=204)

    # Load session from Redis, still needed for tracking transfer history
    session_json = redis_client.get(chat_id)
    session = json.loads(session_json) if session_json else {"is_transferred": False, "human_operator_id": None}

    # 1. Handle chat 'closed' event to transfer back to the bot
    if event == "chat_status_changed" and data.get("chat_status") == "closed":
        if session.get("is_transferred") and session.get("human_operator_id"):
            human_operator = session["human_operator_id"]
            logging.info(f"Chat {chat_id} was closed. Transferring back to bot from {human_operator}.")
            
            session["is_transferred"] = False
            session["human_operator_id"] = None
            redis_client.set(chat_id, json.dumps(session))

            background_tasks.add_task(transfer_chat, chat_id, from_operator=human_operator, to_operator=OPERATOR_ID)
        return Response(status_code=204)

    # 2. **ROBUST GUARD**: If chat is not assigned to our bot, ignore it.
    if current_operator_id and current_operator_id != OPERATOR_ID:
        logging.info(f"Chat {chat_id} is with operator {current_operator_id}, not bot ({OPERATOR_ID}). Ignoring.")
        return Response(status_code=204)
        
    # Remove the old guard that only checked the session. This new one is better.
    # if session.get("is_transferred"): ... (This is no longer needed here)

    # 3. Process new messages assigned to the bot
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if not user_message:
            return Response(status_code=204)

        # Ensure session is created if it's a new conversation
        if not session_json:
            redis_client.set(chat_id, json.dumps(session))

        await set_typing_status(chat_id, is_typing=True)
        response_text = chatbot_response(user_message)
        await set_typing_status(chat_id, is_typing=False)

        if response_text == -1:
            preamble_message = "متوجه شدم. لطفاً چند لحظه صبر کنید تا شما را به یک اپراتور انسانی وصل کنم."
            background_tasks.add_task(send_reply_to_goftino, chat_id, preamble_message)

            logging.info(f"Bot returned -1. Transferring chat {chat_id} to human operator: {SECOND_OPERATOR_ID}.")
            session["is_transferred"] = True
            session["human_operator_id"] = SECOND_OPERATOR_ID
            redis_client.set(chat_id, json.dumps(session))
            
            background_tasks.add_task(transfer_chat, chat_id, from_operator=OPERATOR_ID, to_operator=SECOND_OPERATOR_ID)
        else:
            background_tasks.add_task(send_reply_to_goftino, chat_id, response_text)

    return Response(status_code=204)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Iran-Australia Chatbot is running."}

# =================================================================
# 4. RUN THE APPLICATION
# =================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)