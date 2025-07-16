# utils/rag_helpers.py
import ollama
import chromadb
import os
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="chat_context")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def sanitize_metadata(metadata: dict) -> dict:
    return {k: v for k, v in metadata.items() if v is not None}

def process_pdf(file_path, email: str):
    reader = PdfReader(file_path)
    full_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

    existing_ids = collection.get()['ids']
    if any(i.startswith(f"{email}#chunk") for i in existing_ids):
        print(f"✅ Context PDF untuk {email} sudah ada.")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=500)
    chunks = [c.strip() for c in splitter.split_text(full_text) if c.strip()]
    if not chunks:
        print("❌ Tidak ada chunk valid.")
        return

    response = ollama.embed(model="mxbai-embed-large", input=chunks)
    embeddings = response["embeddings"]
    chunk_ids = [f"{email}#chunk{i}" for i in range(len(chunks))]
    metadatas = [sanitize_metadata({"email": email}) for _ in chunks]

    collection.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas
    )
    print(f"✅ {len(chunks)} context chunk disimpan untuk {email}")

def store_chat_history(email: str, user_question: str, bot_response: str):
    chat_text = f"Pertanyaan: {user_question}\nJawaban: {bot_response}"
    embed = ollama.embed(model="mxbai-embed-large", input=chat_text)
    embedding = embed["embeddings"][0]

    ids = collection.get()['ids']
    new_id = f"{email}_chat{len([i for i in ids if i.startswith(email+'_chat')])}"

    collection.add(
        ids=[new_id],
        embeddings=[embedding],
        documents=[chat_text],
        metadatas=[sanitize_metadata({"email": email})]
    )
    print(f"📝 History untuk {email} disimpan.")

def get_context_from_rag(email: str, user_input: str) -> str:
    process_pdf("LLM/data/context.pdf", email)

    embed = ollama.embed(model="mxbai-embed-large", input=user_input)
    user_embedding = embed["embeddings"][0]

    results = collection.query(
        query_embeddings=[user_embedding],
        where={"email": email},
        n_results=5
    )
    docs = results.get("documents", [])
    if not docs:
        return "Tidak ada konteks relevan ditemukan."
    
    print(docs)

    return "\n".join(sum(docs, []))  # flatten

def index_tools_pdf():
    pdf_path = "LLM/data/tools.pdf"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError("tools.pdf tidak ditemukan.")

    reader = PdfReader(pdf_path)
    text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])

    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = [c.strip() for c in splitter.split_text(text) if c.strip()]

    existing_ids = collection.get()["ids"]
    if any(i.startswith("tools#") for i in existing_ids):
        print("📦 tools.pdf sudah terindeks.")
        return

    for i, chunk in enumerate(chunks):
        embedding = ollama.embed(model="mxbai-embed-large", input=chunk)["embeddings"][0]
        collection.add(
            ids=[f"tools#{i}"],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{"email": "tools"}]  # umum, bukan user
        )
    print(f"📚 tools.pdf diindeks sebanyak {len(chunks)} chunk.")

def get_context_rag_tool(user_input: str, n_results: int = 5) -> str:
    if not any(i.startswith("tools#") for i in collection.get()['ids']):
        index_tools_pdf()

    embed = ollama.embed(model="mxbai-embed-large", input=user_input)
    user_embedding = embed["embeddings"][0]

    results = collection.query(
        query_embeddings=[user_embedding],
        where={"email": "tools"},
        n_results=n_results
    )

    docs = results.get("documents", [])
    if not docs or not docs[0]:
        return "⚠️ Tidak ditemukan konteks relevan dari tools.pdf"

    return "\n---\n".join(docs[0])
