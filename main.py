# =================================================================
# main.py (FINAL PRODUCTION VERSION v5.0)
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
    description="An API to interact with the chatbot via Goftino, now simplified.",
    version="5.0.0"
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

# This is the correct Send Message API URL from the documentation
GOFTINO_SEND_API_URL = "https://api.goftino.com/v1/send_message"

# =================================================================
# 2. HELPER FUNCTION TO SEND MESSAGES
# =================================================================

# In-memory dictionary to store session data for each chat.
chat_sessions = {}


async def send_reply_to_goftino(chat_id: str, message: str):
    """
    Sends a reply message to the Goftino "Send Message" API.
    """
    api_key = os.environ.get("GOFTINO_API_KEY")
    operator_id = os.environ.get("GOFTINO_OPERATOR_ID")

    if not api_key or not operator_id:
        logging.error("API Key or Operator ID is not set in environment variables!")
        return

    headers = {
        "Content-Type": "application/json",
        "goftino-key": api_key
    }

    payload = {
        "chat_id": chat_id,
        "message": message,
        "operator_id": operator_id
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
        # Extract user info from the webhook payload (e.g., from the 'sender' object)
        sender_info = data.get("sender", {})
        user_name = sender_info.get("name")
        user_phone = sender_info.get("phone")

        logging.info(f"New conversation for chat_id: {chat_id}. User: {user_name}, Phone: {user_phone}")
        
        # Create a new session and store the user's info from Goftino
        session = {
            "name": user_name,
            "phone_number": user_phone,
        }
        chat_sessions[chat_id] = session
        
        # The bot now sends a simple, direct welcome message.
        initial_prompt = "سلام! لطفا پیام خود را بنویسید."
        
        background_tasks.add_task(send_reply_to_goftino, chat_id, initial_prompt)
        
        # We have initiated the conversation. Stop processing here and wait for the user's reply.
        return Response(status_code=204)

    # For subsequent messages from the user, process them directly.
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        if user_message:
            logging.info(f"Processing message from existing chat {chat_id}: '{user_message}'")
            
            # Get the bot's response from the chatbot logic module.
            response_text = chatbot_response(user_message, session)
            
            # Send the response back to the user.
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
