import os
from typing import Dict, List, Any, Optional
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document
from rag.basevectoredb import BaseVectorDB
from utils.loggers import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

class PineconeWrapper(BaseVectorDB):
    """Production implementation of the Vector DB interface using Pinecone."""
    _instance = None
    _is_initialized = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        if self._is_initialized:
            return

        # 1. Load the exact model ChromaDB was using secretly
        logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.pc = None
        self.index = None
        
        self.connect()
        self.__class__._is_initialized = True

    def connect(self) -> None:
        """Establishes connection to Pinecone Cloud."""
        try:
            api_key = os.getenv("PINECONE_API_KEY")
            index_name = os.getenv("PINECONE_INDEX_NAME")
            
            if not api_key or not index_name:
                raise ValueError("Missing Pinecone credentials in .env")

            self.pc = Pinecone(api_key=api_key)
            self.index = self.pc.Index(index_name)
            logger.info(f"Connected to Pinecone Index: {index_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}")
            raise RuntimeError("VectorDatabase connection failed") from e
        
    def upsert(self, documents: List[Document]) -> bool:
        """Embeds text and uploads to Pinecone."""
        if not documents:
            return None
        try:
            vectors_to_upsert = []

            for doc in documents:
                doc_id = doc.metadata.get("source")
                if not doc_id:
                    raise ValueError("Document metadata missing 'source' key.")
                
                # Convert the text into a 384-dimension vector
                embedding = self.embedding_model.encode(doc.page_content).tolist()
                
                # Pinecone expects metadata to be a dictionary, we store the raw text here too
                metadata = doc.metadata.copy()
                metadata["text"] = doc.page_content

                vectors_to_upsert.append({
                    "id": doc_id,
                    "values": embedding,
                    "metadata": metadata
                })

            # Upload in batches
            self.index.upsert(vectors=vectors_to_upsert)
            logger.info(f"Successfully upserted {len(documents)} documents to Pinecone.")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert data: {e}") 
            return False
            
        

    def get_metadata_by_id(self, doc_id: str) -> Optional[Dict[str,Any]]:
        """Retrieves metadata without pulling the vector."""
        try:
            result = self.index.fetch(ids=[doc_id])
            
            # V3 Object Notation: Check if the attribute exists
            if hasattr(result, 'vectors') and doc_id in result.vectors:
                # Access the metadata attribute directly
                return result.vectors[doc_id].metadata
            return None
            
        except Exception as e:
            # Changed to debug so it doesn't print red text on first runs
            logger.debug(f"Vector {doc_id} not found. Proceeding to embed.")
            return None
            
    def search(self, query: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None) -> List[Document]:
        """Embeds the search query and finds nearest neighbors."""
        try:
            # Convert the user query into a vector
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True,
                filter=metadata_filters
            )
            
            # V3 Object Notation: Check the .matches attribute
            if not hasattr(results, 'matches') or not results.matches:
                return []
          
            langchain_docs = []
            for match in results.matches: # Dot notation here
                # Match is now an object, so we access .metadata
                metadata = match.metadata or {}
                
                # Extract the raw text we saved during upsert
                page_content = metadata.pop("text", "") 
                
                doc = Document(
                    page_content=page_content,
                    metadata=metadata
                )
                langchain_docs.append(doc)
            return langchain_docs
            
        except Exception as e:
            logger.error(f"Failed for query : {query} : {e}")
            return []
            
    def delete(self, doc_ids: List[str]) -> bool:
        """Removes documents from Pinecone."""
        if not doc_ids:
            return True
        try:
            self.index.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents.")
            return True
        except Exception as e:
            logger.error(f"Deletion Failed : {e}")
            return False