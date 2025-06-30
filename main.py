import os
from langchain_community.document_loaders import TextLoader, CSVLoader, JSONLoader
from langchain_community.document_loaders.helpers import detect_file_encodings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import yaml
import json

# Define the data directory (assuming script is run from the parent directory)
DATA_DIR = "./data" # Adjust if your 'data' folder is elsewhere

# --- 1. Load Documents ---
def load_documents():
    documents = []

    # Load complaints.yaml
    complaints_path = os.path.join(DATA_DIR, "complaints.yaml")
    try:
        with open(complaints_path, 'r', encoding='utf-8') as file:
            yaml_data = yaml.safe_load(file)
            # Assuming complaints.yaml is a list of dictionaries or similar structure
            # Each dictionary/entry becomes a separate document
            if isinstance(yaml_data, list):
                for i, item in enumerate(yaml_data):
                    documents.append(Document(page_content=yaml.dump(item, default_flow_style=False),
                                              metadata={"source": "complaints.yaml", "item_index": i}))
            elif isinstance(yaml_data, dict):
                documents.append(Document(page_content=yaml.dump(yaml_data, default_flow_style=False),
                                          metadata={"source": "complaints.yaml", "is_single_doc": True}))
            else:
                print(f"Warning: complaints.yaml has unexpected structure: {type(yaml_data)}")
                documents.append(Document(page_content=file.read(), metadata={"source": "complaints.yaml"}))

    except Exception as e:
        print(f"Error loading complaints.yaml: {e}")

    # Load faqs.csv
    faqs_path = os.path.join(DATA_DIR, "faqs.csv")
    try:
        # Detect encoding for CSV if unsure, though UTF-8 is common
        encodings = detect_file_encodings(faqs_path)
        csv_loader = CSVLoader(file_path=faqs_path, encoding=encodings[0].encoding if encodings else 'utf-8')
        documents.extend(csv_loader.load())
    except Exception as e:
        print(f"Error loading faqs.csv: {e}")

    # Load info.md
    info_md_path = os.path.join(DATA_DIR, "info.md")
    try:
        md_loader = TextLoader(file_path=info_md_path, encoding='utf-8')
        documents.extend(md_loader.load())
    except Exception as e:
        print(f"Error loading info.md: {e}")

    # Load more_cleaned_merged_output.txt
    txt_path = os.path.join(DATA_DIR, "more_cleaned_merged_output.txt")
    try:
        txt_loader = TextLoader(file_path=txt_path, encoding='utf-8')
        documents.extend(txt_loader.load())
    except Exception as e:
        print(f"Error loading more_cleaned_merged_output.txt: {e}")

    # Load services.json
    services_path = os.path.join(DATA_DIR, "services.json")
    try:
        with open(services_path, 'r', encoding='utf-8') as file:
            json_data = json.load(file)
            # Assuming services.json is a list of dictionaries or a dictionary of services
            if isinstance(json_data, list):
                for i, item in enumerate(json_data):
                    documents.append(Document(page_content=json.dumps(item, indent=2),
                                              metadata={"source": "services.json", "item_index": i}))
            elif isinstance(json_data, dict):
                # If it's a dictionary of services, each key-value pair could be a doc
                for key, value in json_data.items():
                    documents.append(Document(page_content=json.dumps({key: value}, indent=2),
                                              metadata={"source": "services.json", "service_name": key}))
            else:
                print(f"Warning: services.json has unexpected structure: {type(json_data)}")
                documents.append(Document(page_content=file.read(), metadata={"source": "services.json"}))
    except Exception as e:
        print(f"Error loading services.json: {e}")

    return documents

# --- 2. Split and Chunk Documents ---
def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # Optimal chunk size depends on content, start with 1000
        chunk_overlap=200, # Overlap helps maintain context
        length_function=len,
        is_separator_regex=False,
    )

    # Specific splitting for YAML/JSON if their loader didn't split perfectly
    # For this example, we assume the custom loading logic handles initial object separation.
    # If a YAML/JSON entry is very long, it will be further split by RecursiveCharacterTextSplitter.

    chunked_documents = []
    for doc in documents:
        # Check source for more targeted splitting if needed (e.g., markdown specific)
        if doc.metadata.get("source") == "info.md":
            # For Markdown, use specific separators to respect structure
            md_text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", " ", ""], # Prioritize paragraphs, then lines, then words
                length_function=len,
                is_separator_regex=False
            )
            chunked_documents.extend(md_text_splitter.split_documents([doc]))
        else:
            chunked_documents.extend(text_splitter.split_documents([doc]))
    return chunked_documents

