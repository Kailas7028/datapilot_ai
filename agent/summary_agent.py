# summary_agent.py
from llm.prompts import SUMMARY_PROMPT_TEMPLATE
from llm.llm_provider import GroqLlamaProvider

class SummaryAgent:
    def __init__(self):
        self.llm = GroqLlamaProvider()
        self.template = SUMMARY_PROMPT_TEMPLATE

    def summarize_table(self, table_info) -> str:
        try:
            summary =  self.llm.generate(self.template,table_info=table_info)
            return summary.content
        except Exception as e:
            raise RuntimeError(f"Error in summary agent") from e