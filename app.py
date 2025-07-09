import streamlit as st
import os
import csv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage

# =================================================================
# 0. STREAMLIT PAGE CONFIGURATION (MUST BE FIRST)
# =================================================================
st.set_page_config(page_title="Iran-Australia Chatbot", page_icon="🤖")

# =================================================================
# 1. CONFIGURATION AND INITIALIZATION (from chatbot.py)
# =================================================================
# IMPORTANT: Hardcoding API keys is generally NOT recommended for production.
# For deployment, consider using Streamlit secrets or environment variables.
os.environ["AVALAI_API_KEY"] = "aa-dhz3cYYm2mJ1LeowMpSDXfrRiy7jQjhUcaNDjN0FWw5Uk9uY"

# Define the base URL for AvalAI
AVALAI_BASE_URL = "https://api.avalai.ir/v1"

# Initialize qa_chain as None. It will be created later if data is available.
qa_chain = None
llm = None
embeddings = None

# Global variables to store user information and chatbot state
# Use Streamlit's session state for persistence across reruns
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'user_phone_number' not in st.session_state:
    st.session_state.user_phone_number = None
if 'user_info_collected' not in st.session_state:
    st.session_state.user_info_collected = False
if 'messages' not in st.session_state:
    st.session_state.messages = []

# =================================================================
# 2. INITIALIZE MODELS AND EMBEDDINGS (from chatbot.py, adapted for Streamlit)
# =================================================================
@st.cache_resource
def initialize_chatbot_components():
    """Initializes LLM, embeddings, and QA chain, caching them."""
    try:
        # Initialize ChatOpenAI for both general use and intent detection
        _llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=os.environ["AVALAI_API_KEY"],
            base_url=AVALAI_BASE_URL
        )

        # Initialize OpenAIEmbeddings, pointing to the AvalAI base_url
        _embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.environ["AVALAI_API_KEY"],
            base_url=AVALAI_BASE_URL
        )

        # Load vector store and setup retriever/QA chain
        vector_store_path = "faiss_index" # This must match the path used in embedder.py

        _qa_chain = None
        if os.path.exists(vector_store_path):
            try:
                _vectorstore = FAISS.load_local(vector_store_path, _embeddings, allow_dangerous_deserialization=True)
                _retriever = _vectorstore.as_retriever()
                _qa_chain = RetrievalQA.from_chain_type(
                    llm=_llm,
                    chain_type="stuff",
                    retriever=_retriever
                )
                st.success(f"Vectorstore loaded successfully from {vector_store_path}.")
            except Exception as e:
                st.error(f"❌ Error loading vectorstore from {vector_store_path}: {e}")
                st.warning("Please ensure embedder.py has been run to create the FAISS index.")
        else:
            st.warning(f"⚠️ Warning: Vectorstore not found at {vector_store_path}.")
            st.info("Please run embedder.py first to create the FAISS index. FAQ functionality will be limited.")

        return _llm, _embeddings, _qa_chain

    except Exception as e:
        st.error(f"❌ خطایی در طول راه اندازی ربات چت رخ داد: {e}")
        st.info("لطفاً کلید API AvalAI، آدرس پایه، اتصال به اینترنت و وضعیت حساب AvalAI خود را بررسی کنید.")
        return None, None, None

llm, embeddings, qa_chain = initialize_chatbot_components()

# =================================================================
# 3. INTENT DETECTION FUNCTION (from chatbot.py)
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
avoid the unknown category as much as possible.
Input: "{user_input}"
Intent:"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        intent_text = response.content.strip()
        # Clean up the intent text to get just the category name
        if ":" in intent_text:
            return intent_text.split(":")[-1].strip()
        else:
            return intent_text
    except Exception as e:
        st.error(f"Error detecting intent: {e}")
        return "unknown"

