import os
import dotenv
from langchain_groq import ChatGroq
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import AIMessageChunk
from llm.base import BaseLLM
from langchain_core.runnables import RunnableConfig

dotenv.load_dotenv()

# ==========================================
# 1. THE GROQ PROVIDER (For fast JSON Summaries)
# ==========================================
class GroqLlamaProvider(BaseLLM):
    def __init__(self, model_name: str = "llama-3.1-8b-instant", temperature: float = 0.0):
        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=os.getenv("GROQ_API_KEY")
        )

    async def agenerate(self, prompt_template, require_json: bool = False, tag: str = None, config: RunnableConfig = None, **kwargs) -> AIMessageChunk:
        try:
            # Dynamically toggle JSON mode
            active_llm = self.llm.bind(response_format={"type": "json_object"}) if require_json else self.llm

            chain = prompt_template | active_llm.with_config({"tags": [tag]} if tag else {})
            return await chain.ainvoke(kwargs, config=config)
        except Exception as e:
            raise RuntimeError(f"Error in GroqLlamaProvider: {str(e)}")


# ==========================================
# 2. THE VERTEX PROVIDER (For heavy SQL Generation)
# ==========================================
class VertexGeminiProvider(BaseLLM):
    def __init__(self, model_name: str = "gemini-1.5-flash", temperature: float = 0.0):
        self.llm = ChatVertexAI(
            model_name=model_name,
            temperature=temperature,
            project=os.getenv("GCP_PROJECT_ID"),
            location="us-central1" # Default region
        )

    async def agenerate(self, prompt_template, require_json: bool = False, tag:str = None, config: RunnableConfig = None, **kwargs) -> AIMessageChunk:
        try:
            # Vertex doesn't need JSON mode for our SQL generator, but the toggle is here for consistency
            active_llm = self.llm.bind(response_format={"type": "json_object"}) if require_json else self.llm
            chain = prompt_template | active_llm.with_config({"tags": [tag]} if tag else {})
            return await chain.ainvoke(kwargs, config=config)
    
        except Exception as e:
            raise RuntimeError(f"Error in VertexGeminiProvider: {str(e)}")