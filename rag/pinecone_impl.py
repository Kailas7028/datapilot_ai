import os
from typing import Dict, List, Any, Optional
from pinecone import Pinecone
from langchain_core.documents import Document
from rag.basevectoredb import BaseVectorDB
from utils.loggers import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

class PineconeWrapper(BaseVectorDB):
    """Production implementation of the Vector DB interface using Pinecone Inference."""
    _instance = None
    _is_initialized = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        if self._is_initialized:
            return

        
        self.embedding_model_name = "multilingual-e5-large" 
        
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
        """Embeds text using Pinecone API and uploads to Pinecone."""
        if not documents:
            return None
        try:
            vectors_to_upsert = []

            for doc in documents:
                doc_id = doc.metadata.get("source")
                if not doc_id:
                    raise ValueError("Document metadata missing 'source' key.")
                
                # 1. Ask Pinecone to generate the embedding via API
                embedding_response = self.pc.inference.embed(
                    model=self.embedding_model_name,
                    inputs=[doc.page_content],
                    parameters={"input_type": "passage", "truncate": "END"}
                )
                embedding = embedding_response[0].values
                
                # 2. Prepare metadata
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
            if hasattr(result, 'vectors') and doc_id in result.vectors:
                return result.vectors[doc_id].metadata
            return None
        except Exception as e:
            logger.debug(f"Vector {doc_id} not found. Proceeding to embed.")
            return None
            
    def search(self, query: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None) -> List[Document]:
        """Embeds the search query using Pinecone API and finds nearest neighbors."""
        try:
            # 1. Ask Pinecone to embed the search query
            query_embedding_response = self.pc.inference.embed(
                model=self.embedding_model_name,
                inputs=[query],
                parameters={"input_type": "query", "truncate": "END"}
            )
            query_embedding = query_embedding_response[0].values
            
            # 2. Search Pinecone Index
            results = self.index.query(
                vector=query_embedding,
                top_k=limit,
                include_metadata=True,
                filter=metadata_filters
            )
            
            if not hasattr(results, 'matches') or not results.matches:
                return []
          
            langchain_docs = []
            for match in results.matches: 
                metadata = match.metadata or {}
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