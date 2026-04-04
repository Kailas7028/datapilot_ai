from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseDatabase(ABC):
    
    @abstractmethod
    def connect(self) -> None:
        """Establishes the connection to the database."""
        pass

    @abstractmethod
    def get_schema_metadata(self) -> str:
        """Retrieves table schemas and structures for the LLM context."""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Executes a raw SQL query and returns the results as a list of dictionaries."""
        pass
        
    @abstractmethod
    def close(self) -> None:
        """Safely closes the connection."""
        pass