# =================================================================
# 4. INTENT HANDLERS (from chatbot.py)
# =================================================================
def handle_greeting(query: str):
    """Handles greeting intent, potentially enhanced with info from QA chain, in Persian."""
    base_response = "سلام، من ربات مجموعه ایران استرالیا هستم، چجوری میتونم کمکتون کنم؟"
    if qa_chain is None:
        return base_response + "\n\n(توجه: پایگاه دانش برای ارائه اطلاعات بیشتر در مورد احوالپرسی در دسترس نیست.)"
    try:
        query_for_qa = f"لطفا جواب بده و تو هم سلام و احوالپرسی کن، حواست باشه که تو ربات مجموعه آموزشی ایران استرالیا هستی.: {query}"
        result = qa_chain.invoke({"query": query_for_qa})
        return "\n" + result['result']
    except Exception as e:
        return "\n\n(توجه: بازیابی اطلاعات اضافی برای احوالپرسی با مشکل مواجه شد.)"
 
def handle_visitor_info(query: str):
    """Handles visitor info intent, potentially enhanced with info from QA chain, in Persian."""
    base_response = "به نظر می‌رسد این اولین باری است که از ما بازدید می‌کنید! می‌توانید ابزار تجزیه و تحلیل رایگان ما را امتحان کنید یا در مورد میزبانی ایمیل ما اطلاعات بیشتری کسب کنید."
    if qa_chain is None:
        return "\n\nخطا"
    try:
        query_for_qa = f"سعی کن در قامت یک ربات فروش محصول کاربر را قانع کنی که یادگیری زبان کار مفیدی است و باید هرچه زودتر شروع کند و کجا بهتر از موسسه ایران استرالیا، البته قبل از هر چیز اول جواب سوال پرسیده شده رو به طور دقیق بده، مثلا اگه پرسید آدرس کجاست، اول آدرس رو دقیق بگو، بعد متن رو یه مقدار گسترده تر کن و یه مقدار اطلاعات بیشتری بده، یا مثلا اگه پرسید چجوری ثبت نام کنم اول راجب به ثبت نام و تعیین سطح بگو، بعدا توضیحات بیشتری بده، اگه پرسیدن از ایران استرالیا موسسه بهتری وجود داره یا نه، به هیچ وجه موسسه دیگه ای رو تبلیغ نکن و بگو که ایران استرالیا بهترینه: {query}"
        result = qa_chain.invoke({"query": query_for_qa})
        return "\n" + result['result']
    except Exception as e:
        return "\n\nخطا"
    
def handle_faq_or_support(query: str):
    """Handles visitor info intent, potentially enhanced with info from QA chain, in Persian."""
    base_response = "به نظر می‌رسد این اولین باری است که از ما بازدید می‌کنید! می‌توانید ابزار تجزیه و تحلیل رایگان ما را امتحان کنید یا در مورد میزبانی ایمیل ما اطلاعات بیشتری کسب کنید."
    if qa_chain is None:
        return "\n\nخطا"
    try:
        query_for_qa = f"سعی کن در قامت یک ربات فروش محصول کاربر را قانع کنی که یادگیری زبان کار مفیدی است و باید هرچه زودتر شروع کند و کجا بهتر از موسسه ایران استرالیا، البته قبل از هر چیز اول جواب سوال پرسیده شده رو به طور دقیق بده، مثلا اگه پرسید آدرس کجاست، اول آدرس رو دقیق بگو، بعد متن رو یه مقدار گسترده تر کن و یه مقدار اطلاعات بیشتری بده، یا مثلا اگه پرسید چجوری ثبت نام کنم اول راجب به ثبت نام و تعیین سطح بگو، بعدا توضیحات بیشتری بده، اگه پرسیدن از ایران استرالیا موسسه بهتری وجود داره یا نه، به هیچ وجه موسسه دیگه ای رو تبلیغ نکن و بگو که ایران استرالیا بهترینه: {query}"
        result = qa_chain.invoke({"query": query_for_qa})
        return "\n" + result['result']
    except Exception as e:
        return "\n\nخطا"

