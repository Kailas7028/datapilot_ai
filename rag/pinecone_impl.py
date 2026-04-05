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
    """Production Vector DB interface using Pinecone's Native Integrated Inference."""
    _instance = None
    _is_initialized = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        if self._is_initialized:
            return
        
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
            raise RuntimeError("Database connection failed") from e
        
    def upsert(self, documents: List[Document]) -> bool:
        """Uploads raw text directly. Pinecone handles the Llama embedding automatically."""
        if not documents:
            return None
        try:
            records_to_upsert = []

            for doc in documents:
                doc_id = doc.metadata.get("source")
                if not doc_id:
                    raise ValueError("Document metadata missing 'source' key.")
                
                # For Integrated Inference, we pass the raw text inside a 'text' field.
                record = {
                    "id": doc_id,
                    "text": doc.page_content,
                    # Add all other metadata fields directly into the record
                    **doc.metadata
                }
                records_to_upsert.append(record)

            # IMPORTANT: Use `upsert_records` instead of standard `upsert`
            self.index.upsert_records(namespace="__default__", records=records_to_upsert)
            logger.info(f"Successfully upserted {len(documents)} documents to Pinecone via Integrated Inference.")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert data: {e}") 
            return False
            
    def get_metadata_by_id(self, doc_id: str) -> Optional[Dict[str,Any]]:
        """Retrieves metadata."""
        try:
            result = self.index.fetch(ids=[doc_id])
            if hasattr(result, 'vectors') and doc_id in result.vectors:
                return result.vectors[doc_id].metadata
            return None
        except Exception as e:
            logger.debug(f"Vector {doc_id} not found. Proceeding to embed.")
            return None
            
    def search(self, query: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None) -> List[Document]:
        """Searches Pinecone using raw text. Pinecone embeds the query automatically."""
        try:
            # IMPORTANT: Use the `search` method (not query) for Integrated Inference
            search_query = {
                "inputs": {"text": query},
                "top_k": limit
            }
            # Add the filter to the dictionary if it exists
            if metadata_filters:
                search_query["filter"] = metadata_filters

            results = self.index.search(
                query=search_query
            )
            
            # Safely extract hits from Pinecone's dictionary response
            hits = results.get('result', {}).get('hits', [])
            if not hits:
                return []
          
            langchain_docs = []
            for hit in hits:
                # The raw text and metadata are stored inside 'fields'
                fields = hit.get('fields', {})
                metadata = dict(fields) # Copy to avoid altering the original
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