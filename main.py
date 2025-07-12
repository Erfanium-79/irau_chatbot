# =================================================================
# main.py
# This file creates a FastAPI application to serve the chatbot.
# =================================================================

# =================================================================
# 1. IMPORTS
# All necessary libraries for the FastAPI app.
# =================================================================
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


# Import the chatbot_response function from your chatbot.py file
from chatbot import chatbot_response

# =================================================================
# 2. FASTAPI APP INITIALIZATION
# =================================================================
app = FastAPI(
    title="Chatbot API",
    description="An API to interact with the chatbot.",
    version="1.0.0"
)

# Add this middleware
origins = [
    "http://localhost",
    "http://localhost:3000", # Assuming the frontend runs on port 3000
    "https://www.iran-australia.com", # The production domain of the frontend
    "https://iran-australia.com",
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

# =================================================================
# 3. REQUEST AND RESPONSE MODELS
# =================================================================
class ChatRequest(BaseModel):
    """Request model for a user's message."""
    message: str

class ChatResponse(BaseModel):
    """Response model for the chatbot's reply."""
    reply: str

# =================================================================
# 4. API ENDPOINT
# =================================================================
@app.post("/chat/", response_model=ChatResponse)
async def chat_with_bot(request: ChatRequest):
    """
    This endpoint receives a user's message and returns the chatbot's response.
    """
    response_text = chatbot_response(request.message)
    return ChatResponse(reply=response_text)

# =================================================================
# 5. RUN THE APPLICATION
# To run this application, save it as main.py and run the following
# command in your terminal:
# uvicorn main:app --reload
# =================================================================
if __name__ == "__main__":
    # This will run the app on http://127.0.0.1:8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
