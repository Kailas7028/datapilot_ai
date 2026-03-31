import os
import sys
import pytest

# 1. THE PATH FIX
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
os.environ["ENVIRONMENT"] = "testing"

from rag.vector_manager import vector_manager
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualRecallMetric, ContextualRelevancyMetric

# 2. IMPORT THE REQUIRED BYPASS TOOLS
from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI

# 3. BUILD THE CUSTOM TRANSLATOR (The Adapter Pattern)
class GoogleJudge(DeepEvalBaseLLM):
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        return self.model.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        res = await self.model.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return "Gemini-2.5-Flash via LangChain"

# 4. THE SMOKE TEST
def test_production_retrieval():
    question = "How many active users are there?"
    expected_sql = "SELECT COUNT(*) FROM users WHERE is_active = 1"
    
    # Fire the LangChain Retriever
    retriever = vector_manager.get_retriever()
    retrieved_docs = retriever.invoke(question)
    
    # Extract string content
    retrieved_texts = [doc.page_content for doc in retrieved_docs]
    
    # Define the DeepEval Test Case
    test_case = LLMTestCase(
        input=question,
        actual_output="N/A", 
        expected_output=expected_sql, 
        retrieval_context=retrieved_texts
    )
    
    # Initialize our custom Gemini Judge with the active model
    langchain_gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    gemini_judge = GoogleJudge(model=langchain_gemini)
    
    # Define Metrics
    recall_metric = ContextualRecallMetric(threshold=0.7, model=gemini_judge)
    relevancy_metric = ContextualRelevancyMetric(threshold=0.7, model=gemini_judge)
    
    # Run Evaluation
    assert_test(test_case, [recall_metric, relevancy_metric])