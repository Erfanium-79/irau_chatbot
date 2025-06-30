# =================================================================
# streamlit_app.py
# This file creates a Streamlit web interface for the chatbot.
# It loads the pre-computed vector store and uses the chatbot logic.
# =================================================================

import streamlit as st
import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage

# =================================================================
# 0. STREAMLIT PAGE CONFIGURATION (MUST BE FIRST)
# =================================================================
# This must be the very first Streamlit command called in your script.
st.set_page_config(page_title="ACME Inc. Chatbot", page_icon="🤖")

# =================================================================
# 1. CONFIGURATION AND INITIALIZATION
# This section sets up API keys and initializes models.
# =================================================================

# Set your AvalAI API key from environment variables
# Ensure you have AVALAI_API_KEY set in your environment
# For local testing, you can uncomment and set it directly, but for production, use env vars.
# os.environ["AVALAI_API_KEY"] = "aa-dhz3cYYm2mJ1LeowMpSDXfrRiy7jQjhUcaNDjN0FWw5Uk9uY"

AVALAI_BASE_URL = "https://api.avalai.ir/v1"

# Initialize variables to hold LLM and QA chain
llm = None
embeddings = None
qa_chain = None
initialization_successful = False # Flag to track overall initialization status

# Check if the API key is available and initialize models
if "AVALAI_API_KEY" not in os.environ:
    st.error("❌ Error: AVALAI_API_KEY environment variable not set.")
    st.info("Please set your AvalAI API key to run this Streamlit app.")
else:
    try:
        # Initialize ChatOpenAI for both general use and intent detection
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=os.environ["AVALAI_API_KEY"],
            base_url=AVALAI_BASE_URL
        )

        # Initialize OpenAIEmbeddings, pointing to the AvalAI base_url
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.environ["AVALAI_API_KEY"],
            base_url=AVALAI_BASE_URL
        )

        # =================================================================
        # 2. LOAD VECTOR STORE AND SETUP RETRIEVER/QA CHAIN
        # This section loads the pre-computed FAISS vector store.
        # =================================================================
        vector_store_path = "faiss_index" # This must match the path used in embedder.py

        if os.path.exists(vector_store_path):
            try:
                # Load the local FAISS index
                # allow_dangerous_deserialization=True is needed for some FAISS versions
                vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
                retriever = vectorstore.as_retriever()
                st.success(f"Vectorstore loaded successfully from '{vector_store_path}'.")

                # Create the QA chain for handling FAQs
                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",  # "stuff" is a common chain type for this purpose
                    retriever=retriever
                )
                st.success("QA chain created successfully.")
                initialization_successful = True # Set flag to True if all goes well

            except Exception as e:
                st.error(f"❌ Error loading vectorstore from '{vector_store_path}': {e}")
                st.warning("Please ensure 'embedder.py' has been run to create the FAISS index.")
                retriever = None
                qa_chain = None # Ensure qa_chain is None if vectorstore isn't loaded
        else:
            st.warning(f"⚠️ Warning: Vectorstore not found at '{vector_store_path}'.")
            st.info("Please run 'embedder.py' first in your terminal to create the FAISS index.")
            retriever = None
            qa_chain = None # Ensure qa_chain is None if vectorstore isn't loaded

    except Exception as e:
        st.error(f"❌ An error occurred during model or embedding initialization: {type(e).__name__}: {e}") # Display actual error
        st.info("Please check your AvalAI API key, base URL, and internet connection.")
        llm = None
        embeddings = None


