# llm/llm_provider.py
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessageChunk
from llm.base import BaseLLM
import config
import dotenv
import os
from api.models import VisualizationConfig , RouteDecision

dotenv.load_dotenv() 

# 1. Existing Groq Provider
class GroqLlamaProvider(BaseLLM):
    def __init__(self, model_name: str = "llama-3.1-8b-instant", temperature: float = 0.0):

        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=os.getenv("GROQ_API_KEY")
        )

    def generate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return chain.invoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in GroqLlamaProvider: {str(e)}")
        
    #async version of generate   
    async def agenerate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return await chain.ainvoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in GroqLlamaProvider: {str(e)}")
        
    # Router method
    async def router_master(self,prompt_template ,**kwargs) -> RouteDecision:
        try:
            router_chain = prompt_template | self.llm.with_structured_output(RouteDecision)
            return await router_chain.ainvoke(kwargs)
        except Exception as e:
            raise RuntimeError(f" Router failed to route: {str(e)}")
        
#--------------------------------------------------------------------------------------------
# 2. Vertex AI Gemini Provider
class VertexAIGeminiProvider(BaseLLM):
    def __init__(self, model_name: str = "gemini-2.5-pro", temperature: float = 0.0):
        # Vertex AI automatically picks up your GCP project and credentials 
        # from the gcloud CLI authentication you did earlier.
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_output_tokens=8192,
            project = config.GCP_PROJECT_ID
        )
        self.flash_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",  # A smaller, faster model variant for quick checks
            temperature=0.0,
            max_output_tokens=1024,
            project = os.getenv("GCP_PROJECT_ID")
        ).with_structured_output(VisualizationConfig)


    def generate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return chain.invoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in VertexAIGeminiProvider: {str(e)}")
        
    #async version of generate    
    async def agenerate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return await chain.ainvoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in VertexAIGeminiProvider: {str(e)}")
        
    #=================================================================
    # light llm call for quick responses (e.g., for SQL validation feedback or simple clarifications)
    # Sync version for quick checks
    def quick_generate(self, prompt_template, **kwargs) -> VisualizationConfig:
        try:
            chain = prompt_template | self.flash_llm
            return chain.invoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in VertexAIGeminiProvider (quick_generate): {str(e)}")
        
    # Async version for quick checks
    async def quick_agenerate(self, prompt_template, **kwargs) -> VisualizationConfig:
        try:
            chain = prompt_template | self.flash_llm
            return await chain.ainvoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in VertexAIGeminiProvider (quick_agenerate): {str(e)}")
        
#Free tier gemini-3.1-pro-preview provider 
#---------------------------------------------------------------------------------------------
class Gemini3PreviewProvider(BaseLLM):
    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.0):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_output_tokens=8192,
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def generate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return chain.invoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in Gemini3PreviewProvider: {str(e)}")
        
    #async version of generate    
    async def agenerate(self, prompt_template, **kwargs) -> AIMessageChunk:
        try:
            chain = prompt_template | self.llm
            return await chain.ainvoke(kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in Gemini3PreviewProvider: {str(e)}")