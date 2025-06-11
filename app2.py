# =================================================================
# 1. CORRECTED IMPORTS
# These now point to the new packages you installed and are combined.
# =================================================================
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA  # <-- ADDED for the QA chain
from langchain.text_splitter import CharacterTextSplitter
from langchain.schema import HumanMessage
import os

# =================================================================
# 2. YOUR API KEY AND MODEL INITIALIZATION
# Make sure your API key is set correctly and base_url is specified.
# All model and embedding initializations now use AvalAI's endpoint.
# =================================================================
# It's recommended to use environment variables for security.
# Replace "your-avalai-api-key" with your actual AvalAI API key.
os.environ["AVALAI_API_KEY"] = "aa-dhz3cYYm2mJ1LeowMpSDXfrRiy7jQjhUcaNDjN0FWw5Uk9uY"

# Define the base URL for AvalAI
AVALAI_BASE_URL = "https://api.avalai.ir/v1"

# Initialize qa_chain as None. It will be created later if data is available.
qa_chain = None

# Check if the API key is available
if "AVALAI_API_KEY" not in os.environ:
    print("❌ Error: AVALAI_API_KEY environment variable not set.")
    print("Please set your AvalAI API key to run this script.")
else:
    print("AvalAI API key found. Initializing models and embeddings...")
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
        # 3. DATA LOADING, RETRIEVER, AND QA CHAIN SETUP
        # This section loads documents and sets up the vectorstore and QA chain.
        # =================================================================
        print("Loading documents and setting up vectorstore...")
        try:
            faq_loader = TextLoader("data/faqs.csv")
            service_loader = TextLoader("data/services.json")

            docs = faq_loader.load() + service_loader.load()

            vectorstore = FAISS.from_documents(docs, embeddings)
            retriever = vectorstore.as_retriever()
            print("Documents loaded and vectorstore created successfully.")

            # Create the QA chain for handling FAQs
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",  # "stuff" is a common chain type for this purpose
                retriever=retriever
            )
            print("QA chain created successfully.")

        except FileNotFoundError:
            print("⚠️ Warning: Data files 'data/faqs.csv' or 'data/services.json' not found.")
            print("The FAQ and support handler will not be able to answer questions.")
            retriever = None

        # =================================================================
        # 4. INTENT DETECTION FUNCTION
        # This function uses the initialized LLM to classify user intent.
        # =================================================================
        def detect_intent(user_input: str) -> str:
            """Classifies the intent of the user input."""
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
            response = llm.invoke([HumanMessage(content=prompt)])
            intent_text = response.content.strip()
            if ":" in intent_text:
                return intent_text.split(":")[-1].strip()
            else: 
                return intent_text
        # =================================================================
        # 5. INTENT HANDLERS
        # These functions define the specific actions for each detected intent.
        # =================================================================
        def handle_greeting():
            return "Hello! Welcome to ACME Inc. We offer cloud services, analytics, and more. Can I help you get started?"

        def handle_visitor_info():
            return "Looks like it's your first time here! You can try our free analytics tool or learn more about our email hosting."

        def handle_faq_or_support(query: str):
            if not qa_chain:
                return "I'm sorry, my knowledge base is currently unavailable. Please make sure the data files are present."
            # Use .invoke which is the modern way to run chains. The result is a dictionary.
            result = qa_chain.invoke({"query": query})
            return result['result']

        def handle_complaint(query: str):
            # Log to file or DB
            with open("complaints.log", "a") as f:
                f.write(f"User Complaint: {query}\n")
            return "I am sorry to hear that. I've logged your complaint and someone from our support team will reach out shortly."

        # =================================================================
        # 6. MAIN CHATBOT PIPELINE
        # This function connects intent detection to the appropriate handler.
        # =================================================================
        def chatbot_response(user_input: str):
            """The main function that routes user input to the correct handler."""
            intent = detect_intent(user_input)
            print(f"(Intent Detected: {intent})") # Optional: print detected intent for debugging

            if intent == "greeting":
                return handle_greeting()
            elif intent == "visitor_info":
                return handle_visitor_info()
            elif intent == "faq":
                return handle_faq_or_support(user_input)
            elif intent == "complaint":
                return handle_complaint(user_input)
            else: # Handles 'chitchat' and 'unknown'
                return "I'm not sure how to help with that yet. Try asking a question about our services or pricing."

        # =================================================================
        # 7. TESTING THE FULL PIPELINE
        # Send different types of queries to test the routing logic.
        # =================================================================
        print("\n--- Testing the Full Chatbot Pipeline ---")

        # ** Test Greeting Intent **
        user_query_1 = "Hi, how are you?"
        response_1 = chatbot_response(user_query_1)
        print(f"User: '{user_query_1}'\nBot: {response_1}\n")

        # ** Test FAQ Intent **
        # NOTE: This requires your data files to be present for a meaningful answer.
        user_query_2 = "How can I check my billing details?"
        response_2 = chatbot_response(user_query_2)
        print(f"User: '{user_query_2}'\nBot: {response_2}\n")

        # ** Test Complaint Intent **
        user_query_3 = "The new update is terrible and broke my dashboard."
        response_3 = chatbot_response(user_query_3)
        print(f"User: '{user_query_3}'\nBot: {response_3}\n")
        
        # ** Test Unknown Intent **
        user_query_4 = "Can you tell me a joke?"
        response_4 = chatbot_response(user_query_4)
        print(f"User: '{user_query_4}'\nBot: {response_4}\n")


    except Exception as e:
        # If anything goes wrong, the error will be printed.
        print(f"\n❌ An error occurred during setup or query: {e}")
        print("Please check your AvalAI API key, base URL, internet connection, and AvalAI account status.")