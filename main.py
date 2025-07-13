# =================================================================
# main.py
# This file creates a FastAPI application to serve the chatbot.
# =================================================================

# =================================================================
# 1. IMPORTS
# All necessary libraries for the FastAPI app.
# =================================================================
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict


# Import the chatbot_response function from your chatbot.py file
from chatbot import chatbot_response

# =================================================================
# 2. FASTAPI APP INITIALIZATION
# =================================================================
app = FastAPI(
    title="Chatbot API",
    description="An API to interact with the chatbot.",
    version="1.0.1"
)

# Add this middleware
origins = [
    "http://localhost",
    "http://localhost:3000", # Assuming the frontend runs on port 3000
    "https://www.iran-australia.com", # The production domain of the frontend
    "https://iran-australia.com",
    "https://www.goftino.com", # Add Goftino's domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your chatbot routes and logic go here
@app.get("/")
def read_root():
    return {"Hello": "World"}

GOFTINO_API_KEY = "apo4zfmz3642l50g1axxbwme42cbbe86df1f4208f72063b91ce2a3c829183fc7"

# =================================================================
# 3. REQUEST AND RESPONSE MODELS
# =================================================================
# Goftino will likely send a more complex JSON object.
# We'll use a generic model to accept any JSON from Goftino.
class GoftinoWebhookRequest(BaseModel):
    # This allows the model to accept any structure
    data: Dict[str, Any] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    """Response model for the chatbot's reply."""
    reply: str

# =================================================================
# 4. API ENDPOINT
# =================================================================
@app.post("/chat/", response_model=ChatResponse)
async def chat_with_bot(request: Request):
    """
    This endpoint receives a user's message from Goftino and returns the chatbot's response.
    """
    # 1. Verify the request is coming from Goftino
    goftino_key = request.headers.get("goftino-key")
    if goftino_key != GOFTINO_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Get the JSON body from the request
    webhook_data = await request.json()

    # !!! IMPORTANT !!!
    # 3. Extract the user's message from the Goftino webhook data.
    # The structure of the JSON sent by Goftino is not public.
    # You will need to inspect the logs of your application to see the exact structure.
    # For example, the message might be in a field like: webhook_data['message']['text']
    # I am assuming the message is in a 'message' field for this example.
    # You will need to update this line based on what you see in your logs.
    print(f"Received from Goftino: {webhook_data}") # This will print the full data to your Render logs
    user_message = webhook_data.get("message", "No message found")


    # 4. Get the chatbot's response
    response_text = chatbot_response(user_message)

    # 5. Return the response
    return ChatResponse(reply=response_text)


@app.get("/")
def read_root():
    return {"Hello": "This is the Iran-Australia Chatbot for Goftino."}

# =================================================================
# 5. RUN THE APPLICATION
# =================================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
