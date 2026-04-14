from abc import ABC, abstractmethod

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generates a response based on the input prompt."""
        pass
    
    @abstractmethod
    async def agenerate(self, prompt: str) -> str:
        """Asynchronously generates a response based on the input prompt."""
        pass