# =================================================================
# 3. INTENT DETECTION FUNCTION
# This function uses the initialized LLM to classify user intent.
# =================================================================
@st.cache_data(show_spinner=False) # Hide spinner for this internal function
def detect_intent(user_input: str) -> str:
    """Classifies the intent of the user input."""
    if llm is None:
        return "unknown" # Cannot detect intent without LLM
    prompt = f"""
You are an intent classifier. Classify the intent of the user input below into one of these:
- greeting
- faq
- complaint
- visitor_info
- chitchat
- unknown

Input: "{user_input}"
Intent:"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        intent_text = response.content.strip()
        if ":" in intent_text:
            return intent_text.split(":")[-1].strip()
        else:
            return intent_text
    except Exception as e:
        # st.error(f"Error detecting intent: {e}") # Avoid showing this repeatedly in chat
        return "unknown"

# =================================================================
# 4. INTENT HANDLERS
# These functions define the specific actions for each detected intent.
# =================================================================
# Updated handle_greeting based on user's provided code
def handle_greeting(query: str):
    """Handles greeting intent, potentially enhanced with info from QA chain."""
    base_response = "Hello! Welcome to ACME Inc. We offer cloud services, analytics, and more. How can I help you today?"
    if qa_chain is None:
        return base_response + "\n\n(Note: Knowledge base unavailable to provide more context for greeting.)"
    try:
        result = qa_chain.invoke({"query": query})
        return base_response + "\n" + result['result']
    except Exception as e:
        st.error(f"Error enhancing greeting with FAQ: {e}")
        return base_response + "\n\n(Note: Failed to retrieve additional context for greeting.)"

# Updated handle_visitor_info based on user's provided code
def handle_visitor_info(query: str):
    """Handles visitor info intent, potentially enhanced with info from QA chain."""
    base_response = "Looks like it's your first time here! You can try our free analytics tool or learn more about our email hosting."
    if qa_chain is None:
        return base_response + "\n\n(Note: Knowledge base unavailable to provide more context for visitor info.)"
    try:
        result = qa_chain.invoke({"query": query})
        return base_response + "\n" + result['result']
    except Exception as e:
        st.error(f"Error enhancing visitor info with FAQ: {e}")
        return base_response + "\n\n(Note: Failed to retrieve additional context for visitor info.)"


def handle_faq_or_support(query: str):
    if qa_chain is None:
        return "I'm sorry, my knowledge base is currently unavailable. Please make sure the data files and vector store are properly set up."
    try:
        result = qa_chain.invoke({"query": query})
        return result['result']
    except Exception as e:
        st.error(f"Error retrieving FAQ answer: {e}")
        return "I encountered an issue while trying to find an answer. Please try rephrasing your question."

def handle_complaint(query: str):
    # In a real application, you'd send this to a ticketing system or database
    try:
        with open("complaints.log", "a") as f:
            f.write(f"User Complaint: {query}\n")
        return "I am sorry to hear that. I've logged your complaint and someone from our support team will reach out shortly."
    except Exception as e:
        st.error(f"Error logging complaint: {e}")
        return "I apologize, I could not log your complaint at this moment. Please try again later."


# =================================================================
# 5. MAIN CHATBOT PIPELINE
# This function connects intent detection to the appropriate handler.
# =================================================================
def chatbot_response(user_input: str):
    """The main function that routes user input to the correct handler."""
    if not initialization_successful:
        return "I am currently unable to respond due to an initialization error. Please check the messages above for details."

    intent = detect_intent(user_input)
    st.session_state.messages.append({"role": "bot_debug", "content": f"(Intent Detected: {intent})"}) # For debugging

    if intent == "greeting":
        return handle_greeting(user_input) # Pass user_input to handle_greeting
    elif intent == "visitor_info":
        return handle_visitor_info(user_input) # Pass user_input to handle_visitor_info
    elif intent == "faq":
        return handle_faq_or_support(user_input)
    elif intent == "complaint":
        return handle_complaint(user_input)
    else: # Handles 'chitchat' and 'unknown'
        return "I'm not sure how to help with that yet. Try asking a question about our services or pricing."

# =================================================================
# 6. STREAMLIT APP UI
# This section defines the layout and interaction for the chatbot dashboard.
# =================================================================

st.title("🤖 ACME Inc. Support Chatbot")
st.write("Ask me anything about ACME Inc.'s services, FAQs, or even lodge a complaint!")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    elif message["role"] == "assistant":
        with st.chat_message("assistant"):
            st.markdown(message["content"])
    elif message["role"] == "bot_debug":
        # Display debug messages in a distinct way, maybe smaller text or italic
        st.markdown(f"<small><i>{message['content']}</i></small>", unsafe_allow_html=True)


# Accept user input
if user_query := st.chat_input("Type your message here..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Get chatbot response
    with st.spinner("Thinking..."):
        # The initialization_successful flag ensures we don't try to use uninitialized models
        response = chatbot_response(user_query)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)

# Optional: Clear chat history button
if st.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()

