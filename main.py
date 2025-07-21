# =================================================================
# main.py (Stateless Version - No Redis)
# =================================================================
import uvicorn
import os
import httpx
import logging
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
    description="An API for a stateless chatbot with automated transfer to/from human operators.",
    version="10.0.0"
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
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")
    
    if not chat_id:
        logging.warning("Webhook received without a chat_id.")
        return Response(status_code=204)

    # Handle new messages from the user
    if event == "new_message" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        current_operator_id = data.get("operator_id")

        if not user_message or data.get("type") != "text":
            return Response(status_code=204) # Ignore non-text messages

        # --- THIS IS THE KEY CHANGE ---
        # Only respond if the message is assigned to the BOT.
        if current_operator_id != BOT_OPERATOR_ID:
            logging.info(f"Chat {chat_id} is assigned to operator {current_operator_id}. Bot will not intervene.")
            return Response(status_code=204)

        logging.info(f"Bot ({BOT_OPERATOR_ID}) is processing message for chat {chat_id}: '{user_message}'")
        
        await set_typing_status(chat_id, is_typing=True)
        response_text = chatbot_response(user_message)
        await set_typing_status(chat_id, is_typing=False)

        if response_text == -1:
            logging.info(f"Bot returned -1. Transferring chat {chat_id} to human operator: {HUMAN_OPERATOR_ID}.")
            
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