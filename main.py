# =================================================================
# main.py (FINAL PRODUCTION VERSION v9.3 with URL-based Redis Connection)
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

# Configure logging to provide detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =================================================================
# 1. APP INITIALIZATION & CONFIGURATION
# =================================================================
app = FastAPI(
    title="Chatbot API for Goftino",
    description="An API for a stateful chatbot with automated transfer to/from human operators.",
    version="9.3.0"
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
GOFTINO_API_KEY = os.environ.get("GOFTINO_API_KEY", "YOUR_GOFTINO_API_KEY")
BOT_OPERATOR_ID = os.environ.get("GOFTINO_OPERATOR_ID", "YOUR_BOT_OPERATOR_ID")  # The Chatbot's Operator ID
HUMAN_OPERATOR_ID = "687c9153c7b2788949dda73c"      # The Human Operator's ID

# API URLs
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"
GOFTINO_TYPING_API_URL = "https://api.goftino.com/v1/operator_typing"
GOFTINO_TRANSFER_API_URL = "https://api.goftino.com/v1/transfer_chat"

# ### CHANGE ### - Simplified Redis configuration to use a single URL
# This is more reliable and easier to configure in a production environment.
REDIS_URL = os.environ.get("REDIS_URL")

# Create a Redis client instance
redis_client = None
if REDIS_URL:
    try:
        # Use from_url to connect using the single connection string
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Ping the server to check the connection
        redis_client.ping()
        logging.info("Successfully connected to Redis using the provided URL.")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Could not connect to Redis using the provided URL: {e}")
        redis_client = None
else:
    logging.error("REDIS_URL environment variable not set. Redis connection not established.")


# =================================================================
# 2. HELPER FUNCTIONS
# =================================================================
async def transfer_chat(chat_id: str, to_operator: str):
    """Transfers a chat to a specified operator."""
    if not all([GOFTINO_API_KEY, to_operator]):
        logging.error("API Key or target Operator ID are missing for transfer!")
        return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "to_operator": to_operator}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_TRANSFER_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Successfully initiated transfer for chat {chat_id} to operator {to_operator}.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error transferring chat: {e.response.status_code} - {e.response.text}")

async def set_typing_status(chat_id: str, is_typing: bool):
    """Sets the bot's typing status in the chat."""
    if not all([GOFTINO_API_KEY, BOT_OPERATOR_ID]): return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "operator_id": BOT_OPERATOR_ID, "typing_status": "true" if is_typing else "false"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(GOFTINO_TYPING_API_URL, json=payload, headers=headers)
        except httpx.HTTPStatusError as e:
            logging.error(f"Error setting typing status: {e.response.status_code}")

async def send_reply_to_goftino(chat_id: str, message: str):
    """Sends a message from the bot to the user via Goftino."""
    if not all([GOFTINO_API_KEY, BOT_OPERATOR_ID]): return
    headers = {"Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY}
    payload = {"chat_id": chat_id, "message": message, "operator_id": BOT_OPERATOR_ID}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_SEND_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Sent message to chat {chat_id}: '{message}'")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error sending message to Goftino: {e.response.status_code} - {e.response.text}")

# =================================================================
# 3. MAIN WEBHOOK ENDPOINT
# =================================================================
@app.post("/chat/")
async def chat_webhook(request: Request, background_tasks: BackgroundTasks):
    if not redis_client:
        logging.error("Redis is not available. Cannot process request.")
        return Response(status_code=503, content="Service Unavailable: Redis connection failed.")

    webhook_data = await request.json()
    logging.info(f"Received webhook: {json.dumps(webhook_data, indent=2)}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")
    
    if not chat_id:
        logging.warning("Webhook received without a chat_id.")
        return Response(status_code=204)

    # Load session state from Redis
    session_key = f"chat_session:{chat_id}"
    session_json = redis_client.get(session_key)
    session = json.loads(session_json) if session_json else {"is_with_human": False}

    # --- Event Handling Logic ---

    # 1. Handle chat 'closed' event to reset the state
    if event == "chat_status_changed" and data.get("chat_status") == "closed":
        closing_operator = data.get("operator_id")
        logging.info(f"Chat {chat_id} was closed by operator {closing_operator}.")
        
        if session.get("is_with_human"):
            logging.info(f"Resetting state for chat {chat_id}. Next message will go to the bot.")
            session["is_with_human"] = False
            redis_client.set(session_key, json.dumps(session))
        return Response(status_code=204)

    # 2. Handle new messages from the user
    if event == "new_message" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if not user_message or data.get("type") != "text":
            return Response(status_code=204)

        if session.get("is_with_human"):
            logging.info(f"Chat {chat_id} is with a human. Bot is ignoring the message.")
            return Response(status_code=204)

        logging.info(f"Bot is processing message for chat {chat_id}: '{user_message}'")
        
        await set_typing_status(chat_id, is_typing=True)
        response_text = chatbot_response(user_message)
        await set_typing_status(chat_id, is_typing=False)

        if response_text == -1:
            logging.info(f"Bot returned -1. Transferring chat {chat_id} to human operator: {HUMAN_OPERATOR_ID}.")
            
            session["is_with_human"] = True
            redis_client.set(session_key, json.dumps(session))
            
            preamble_message = "متوجه شدم. لطفاً چند لحظه صبر کنید تا شما را به یک اپراتور انسانی وصل کنم."
            background_tasks.add_task(send_reply_to_goftino, chat_id, preamble_message)
            background_tasks.add_task(transfer_chat, chat_id, to_operator=HUMAN_OPERATOR_ID)
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