# --- 3. Embed Documents with a Free Model (CPU) ---
def get_embeddings_model():
    # Model: all-MiniLM-L6-v2 is a good CPU-friendly choice
    # model_kwargs = {'device': 'cpu'} ensures it runs on CPU
    # encode_kwargs = {'normalize_embeddings': False} is default but good to be explicit if needed
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )
    return embeddings

# --- 4. Store in FAISS Vector Space ---
def create_faiss_vectorstore(chunked_documents, embeddings_model):
    print("Creating FAISS vector store...")
    vectorstore = FAISS.from_documents(chunked_documents, embeddings_model)
    print("FAISS vector store created.")
    return vectorstore

# --- Main Execution ---
if __name__ == "__main__":
    # Ensure the data directory exists
    if not os.path.exists(DATA_DIR):
        print(f"Error: Data directory '{DATA_DIR}' not found. Please create it and place your files inside.")
        exit()

    print("Loading documents...")
    all_documents = load_documents()
    print(f"Loaded {len(all_documents)} raw documents.")

    print("Splitting and chunking documents...")
    chunked_docs = split_documents(all_documents)
    print(f"Split into {len(chunked_docs)} chunks.")

    print("Initializing embedding model (all-MiniLM-L6-v2) for CPU...")
    embeddings = get_embeddings_model()
    print("Embedding model loaded.")

    faiss_vectorstore = create_faiss_vectorstore(chunked_docs, embeddings)

    # You can now save the FAISS index to disk for persistence
    FAISS_INDEX_PATH = "faiss_index_chatbot"
    faiss_vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"FAISS index saved to '{FAISS_INDEX_PATH}'")

    # --- Example: How to use the vector store for retrieval ---
    print("\n--- Example Retrieval ---")
    retrieved_docs = faiss_vectorstore.similarity_search("What are the available services?", k=3)
    print(f"Found {len(retrieved_docs)} similar documents for 'What are the available services?':")
    for i, doc in enumerate(retrieved_docs):
        print(f"\nDocument {i+1} (Source: {doc.metadata.get('source', 'N/A')}):")
        print(doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content)
        print("-" * 30)

    # --- To load the index later ---
    # print("\n--- Loading saved FAISS index ---")
    # loaded_vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    # print("FAISS index loaded successfully.")
    # retrieved_docs_loaded = loaded_vectorstore.similarity_search("How can I file a complaint?", k=2)
    # print(f"Found {len(retrieved_docs_loaded)} similar documents for 'How can I file a complaint?' from loaded index:")
    # for i, doc in enumerate(retrieved_docs_loaded):
    #     print(f"\nDocument {i+1} (Source: {doc.metadata.get('source', 'N/A')}):")
    #     print(doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content)
    #     print("-" * 30)

    # --- Next steps for a Chatbot: Integrate with an LLM ---
    print("\n--- Next Steps: Integrating with an LLM for a Chatbot ---")
    print("To build a full chatbot, you would integrate this vector store with a Large Language Model (LLM).")
    print("Since you only have CPU access, consider using local, quantized LLMs (e.g., from Hugging Face Transformers with `llama.cpp` or `ollama`).")
    print("You'd typically use LangChain's RetrievalQA chain or a custom RAG (Retrieval Augmented Generation) chain:")
    print("1. User asks a question.")
    print("2. Retrieve relevant documents from the FAISS vector store based on the question.")
    print("3. Pass the retrieved documents and the user's question to an LLM as context.")
    print("4. The LLM generates a coherent answer based on the provided context.")
    print("\nExample LangChain RAG setup (conceptual, requires a local LLM setup):")
    print("""
    # from langchain_community.llms import LlamaCpp # Example for local LLM
    # from langchain.chains import RetrievalQA

    # llm = LlamaCpp(model_path="/path/to/your/quantized_model.gguf", n_ctx=2048) # Adjust path and context window
    # qa_chain = RetrievalQA.from_chain_type(
    #     llm=llm,
    #     chain_type="stuff", # Or map_reduce, refine, etc.
    #     retriever=faiss_vectorstore.as_retriever()
    # )
    #
    # query = "Can you tell me about the different types of complaints handled?"
    # response = qa_chain.invoke({"query": query})
    # print(response["result"])
    """)