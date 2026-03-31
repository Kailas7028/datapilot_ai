from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document

class BaseVectorDB(ABC):
    """Abstract Base Class for Vector Database implementation."""


    @abstractmethod
    def connect(self)->None:
        """Establishes the connection to the underlying database
        """
        pass


    @abstractmethod
    def upsert(self,documents:List[Document]) -> bool:
        """
        Insert or updates documents in the vector dtabase

        Args:
            documents (List[Document]): A list of langchain Document objects.

        Returns:
            bool: True if the operation was completely successful, false otherwise.
        """
        pass


    @abstractmethod
    def get_metadata_by_id(seld,doc_id: str) -> Optional[Dict[str,Any]]:
        """Retrieves the metadata for a specific document id without pulling the vector.
        Args:
        doc_id (str): the unique identifier of the document
        Returns:
        Optional[Dict[str,Any]]: The metadata dictionary if found, None if the document not exist.
        """
        pass


    @abstractmethod
    def search(self,query: str, limit: int = 5, metadata_filters: Optional[Dict[str,Any]] = None) -> List[Document]:
        """Performs a semantic search against the vector database.

        Args:
            query (str): The raw text to search for.
            limit (int, optional): No of similar documents want to fetch. Defaults to 5.
            metadata_filters (Optional[Dict[str,Any]], optional): key-value pairs to pre-filter results before calculating distance. Defaults to None.

        Returns:
            List[Document]: The top matching langchain document objects.

        """
        pass

    
    @abstractmethod
    def delete(self,doc_ids: List[str]) -> bool:
        """Removes documents from the database. Essential for keeping the DB clean 
        if a table is dropped from the source PostgreSQL database.

        Args:
            doc_ids (List[str]): List of unique identifiers to delete.

        Returns:
            bool: True if deletion was successful.
        """
        pass