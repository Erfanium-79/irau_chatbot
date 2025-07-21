# =================================================================
# chatbot.py
# This file handles the chatbot's runtime logic, including
# loading the pre-computed vector store and responding to queries.
# =================================================================

# =================================================================
# 1. IMPORTS
# All necessary libraries for the Streamlit app.
# =================================================================
import os
import csv # Import the csv module
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage

# Import the API key from your config.py file
from config import AVALAI_API_KEY

# =================================================================
# 2. CONFIGURATION AND INITIALIZATION
# Make sure your API key is set correctly and base_url is specified.
# All model and embedding initializations now use AvalAI's endpoint.
# =================================================================
# It's recommended to use environment variables for security.
# Replace "your-avalai-api-key" with your actual AvalAI API key
# or ensure it's set in your environment before running this script.

# Define the base URL for AvalAI
AVALAI_BASE_URL = "https://api.avalai.ir/v1"

# Initialize qa_chain as None. It will be created later if data is available.
qa_chain = None

# Global variables to store user information and chatbot state
user_name = None
user_phone_number = None
user_info_collected = False

# Check if the API key is available
if not AVALAI_API_KEY: # This check is now based on the imported variable
    print("❌ Error: AVALAI_API_KEY not found in config.py.")
    print("Please ensure config.py exists and AVALAI_API_KEY is set.")
