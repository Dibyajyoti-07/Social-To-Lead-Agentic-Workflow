import os
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Resolve path to knowledge base relative to this file
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KB_PATH = os.path.join(_BASE_DIR, "knowledge_base", "autostream_kb.md")
_CHROMA_DIR = os.path.join(_BASE_DIR, "chroma_db")

# Load and split the knowledge base
def _build_vectorstore() -> Chroma:
    loader = TextLoader(_KB_PATH, encoding="utf-8")
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=_CHROMA_DIR,
        collection_name="autostream_kb",
    )
    return vectorstore


# Singleton — build once and reuse
_vectorstore: Chroma = None


def _get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _build_vectorstore()
    return _vectorstore


def retrieve(query: str, k: int = 2) -> str:
    """
    Retrieve the top-k relevant chunks from the knowledge base
    for the given query. Returns them as a single concatenated string.
    """
    vs = _get_vectorstore()
    results = vs.similarity_search(query, k=k)
    if not results:
        return "No relevant information found in the knowledge base."
    return "\n\n".join(doc.page_content for doc in results)

