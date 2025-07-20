# =================================================================
# main.py (FINAL PRODUCTION VERSION v7.0 with State Management)
# =================================================================
import uvicorn
import os
import httpx
import logging
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from chatbot import chatbot_response

# Configure logging to see outputs in Render
logging.basicConfig(level=logging.INFO)

# =================================================================
# 1. APP INITIALIZATION & CONFIGURATION
# =================================================================
app = FastAPI(
    title="Chatbot API for Goftino",
    description="An API to interact with the chatbot via Goftino, with stateful chat transfer.",
    version="7.0.0"
)

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://www.iran-australia.com",
    "https://iran-australia.com",
    "https://www.goftino.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the Goftino API key from environment variables for security
GOFTINO_API_KEY = os.environ.get("GOFTINO_API_KEY")
OPERATOR_ID = os.environ.get("GOFTINO_OPERATOR_ID")
SECOND_OPERATOR_ID = "687c9153c7b2788949dda73c"

# API URLs from the Goftino documentation
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"
GOFTINO_TYPING_API_URL = "https://api.goftino.com/v1/operator_typing"
GOFTINO_TRANSFER_API_URL = "https://api.goftino.com/v1/transfer_chat"

# In-memory dictionary to store session data for each chat.
# For production at scale, consider a persistent store like Redis.
chat_sessions = {}

# =================================================================
# 2. HELPER FUNCTIONS
# =================================================================

async def transfer_chat_to_operator(chat_id: str):
    """
    Transfers the chat from the bot operator to a human operator.
    """
    if not all([GOFTINO_API_KEY, OPERATOR_ID, SECOND_OPERATOR_ID]):
        logging.error("API Key or Operator IDs are not set for transfer!")
        return

    headers = {
        "Content-Type": "application/json",
        "goftino-key": GOFTINO_API_KEY
    }
    payload = {
        "chat_id": chat_id,
        "from_operator": OPERATOR_ID,
        "to_operator": SECOND_OPERATOR_ID
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_TRANSFER_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Successfully transferred chat {chat_id} to operator {SECOND_OPERATOR_ID}.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error transferring chat: {e.response.status_code} - {e.response.text}")

async def set_typing_status(chat_id: str, is_typing: bool):
    """
    Sends a request to Goftino to show or hide the "operator is typing" animation.
    """
    if not GOFTINO_API_KEY or not OPERATOR_ID:
        logging.error("API Key or Operator ID is not set for typing status!")
        return

    headers = { "Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY }
    payload = { "chat_id": chat_id, "operator_id": OPERATOR_ID, "typing_status": "true" if is_typing else "false" }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(GOFTINO_TYPING_API_URL, json=payload, headers=headers)
        except httpx.HTTPStatusError as e:
            logging.error(f"Error setting typing status: {e.response.status_code}")

async def send_reply_to_goftino(chat_id: str, message: str):
    """
    Sends a reply message to the Goftino "Send Message" API.
    """
    if not GOFTINO_API_KEY or not OPERATOR_ID:
        logging.error("API Key or Operator ID is not set in environment variables!")
        return

    headers = { "Content-Type": "application/json", "goftino-key": GOFTINO_API_KEY }
    payload = { "chat_id": chat_id, "message": message, "operator_id": OPERATOR_ID }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_SEND_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Successfully sent reply to chat_id {chat_id}.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error sending message to Goftino: {e.response.status_code} - {e.response.text}")

# =================================================================
# 3. MAIN WEBHOOK ENDPOINT
# =================================================================
@app.post("/chat/")
async def chat_with_bot(request: Request, background_tasks: BackgroundTasks):
    """
    This webhook manages the entire chat lifecycle:
    1. Creates a session for new chats.
    2. Disables the bot if the chat has been transferred.
    3. Processes messages and transfers to a human if the bot is unsure.
    """
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")
    event = webhook_data.get("event")

    if not chat_id:
        return Response(status_code=204)

    # [MODIFIED] Get or create a session to track chat state
    if chat_id not in chat_sessions:
        logging.info(f"New conversation started with chat_id: {chat_id}.")
        chat_sessions[chat_id] = {"is_transferred": False}
    
    session = chat_sessions[chat_id]

    # [NEW] If chat has been transferred, the bot should do nothing.
    if session.get("is_transferred"):
        logging.info(f"Chat {chat_id} is already transferred. Bot will not respond.")
        return Response(status_code=204)

    # Process new text messages from the user
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if not user_message:
            return Response(status_code=204)

        logging.info(f"Processing message from chat {chat_id}: '{user_message}'")
        
        await set_typing_status(chat_id, is_typing=True)
        response_text = chatbot_response(user_message)
        await set_typing_status(chat_id, is_typing=False)

        # [MODIFIED] Decide whether to reply or transfer the chat
        if response_text == -1:
            logging.info(f"Bot returned -1. Transferring chat {chat_id} to a human operator.")
            session["is_transferred"] = True  # Mark the session as transferred
            background_tasks.add_task(transfer_chat_to_operator, chat_id)
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