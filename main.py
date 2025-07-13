# =================================================================
# main.py (PRODUCTION VERSION)
# This file creates a FastAPI application to serve the chatbot.
# =================================================================

# =================================================================
# 1. IMPORTS
# =================================================================
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import the chatbot_response function from your chatbot.py file
from chatbot import chatbot_response

# Configure logging
logging.basicConfig(level=logging.INFO)

# =================================================================
# 2. FASTAPI APP INITIALIZATION
# =================================================================
app = FastAPI(
    title="Chatbot API for Goftino",
    description="An API to interact with the chatbot via Goftino.",
    version="2.0.0"
)

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

# IMPORTANT: Get this key from your Goftino dashboard
# You should store this as an environment variable in Render for better security
GOFTINO_API_KEY = "apo4zfmz3642l50g1axxbwme42cbbe86df1f4208f72063b91ce2a3c829183fc7" 

# =================================================================
# 3. REQUEST AND RESPONSE MODELS
# =================================================================
class ChatResponse(BaseModel):
    """Response model for the chatbot's reply."""
    reply: str

# =================================================================
# 4. API ENDPOINT
# =================================================================
@app.post("/chat/")
async def chat_with_bot(request: Request):
    """
    This endpoint receives a webhook from Goftino, processes it, 
    and returns the chatbot's response.
    """
    # 1. Verify the request is coming from Goftino
    goftino_key = request.headers.get("goftino-key")
    if goftino_key != GOFTINO_API_KEY:
        logging.warning("Invalid API Key received.")
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Get the JSON body from the webhook
    webhook_data = await request.json()
    logging.info(f"Received webhook: {webhook_data}")

    event = webhook_data.get("event")
    data = webhook_data.get("data", {})

    # 3. Process the webhook only if it's a new message from a visitor
    if event == "new_message" and data.get("type") == "text" and data.get("sender", {}).get("from") == "visitor":
        user_message = data.get("content")
        
        if not user_message:
            logging.info("Ignored: Message content is empty.")
            return Response(status_code=204) # 204 No Content

        # 4. Get the chatbot's response
        logging.info(f"Processing message from visitor: {user_message}")
        response_text = chatbot_response(user_message)
        
        # 5. Return the response in the format Goftino expects
        # NOTE: The provided docs do not specify the response format. 
        # We are assuming Goftino expects a simple JSON with a 'reply' key.
        # If this does not work, the next step is to use the "Send Message" API.
        return ChatResponse(reply=response_text)
    else:
        # 6. If it's not a new message from a visitor, ignore it.
        # We return a 200 OK or 204 No Content response so Goftino knows we received it.
        logging.info(f"Ignored event '{event}' from sender '{data.get('sender', {}).get('from')}'.")
        return Response(status_code=204) # 204 No Content is best for "processed, nothing to return"

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Iran-Australia Chatbot is running."}

# =================================================================
# 5. RUN THE APPLICATION
# =================================================================
if __name__ == "__main__":
    # For local development, use "127.0.0.1". For Render, use "0.0.0.0".
    uvicorn.run(app, host="0.0.0.0", port=8000)