else:
    print("AvalAI API key found. Initializing models and embeddings...")
    try:
        # Initialize ChatOpenAI for both general use and intent detection
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=AVALAI_API_KEY,
            base_url=AVALAI_BASE_URL
        )

        # Initialize OpenAIEmbeddings, pointing to the AvalAI base_url
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=AVALAI_API_KEY,
            base_url=AVALAI_BASE_URL
        )

        # =================================================================
        # 3. LOAD VECTOR STORE AND SETUP RETRIEVER/QA CHAIN
        # This section loads the pre-computed FAISS vector store.
        # =================================================================
        # print("Loading vectorstore...")
        vector_store_path = "faiss_index" # This must match the path used in embedder.py

        if os.path.exists(vector_store_path):
            try:
                # Load the local FAISS index
                # allow_dangerous_deserialization=True is often needed for FAISS.load_local
                vectorstore = FAISS.load_local(vector_store_path, embeddings, allow_dangerous_deserialization=True)
                retriever = vectorstore.as_retriever()
                # print(f"Vectorstore loaded successfully from {vector_store_path}.")

                # Create the QA chain for handling FAQs
                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",  # "stuff" is a common chain type for this purpose
                    retriever=retriever
                )
                # print("QA chain created successfully.")

            except Exception as e:
                print(f"❌ Error loading vectorstore from {vector_store_path}: {e}")
                print("Please ensure embedder.py has been run to create the FAISS index.")
                retriever = None
        else:
            print(f"⚠️ Warning: Vectorstore not found at {vector_store_path}.")
            print("Please run embedder.py first to create the FAISS index.")
            retriever = None
            qa_chain = None # Ensure qa_chain is None if vectorstore isn't loaded

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
        - unrelated to the iran-australia institute
        - unknown
        avoid the unknown category as much as possible
        Input: "{user_input}"
        Intent:"""
            response = llm.invoke([HumanMessage(content=prompt)])
            intent_text = response.content.strip()
            # Clean up the intent text to get just the category name
            if ":" in intent_text:
                return intent_text.split(":")[-1].strip()
            else:
                return intent_text

        # =================================================================
        # 5. INTENT HANDLERS
        # These functions define the specific actions for each detected intent.
        # All responses should be comprehensive and in Persian.
        # =================================================================
        def handle_greeting(query: str):
            """Handles greeting intent, potentially enhanced with info from QA chain, in Persian."""
            base_response = "سلام، من ربات مجموعه آموزش زبان ایران استرالیا هستم، چجوری میتونم کمکتون کنم؟"
            if qa_chain is None:
                return base_response + "\n\n(توجه: پایگاه دانش برای ارائه اطلاعات بیشتر در دسترس نیست.)"
            try:
                # Add prompt engineering for comprehensive Persian response
                query_for_qa = f"لطفا جواب بده و تو هم سلام و احوالپرسی کن، حواست باشه که تو ربات مجموعه آموزشی ایران استرالیا هستی و بجز این موسسه نباید تبلیغ هیچ جای دیگه ای رو بکنی.: {query}"
                result = qa_chain.invoke({"query": query_for_qa})
                return "\n" + result['result']
            except Exception as e:
                return base_response + "\n\n(پایگاه دانش برای ارائه اطلاعات بیشتر در دسترس نیست.)"
     
        def handle_visitor_info(query: str):
            """Handles visitor info intent, potentially enhanced with info from QA chain, in Persian."""
            base_response = "سلام، به نظر میرسه که اولین باره با موسسه ایران استرالیا داری صحبت میکنی"
            if qa_chain is None:
                return "\n\n(پایگاه دانش برای ارائه اطلاعات بیشتر در دسترس نیست.)"
            try:
                # Add prompt engineering for comprehensive Persian response
                query_for_qa = f" سعی کن در قامت یک ربات فروش محصول کاربر را قانع کنی که یادگیری زبان کار مفیدی است و باید هرچه زودتر شروع کند و کجا بهتر از موسسه ایران استرالیا، البته قبل از هر چیز اول جواب سوال پرسیده شده رو بده، مثلا اگه پرسید آدرس کجاست، اول آدرس رو دقیق بگو، بعد اگه حرف بیشتری داشتی بگو خیلی هم زیاده گویی نکن، مختصر و مفید، مثلا اگه پرسید چجوری ثبت نام کنم اول راجب به ثبت نام و تعیین سطح بگو، حواست باشه که تو ربات مجموعه آموزشی ایران استرالیا هستی و بجز این موسسه نباید تبلیغ هیچ جای دیگه ای رو بکنی {query}"
                result = qa_chain.invoke({"query": query_for_qa})
                return "\n" + result['result']
            except Exception as e:
                return base_response + "\n\n(پایگاه دانش برای ارائه اطلاعات بیشتر در دسترس نیست.)"
            
        def handle_faq_or_support(query: str):
            """Handles FAQ or support intent, providing comprehensive Persian answers."""
            if not qa_chain:
                return "متاسفم، پایگاه دانش من در حال حاضر در دسترس نیست. لطفاً مطمئن شوید که فایل‌های داده موجود هستند."
            
            # Add prompt engineering to ensure comprehensive Persian answer
            query_for_qa = f"لطفاً به این سوال به طور کامل، و با جزئیات کافی به فارسی پاسخ دهید: {query}"
            
            try:
                result = qa_chain.invoke({"query": query_for_qa})
                return result['result']
            except Exception as e:
                return f"متاسفم، در حال حاضر نمی‌توانم به سوال شما پاسخ دهم. لطفاً بعداً دوباره امتحان کنید. خطای رخ داده: {e}"

        def handle_unrelated(query: str):
                    return "متأسفم، من اطلاعاتی در این باره ندارم زیرا مأموریت من ارائه اطلاعات و خدمات مرتبط با موسسه زبان ایران استرالیا است. اگر سؤالی درباره یادگیری زبان انگلیسی یا خدمات موسسه ایران استرالیا دارید، خوشحال می‌شوم کمک کنم!"


        def handle_complaint(query: str):
            """Handles complaint intent, logging to complaints.csv with user details, in Persian."""
            global user_name, user_phone_number
            
            # Create or append to complaints.csv
            file_exists = os.path.isfile("complaints.csv")
            with open("complaints.csv", "a", newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Name", "Phone Number", "complaint"]) # Write header if file is new
                writer.writerow([user_name if user_name else "N/A", user_phone_number if user_phone_number else "N/A", query])
            
            return "از اینکه این موضوع را با ما در میان گذاشتید متاسفم. شکایت شما ثبت شد و یکی از اعضای تیم پشتیبانی ما به زودی با شما تماس خواهد گرفت."

        # =================================================================
        # 6. MAIN CHATBOT PIPELINE
        # This function connects intent detection to the appropriate handler.
        # =================================================================
        def chatbot_response(user_input: str):
            """
            The main function that routes user input to the correct handler using session state.
            """
            # First, check if user information has been collected from the session
            # if not session.get("info_collected"):
            #     if session.get("name") is None:
            #         session["name"] = user_input.strip()
            #         return "متشکرم، لطفا شماره تلفن خود را وارد کنید:"
            #     elif session.get("phone_number") is None:
            #         session["phone_number"] = user_input.strip()
            #         session["info_collected"] = True
            #         return f"سلام {session['name']}! شماره تلفن شما ({session['phone_number']}) ثبت شد. حالا چگونه می‌توانم به شما کمک کنم؟"

            # If user information is collected, proceed with intent detection
            intent = detect_intent(user_input)
            # logging.info(f"Detected intent: {intent} for chat_id with name {session.get('name')}")


            if intent == "greeting":
                return handle_greeting(user_input)
            elif intent == "visitor_info":
                return handle_visitor_info(user_input)
            elif intent == "faq":
                return handle_visitor_info(user_input)
            elif intent == "unrelated":
                return handle_unrelated(user_input)
            elif intent == "chitchat":
                # For chitchat, we can try to use the LLM directly for a general response in Persian
                prompt = f"""
شما یک دستیار هوش مصنوعی دوستانه و مفید هستید. لطفاً به این پیام به صورت دوستانه و جامع به فارسی پاسخ دهید:
پیام کاربر: "{user_input}"
پاسخ:"""
                response = llm.invoke([HumanMessage(content=prompt)])
                return response.content.strip()
            else: # Handles 'unknown'
                return -1

    except Exception as e:
        # If anything goes wrong, the error will be printed.
        print(f"\n❌ خطایی در طول راه اندازی یا پرس و جو رخ داد: {e}")
        print("لطفاً کلید API AvalAI، آدرس پایه، اتصال به اینترنت و وضعیت حساب AvalAI خود را بررسی کنید.")