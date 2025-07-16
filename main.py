# =================================================================
# main.py (FINAL PRODUCTION VERSION v5.1 with Typing Indicator)
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
    description="An API to interact with the chatbot via Goftino, now with typing indicator.",
    version="5.1.0"
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


# API URLs from the Goftino documentation
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"
# [NEW] Added the URL for the typing status endpoint
GOFTINO_TYPING_API_URL = "https://api.goftino.com/v1/operator_typing"

# =================================================================
# 2. HELPER FUNCTIONS TO SEND MESSAGES & STATUS
# =================================================================

# In-memory dictionary to store session data for each chat.
chat_sessions = {}


# [NEW] Helper function to set the typing status in Goftino
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
    It welcomes the user and immediately processes their message.
    """
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})
    chat_id = data.get("chat_id")

    if not chat_id:
        return Response(status_code=204)
    
    session = chat_sessions.get(chat_id)

    # If this is the first time we see this user, create a session and welcome them.
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

    # [MODIFIED] For subsequent messages, handle the typing indicator
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if user_message:
            logging.info(f"Processing message from existing chat {chat_id}: '{user_message}'")
            
            # 1. Show "operator is typing..." animation
            await set_typing_status(chat_id, is_typing=True)
            
            # 2. Get the bot's response. The typing animation is active during this process.
            response_text = chatbot_response(user_message)
            
            # 3. Stop the "typing..." animation just before sending the reply.
            await set_typing_status(chat_id, is_typing=False)

            # 4. Send the final response back to the user in a background task.
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