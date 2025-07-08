# =================================================================
# 1. IMPORTS
# All necessary libraries for the Streamlit app.
# =================================================================
# import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage
import os
# Import the API key from your config.py file
from config import AVALAI_API_KEY

AVALAI_BASE_URL = "https://api.avalai.ir/v1"

# Initialize qa_chain as None. It will be created later if data is available.
qa_chain = None

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=AVALAI_API_KEY,
    base_url=AVALAI_BASE_URL
)

faq_loader = TextLoader("data/faqs.csv")
service_loader = TextLoader("data/services.json")
info_loader = TextLoader('data/info.md')
complaints = TextLoader('data/complaints.yaml')

docs = faq_loader.load() + service_loader.load() + info_loader.load()

vectorstore = FAISS.from_documents(docs, embeddings)
# retriever = vectorstore.as_retriever()
print("Documents loaded and vectorstore created successfully.")

# --- NEW: Save the vectorstore ---
vector_store_path = "faiss_index" # Define a path to save your FAISS index
vectorstore.save_local(vector_store_path)
print(f"Vectorstore saved successfully to {vector_store_path}")
