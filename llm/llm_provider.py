# llm_providers.py
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessageChunk
from llm.base import BaseLLM
import config
import dotenv
import os

dotenv.load_dotenv()  # Load environment variables from .env file
api_key = os.getenv("GROQ_API_KEY")



class GroqLlamaProvider(BaseLLM):
    def __init__(self, model_name: str = "llama-3.1-8b-instant", temperature: float = 0.0):
        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=api_key
        )

    # Simplified: Just take whatever LangChain messages are passed in
    def generate(self, prompt_template: list, **kwargs) -> AIMessageChunk:
        try:
                # Create a chain with the provided prompt template and the LLM
            chain= prompt_template | self.llm
            response = chain.invoke(kwargs)
            return response
        
        except Exception as e:
            raise RuntimeError(f"Error in GroqLlamaProvider: {str(e)}")