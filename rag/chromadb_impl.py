import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
from typing import Dict, List, Any, Optional
from rag.basevectoredb import BaseVectorDB
from utils.loggers import get_logger

# seting up module level logger via shared helper
logger = get_logger(__name__)

class ChromaDBWrapper(BaseVectorDB):
    """Production implementation of the Vector DB interface using ChromaDB.
    Uses PersistentClient to save vectors locally to disk.
    """
    _instance = None
    _is_initialized = None

    def __new__(cls,*args,**kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self,persist_directory: str = "./chroma_data", collection_name: str = "table_summaries"):
        if self._is_initialized:
            return

        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = None
        self.collection = None

        # We call connect on initialization so the object is ready to use immediately
        self.connect()

        self.__class__._is_initialized = True

    #-----------------------------------------------------------------------------

    def connect(self) -> None:

        """Establishes the connection to the underlying database
        """
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory, settings=Settings(anonymized_telemetry=False))
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            logger.info(f"Connected to chromadb collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to connect chromadb: {e}")
            raise RuntimeError("VectorDatabase connection failed") from e
        
    #----------------------------------------------------------------------------
        
    def upsert(self, documents: List[Document]) -> bool:
        """
        Insert or updates documents in the vector dtabase

        Args:
            documents (List[Document]): A list of langchain Document objects.

        Returns:
            bool: True if the operation was completely successful, false otherwise.
        """

        if not documents:
            return None
        try:
            ids = []
            texts = []
            metadatas = []

            for doc in documents:
                doc_id = doc.metadata.get("source")
                if not doc_id:
                    raise ValueError("Document metadata is missing required 'source' key for ID generation.")
                
                ids.append(doc_id)
                texts.append(doc.page_content)
                metadatas.append(doc.metadata)

            self.collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Successfully upserted {len(documents)} documents.")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert data: {e}") 
            return False
        
    #----------------------------------------------------------------------------------------   

    def get_metadata_by_id(self, doc_id: str) -> Optional[Dict[str,Any]]:

        """Retrieves the metadata for a specific document id without pulling the vector.
        Args:
        doc_id (str): the unique identifier of the document
        Returns:
        Optional[Dict[str,Any]]: The metadata dictionary if found, None if the document not exist.
        """

        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["metadatas"]   #only loads metadata 
            )
            # unpack lists if returend list of lists
            if result and result.get("metadatas") and len(result["metadatas"]) > 0:
                return result["metadatas"][0]
            return None
        
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {doc_id}: {e}")
            return None
        
    #---------------------------------------------------------------------------------    

    def search(self, query: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None) -> List[Document]:

        """Performs a semantic search against the vector database.

        Args:
            query (str): The raw text to search for.
            limit (int, optional): No of similar documents want to fetch. Defaults to 5.
            metadata_filters (Optional[Dict[str,Any]], optional): key-value pairs to pre-filter results before calculating distance. Defaults to None.

        Returns:
            List[Document]: The top matching langchain document objects.

        """

        try:
            #execute the semantic search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=metadata_filters or None,
                include=["documents","metadatas"]
            )
            #if no result return empty
            if not results or not results.get("documents") or not results["documents"][0]:
                return []
          
            langchain_docs=[]
            for i in range(len(results["documents"][0])):
                doc=Document(
                    page_content=results["documents"][0][i],
                    metadata = results["metadatas"][0][i]
                )
                langchain_docs.append(doc)
            return langchain_docs

            
        except Exception as e:
            logger.error(f"Failed for query : {query} : {e}")
            return []
        
    #--------------------------------------------------------------   

    def delete(self, doc_ids:List[str]) -> bool:
        """Removes documents from the database. Essential for keeping the DB clean 
        if a table is dropped from the source PostgreSQL database.

        Args:
            doc_ids (List[str]): List of unique identifiers to delete.

        Returns:
            bool: True if deletion was successful.
        """
        if not doc_ids:
            return True
        try:
            self.collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents.")
            return True
            
        except Exception as e:
            logger.error(f"Deletaion Filed : {e}")
            return False
        