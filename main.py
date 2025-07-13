# =================================================================
# main.py (FINAL PRODUCTION VERSION v4.0)
# =================================================================
import uvicorn
import os
import httpx
import logging
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from chatbot import chatbot_response

# Configure logging to see outputs in Render
logging.basicConfig(level=logging.INFO)

# =================================================================
# 1. APP INITIALIZATION & CONFIGURATION
# =================================================================
app = FastAPI(
    title="Chatbot API for Goftino",
    description="An API to interact with the chatbot via Goftino.",
    version="4.0.0"
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
async def send_reply_to_goftino(chat_id: str, message: str):
    """
    Sends a reply message to the Goftino "Send Message" API.
    """
    if not GOFTINO_API_KEY:
        logging.error("GOFTINO_API_KEY is not set!")
        return

    headers = {
        "Content-Type": "application/json",
        "goftino-key": GOFTINO_API_KEY
    }

    # This payload structure is based on the documentation you provided.
    # NOTE: The 'operator_id' field is omitted. See the note below.
    payload = {
        "chat_id": chat_id,
        "message": message
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GOFTINO_SEND_API_URL, json=payload, headers=headers)
            response.raise_for_status()  # Raises an exception for 4XX or 5XX status codes
            logging.info(f"Successfully sent reply to chat_id {chat_id}. Response: {response.json()}")
        except httpx.HTTPStatusError as e:
            logging.error(f"Error sending message to Goftino: {e.response.status_code} - {e.response.text}")

# =================================================================
# 3. MAIN WEBHOOK ENDPOINT
# =================================================================
@app.post("/chat/")
async def chat_with_bot(request: Request, background_tasks: BackgroundTasks):
    """
    This is the main webhook that receives all events from Goftino.
    """
    # goftino_key = request.headers.get("goftino-key")
    # if goftino_key != GOFTINO_API_KEY:
    #     raise HTTPException(status_code=403, detail="Invalid API Key")

    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})

    # Process the message only if it's a new text message from a user
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "user":
        user_message = data.get("content")
        chat_id = data.get("chat_id")

        if user_message and chat_id:
            logging.info(f"Processing message from user for chat_id {chat_id}")
            response_text = chatbot_response(user_message)

            # Add the reply task to the background.
            # This allows us to send the 204 response immediately.
            background_tasks.add_task(send_reply_to_goftino, chat_id, response_text)

    # Acknowledge the webhook immediately with a 204 No Content response
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