import os
import sys
import json
import pytest

# 1. THE PATH FIX
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
os.environ["ENVIRONMENT"] = "testing"

from rag.vector_manager import vector_manager
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualRecallMetric, ContextualRelevancyMetric

from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_ollama import ChatOllama

# 2. THE OLLAMA ADAPTER
class OllamaJudge(DeepEvalBaseLLM):
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        strict_prompt = prompt + "\n\nCRITICAL INSTRUCTION: You must return ONLY a raw JSON object. Do not include any conversational text, markdown formatting, or code scripts. Output valid JSON only."
        return self.model.invoke(strict_prompt).content

    async def a_generate(self, prompt: str) -> str:
        strict_prompt = prompt + "\n\nCRITICAL INSTRUCTION: You must return ONLY a raw JSON object. Do not include any conversational text, markdown formatting, or code scripts. Output valid JSON only."
        res = await self.model.ainvoke(strict_prompt)
        return res.content

    def get_model_name(self):
        return "Llama-3.1 (Colab Server)"

# 3. LOAD THE DATASET
def load_evaluation_data():
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "mini_eval_queries.json"))
    with open(dataset_path, "r") as file:
        return json.load(file)

# 4. THE TEST SUITE
@pytest.mark.parametrize("test_data", load_evaluation_data())
def test_full_retriever_accuracy(test_data):
    question = test_data.get("question")
    expected_sql = test_data.get("expected_sql", "")
    
    if not question or not expected_sql:
        pytest.skip("Missing question or expected SQL.")
        
    retriever = vector_manager.get_retriever()
    retrieved_docs = retriever.invoke(question)
    retrieved_texts = [doc.page_content for doc in retrieved_docs]
    
    test_case = LLMTestCase(
        input=question,
        actual_output="N/A", 
        expected_output=expected_sql, 
        retrieval_context=retrieved_texts
    )
    
    # 5. CONNECT TO COLAB
    # PASTE YOUR NEW COLAB URL HERE:
    langchain_ollama = ChatOllama(
        model="llama3.1",
        base_url="https://nice-teeth-brake.loca.lt/", 
        client_kwargs={"headers": {"Bypass-Tunnel-Reminder": "true"}},
        format="json"
    )
    
    eval_judge = OllamaJudge(model=langchain_ollama)
    
    recall_metric = ContextualRecallMetric(threshold=0.7, model=eval_judge,verbose_mode=True)
    relevancy_metric = ContextualRelevancyMetric(threshold=0.7, model=eval_judge,verbose_mode=True)
    
    # 6. THE MAGIC BULLET
    # run_async=False forces it to send 1 request at a time. 
    # The tunnel will easily handle this without crashing.
    assert_test(test_case, [recall_metric, relevancy_metric], run_async=False)