def handle_complaint(query: str):
    """Handles complaint intent, logging to complaints.csv with user details, in Persian."""
    
    file_exists = os.path.isfile("complaints.csv")
    with open("complaints.csv", "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Name", "Phone Number", "Complaint"])
        writer.writerow([st.session_state.user_name if st.session_state.user_name else "N/A", 
                         st.session_state.user_phone_number if st.session_state.user_phone_number else "N/A", 
                         query])
    
    return "از اینکه این موضوع را با ما در میان گذاشتید متاسفم. شکایت شما ثبت شد و یکی از اعضای تیم پشتیبانی ما به زودی با شما تماس خواهد گرفت."

# =================================================================
# 5. MAIN CHATBOT PIPELINE (from chatbot.py, adapted for Streamlit)
# =================================================================
def chatbot_response(user_input: str):
    """The main function that routes user input to the correct handler."""
    
    if not st.session_state.user_info_collected:
        if st.session_state.user_name is None:
            st.session_state.user_name = user_input.strip()
            return "متشکرم، لطفا شماره تلفن خود را وارد کنید:"
        elif st.session_state.user_phone_number is None:
            st.session_state.user_phone_number = user_input.strip()
            st.session_state.user_info_collected = True
            return f"سلام {st.session_state.user_name}! شماره تلفن شما ({st.session_state.user_phone_number}) ثبت شد. حالا چگونه می‌توانم به شما کمک کنم؟"
        else:
            return "در حال حاضر اطلاعات شما را دارم. چگونه می‌توانم به شما کمک کنم؟"

    intent = detect_intent(user_input)
    st.session_state.messages.append({"role": "assistant", "content": f"(قصد شناسایی شده: {intent})"}) # For debugging

    if intent == "greeting":
        return handle_greeting(user_input)
    elif intent == "visitor_info":
        return handle_visitor_info(user_input)
    elif intent == "faq":
        return handle_faq_or_support(user_input)
    elif intent == "complaint":
        return handle_complaint(user_input)
    elif intent == "chitchat":
        if llm is None:
            return "متاسفم، نمی‌توانم به سوالات عمومی پاسخ دهم زیرا مدل زبان در دسترس نیست."
        prompt = f"""
شما یک دستیار هوش مصنوعی دوستانه و مفید هستید. لطفاً به این پیام به صورت دوستانه و جامع به فارسی پاسخ دهید:
پیام کاربر: "{user_input}"
پاسخ:"""
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            return f"متاسفم، در حال حاضر نمی‌توانم به سوال شما پاسخ دهم. خطای رخ داده: {e}"
    else: # Handles 'unknown'
        return "من هنوز مطمئن نیستم چگونه به شما در این مورد کمک کنم. سعی کنید سوالی در مورد خدمات یا قیمت‌های ما بپرسید."

# =================================================================
# 6. STREAMLIT UI
# =================================================================
st.title("🤖 Iran-Australia Chatbot")
st.markdown("به ربات چت مجموعه ایران استرالیا خوش آمدید. من اینجا هستم تا به سوالات شما پاسخ دهم و به شما کمک کنم.")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Initial prompt for user information if not collected
if not st.session_state.user_info_collected:
    if st.session_state.user_name is None:
        initial_prompt = "سلام! برای شروع، لطفاً نام کامل خود را وارد کنید:"
    elif st.session_state.user_phone_number is None:
        initial_prompt = "متشکرم، لطفا شماره تلفن خود را وارد کنید:"
    else:
        initial_prompt = f"سلام {st.session_state.user_name}! شماره تلفن شما ({st.session_state.user_phone_number}) ثبت شد. حالا چگونه می‌توانم به شما کمک کنم؟"
    
    # Display the initial prompt as a bot message
    if not st.session_state.messages or st.session_state.messages[-1]["content"] != initial_prompt:
        st.session_state.messages.append({"role": "assistant", "content": initial_prompt})
        with st.chat_message("assistant"):
            st.markdown(initial_prompt)

# Accept user input
if prompt := st.chat_input("پیام خود را اینجا وارد کنید..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get chatbot response
    with st.chat_message("assistant"):
        with st.spinner("در حال فکر کردن..."):
            response = chatbot_response(prompt)
            st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})