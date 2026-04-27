import os
from typing import Dict, List, Any, Optional
from pinecone import Pinecone
from langchain_core.documents import Document
from rag.basevectoredb import BaseVectorDB
from utils.loggers import get_logger
from dotenv import load_dotenv
from langsmith import traceable

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

    #-- PINECONE INTEGRATED INFERENCE METHODS --
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
        

    #-- Upser to Pinecone using raw text (Pinecone handles embedding) --    
    def upsert(self, documents: List[Document], tenant_id: str) -> bool:
        """Uploads raw text directly. Pinecone handles the Llama embedding automatically."""
        if not documents:
            return None
        if not tenant_id:
            raise ValueError("Tenant ID is required for upsert operation.")
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
            self.index.upsert_records(namespace=tenant_id, records=records_to_upsert)
            logger.info(f"Successfully upserted {len(documents)} documents to Pinecone via Integrated Inference.")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert data: {e}") 
            return False
            
    # -- Search Pinecone using raw text query (Pinecone handles embedding) --        
    @traceable(name="pinecone_search")
    def search(self, query: str, tenant_id: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None ) -> List[Document]:
        """Searches Pinecone using raw text. Pinecone embeds the query automatically."""
        if not tenant_id:
            raise ValueError("Tenant ID is required for search operation.")
        try:
            # Construct the search query with the raw text and optional metadata filters
            search_query = {
                "inputs": {"text": query},
                "top_k": limit
            }
            # Add the filter to the dictionary if it exists
            if metadata_filters:
                search_query["filter"] = metadata_filters

            results = self.index.search(
                query=search_query,
                namespace=tenant_id
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
        
    #-- Delete documents from Pinecone --        
    def delete(self, doc_ids: List[str], tenant_id: str) -> bool:
        """Removes documents from Pinecone."""
        if not doc_ids:
            return True
        if not tenant_id:
            raise ValueError("Tenant ID is required for delete operation.")
        try:
            self.index.delete(ids=doc_ids, namespace=tenant_id)
            logger.info(f"Deleted {len(doc_ids)} documents.")
            return True
        except Exception as e:
            logger.error(f"Deletion Failed : {e}")
            return False

    #---fetch ids for specific tenant 
    def get_all_ids(self, tenant_id: str) -> List[str]:
            """Fetches all document IDs currently stored in the tenant's namespace."""
            if not tenant_id:
                raise ValueError("Tenant ID is required to list vectors.")
            
            try:
                # Pinecone's list() returns a generator of pagination objects
                vector_ids = []
                for id_chunk in self.index.list(namespace=tenant_id):
                    vector_ids.extend(id_chunk)
                    
                return vector_ids
            except Exception as e:
                logger.error(f"Failed to list vector IDs for {tenant_id}: {e}")
                return []
            
            
    #-- Fetch metadata for a single document ID --
    def get_metadata_by_id(self, doc_id: str, tenant_id: str) -> Optional[Dict[str,Any]]:
        """Retrieves metadata."""
        if not tenant_id:
            raise ValueError("Tenant ID is required for fetching metadata.")
        try:
            result = self.index.fetch(ids=[doc_id], namespace=tenant_id)
            if hasattr(result, 'vectors') and doc_id in result.vectors:
                return result.vectors[doc_id].metadata
            return None
        except Exception as e:
            logger.debug(f"Vector {doc_id} not found. Proceeding to embed.")
            return None
        
    #-- Fetch metadata for multiple document IDs in bulk --        
    def get_bulk_metadata(self, doc_ids: List[str], tenant_id: str) -> Dict[str, dict]:
        """Fetches metadata for multiple documents in a single API call."""
        if not tenant_id:
            raise ValueError("Tenant ID is required for fetching metadata.")
        if not doc_ids:
            return {}
            
        try:
            # Pinecone fetch allows up to 1000 IDs per request. 
            # If you expect more than 1000 tables, you would chunk the doc_ids list here.
            result = self.index.fetch(ids=doc_ids, namespace=tenant_id)
            
            bulk_meta = {}
            if hasattr(result, 'vectors'):
                for v_id, vector_data in result.vectors.items():
                    bulk_meta[v_id] = vector_data.metadata
            return bulk_meta
            
        except Exception as e:
            logger.error(f"Bulk metadata fetch failed: {e}")
            return {}