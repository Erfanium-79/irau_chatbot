# =================================================================
# main.py (FINAL PRODUCTION VERSION v6.0 with Chat Transfer)
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
    description="An API to interact with the chatbot via Goftino, with typing indicator and chat transfer.",
    version="6.0.0"
)

# Add CORS middleware to allow requests from your frontend and Goftino
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
SECOND_OPERATOR_ID = "68726fa2d79ebf4c3130a5a6" # The ID of the operator to transfer to

# API URLs from the Goftino documentation
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"
GOFTINO_TYPING_API_URL = "https://api.goftino.com/v1/operator_typing"
# [NEW] Added the URL for the chat transfer endpoint
GOFTINO_TRANSFER_API_URL = "https://api.goftino.com/v1/transfer_chat"

# =================================================================
# 2. HELPER FUNCTIONS TO SEND MESSAGES, STATUS & TRANSFERS
# =================================================================

# In-memory dictionary to store session data for each chat.
chat_sessions = {}

# [NEW] Helper function to transfer the chat to another operator
async def transfer_chat_to_operator(chat_id: str):
    """
    Transfers the chat from the bot operator (from_operator) to a human operator (to_operator).
    """
    if not all([GOFTINO_API_KEY, OPERATOR_ID, SECOND_OPERATOR_ID]):
        logging.error("API Key, Operator ID, or Second Operator ID is not set!")
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

    headers = {
        "Content-Type": "application/json",
        "goftino-key": GOFTINO_API_KEY
    }

    payload = {
        "chat_id": chat_id,
        "operator_id": OPERATOR_ID,
        "typing_status": "true" if is_typing else "false"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_TYPING_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Set typing status to {is_typing} for chat_id {chat_id}.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error setting typing status: {e.response.status_code} - {e.response.text}")


async def send_reply_to_goftino(chat_id: str, message: str):
    """
    Sends a reply message to the Goftino "Send Message" API.
    """
    if not GOFTINO_API_KEY or not OPERATOR_ID:
        logging.error("API Key or Operator ID is not set in environment variables!")
        return

    headers = {
        "Content-Type": "application/json",
        "goftino-key": GOFTINO_API_KEY
    }

    payload = {
        "chat_id": chat_id,
        "message": message,
        "operator_id": OPERATOR_ID
    }

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
    This is the main webhook that receives all events from Goftino.
    It welcomes the user and processes their message, transferring if necessary.
    """
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")

    if not chat_id:
        return Response(status_code=204)
    
    session = chat_sessions.get(chat_id)

    if session is None:
        sender_info = data.get("sender", {})
        user_name = sender_info.get("name")
        user_phone = sender_info.get("phone")

        logging.info(f"New conversation for chat_id: {chat_id}. User: {user_name}, Phone: {user_phone}")
        
        session = {
            "name": user_name,
            "phone_number": user_phone,
        }
        chat_sessions[chat_id] = session
        
        initial_prompt = "سلام! لطفا پیام خود را بنویسید."
        
        background_tasks.add_task(send_reply_to_goftino, chat_id, initial_prompt)
        
        return Response(status_code=204)

    # [MODIFIED] Handle new messages with transfer logic
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if user_message:
            logging.info(f"Processing message from existing chat {chat_id}: '{user_message}'")
            
            # 1. Show "operator is typing..." animation
            await set_typing_status(chat_id, is_typing=True)
            
            # 2. Get the bot's response.
            response_text = chatbot_response(user_message)
            
            # 3. Stop the "typing..." animation before replying or transferring.
            await set_typing_status(chat_id, is_typing=False)

            # 4. If bot returns -1, transfer the chat. Otherwise, send the response.
            if response_text == -1:
                logging.info(f"Bot returned -1. Transferring chat {chat_id} to a human operator.")
                # Add the transfer task to the background
                background_tasks.add_task(transfer_chat_to_operator, chat_id)
            else:
                # Add the reply task to the background
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