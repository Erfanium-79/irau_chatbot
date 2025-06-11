# =================================================================
# 1. IMPORTS
# All necessary libraries for the Streamlit app.
# =================================================================
import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage
import os

# =================================================================
# 2. STREAMLIT PAGE CONFIGURATION
# Set the title and icon for your web application.
# =================================================================
st.set_page_config(page_title="ACME Inc. Support Chatbot", page_icon="🤖")
st.title("Welcome to ACME Inc. Support")
st.write("Our AI-powered chatbot is here to help you with your questions.")

# =================================================================
# 3. API KEY AND MODEL CONFIGURATION
# Securely load the API key from Streamlit's secrets management or user input.
# =================================================================
AVALAI_API_KEY = "aa-dhz3cYYm2mJ1LeowMpSDXfrRiy7jQjhUcaNDjN0FWw5Uk9uY"  # Initialize as empty

# Try to get the key from Streamlit's secrets.
try:
    AVALAI_API_KEY = st.secrets["AVALAI_API_KEY"]
    st.sidebar.success("✅ API Key loaded from secrets.")
except (FileNotFoundError, KeyError):
    st.sidebar.warning("API Key not found in secrets.")
    AVALAI_API_KEY = st.sidebar.text_input(
        "Enter your AvalAI API Key:", 
        type="password",
        help="You can find your API key on the AvalAI dashboard."
    )

# If the key is still not available, stop the app and wait for user input.
if not AVALAI_API_KEY:
    st.info("Please provide your AvalAI API key in the sidebar to continue.")
    st.stop()

# Set the environment variable for LangChain and display a success message.
os.environ["AVALAI_API_KEY"] = AVALAI_API_KEY
st.sidebar.success("✅ API Key configured.")


# Define the base URL for AvalAI
AVALAI_BASE_URL = "https://api.avalai.ir/v1"


# =================================================================
# 4. CACHED FUNCTIONS FOR LOADING MODELS AND DATA
# Use caching to avoid reloading models and data on every interaction.
# =================================================================
@st.cache_resource
def load_llm_and_embeddings():
    """Loads the LLM and embeddings models."""
    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=AVALAI_API_KEY,
            base_url=AVALAI_BASE_URL
        )
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=AVALAI_API_KEY,
            base_url=AVALAI_BASE_URL
        )
        return llm, embeddings
    except Exception as e:
        st.error(f"Failed to load models. Please check your API key and network. Error: {e}")
        return None, None

@st.cache_resource
def load_qa_chain(_llm, _embeddings):
    """Loads documents and creates the QA retrieval chain."""
    if _llm is None or _embeddings is None:
        return None
    try:
        faq_loader = TextLoader("data/faqs.csv", encoding='utf-8')
        service_loader = TextLoader("data/services.json", encoding='utf-8')
        info = TextLoader("data/info.md", encoding='utf-8')

        docs = faq_loader.load() + service_loader.load() + info.load()

        vectorstore = FAISS.from_documents(docs, _embeddings)
        retriever = vectorstore.as_retriever()

        qa_chain = RetrievalQA.from_chain_type(
            llm=_llm,
            chain_type="stuff",
            retriever=retriever
        )
        return qa_chain
    except FileNotFoundError:
        st.warning("⚠️ Data files not found. The FAQ handler will be limited.")
        return None
    except Exception as e:
        st.error(f"Error creating QA chain: {e}")
        return None

# Load the models and QA chain
llm, embeddings = load_llm_and_embeddings()
qa_chain = load_qa_chain(llm, embeddings)


# =================================================================
# 5. INTENT DETECTION AND HANDLERS
# These are the core logic functions from your original script.
# =================================================================
def detect_intent(user_input: str) -> str:
    """Classifies the intent of the user input."""
    if llm is None: return "unknown"
    prompt = f"""
You are an intent classifier. Classify the user input below into one of these categories:
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
        return intent_text.split(":")[-1].strip() if ":" in intent_text else intent_text
    except Exception as e:
        st.error(f"Intent detection failed: {e}")
        return "unknown"

def handle_greeting(query: str):
    result = qa_chain.invoke({"query": query})
    return "Hello! Welcome to ACME Inc. We offer cloud services, analytics, and more. How can I help you today?"+"\n" + result['result']

def handle_visitor_info(query: str):
    result = qa_chain.invoke({"query": query})
    return "It looks like you're new here! You can ask me about our services, pricing, or check out our free analytics tool."+"\n"+result['result']

def handle_faq_or_support(query: str):
    if not qa_chain:
        return "I'm sorry, my knowledge base is currently unavailable. I can still help with general queries."
    try:
        result = qa_chain.invoke({"query": query})
        return result['result']
    except Exception as e:
        return f"Sorry, I encountered an error retrieving the answer. {e}"

def handle_complaint(query: str):
    try:
        with open("complaints.log", "a") as f:
            f.write(f"User Complaint: {query}\n")
        return "I am sorry to hear that. I've logged your complaint, and our support team will review it shortly."
    except:
        return "I am sorry to hear that. I was unable to log your complaint, but please contact our support team directly."

def handle_chitchat(query: str):
    """Handles chitchat with a direct LLM call and adds a promotional message."""
    if llm is None:
        return "I'm not in the mood for chitchat right now, but I can help with our services!"
    try:
        # Get a direct response from the LLM for the chitchat
        response = llm.invoke([HumanMessage(content=query)])
        chitchat_response = response.content.strip()

        # Add a promotional message
        promotional_message = "\n\nBy the way, did you know you can supercharge your business with our cloud services and analytics tools? Ask me how!"

        return f"{chitchat_response}{promotional_message}"
    except Exception as e:
        st.error(f"Chitchat handling failed: {e}")
        return "I'd love to chat, but I'm having a bit of trouble thinking right now. Please ask me about our services instead."


def chatbot_response(user_input: str):
    """Routes user input to the correct handler based on intent."""
    intent = detect_intent(user_input)
    st.sidebar.info(f"Detected Intent: **{intent}**") # Display intent in the sidebar for debugging

    if intent == "greeting":
        return handle_greeting(user_input)
    elif intent == "visitor_info":
        return handle_visitor_info(user_input)
    elif intent == "faq":
        return handle_faq_or_support(user_input)
    elif intent == "complaint":
        return handle_complaint(user_input)
    elif intent == "chitchat":
        return handle_chitchat(user_input)
    else: # Handles 'chitchat' and 'unknown'
        return "I'm not sure how to help with that. Could you please rephrase or ask about our services, pricing, or support?"

# =================================================================
# 6. STREAMLIT CHAT INTERFACE
# Manages chat history and user interaction.
# =================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What can I help you with?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Get bot response
    response = chatbot_response(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
