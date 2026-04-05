""" Agent nodes for handling different stages of the SQL generation and execution process """
#sql generation node
from llm.prompts import FEW_SHOT_COT_PROMPT, DATA_INSIGHT_PROMPT
from llm.llm_provider import GroqLlamaProvider
from agent.state import AgentState
from utils.loggers import get_logger
from rag.pinecone_impl import PineconeWrapper
import json

# Initialize logger
logger = get_logger(__name__)
#initialize retriever object
retriever = PineconeWrapper()
provider = GroqLlamaProvider()

#sql generation node
#---------------------------------------------------------
def sql_generation_node(state: AgentState) -> AgentState:
    """
    Node for generating SQL from the question and schema prompt
    """
    try:
        logger.info(f"Generating SQL for the question: {state.get('question','')}")
        response = provider.generate(prompt_template=FEW_SHOT_COT_PROMPT,schema = state.get("retrieved_docs",[]),question = state.get("question",""))
        input_tokens=response.usage_metadata.get("input_tokens", 0)
        output_tokens=response.usage_metadata.get("output_tokens", 0)
        # 3. Clean the output (Replace the logic we lost from sql_agent)
        raw_sql = response.content.strip()
        
        # Safely strip markdown if the LLM disobeys the prompt
        if raw_sql.startswith("```sql"):
            raw_sql = raw_sql[6:]
        elif raw_sql.startswith("```"):
            raw_sql = raw_sql[3:]
            
        if raw_sql.endswith("```"):
            raw_sql = raw_sql[:-3]
            
        final_sql = raw_sql.strip()
        
        # 4. Return the cleaned SQL back to the graph state
        
        logger.info(f"Generated SQL: {final_sql}")
        logger.info(f"SQL generation completed. Input tokens: {input_tokens}, Output tokens: {output_tokens}")

        return {"generated_sql": final_sql, "input_tokens": input_tokens, "output_tokens": output_tokens}
    except Exception as e:  
        logger.error(f"Error occurred during SQL generation: {str(e)}")
        return {"generated_sql": None, "input_tokens": 0, "output_tokens": 0, "error": str(e)}

#sql validation node
#---------------------------------------------------------
from app.sql_validator import validate_sql
def sql_validation_node(state: AgentState) -> AgentState:
    """
    Node for validating the generated SQL
    """
    logger.info("Validating generated SQL.")
    try:
        validate_sql(state.get("generated_sql", ""))
        logger.info("SQL validation successful.")
        return {"validated_sql":state.get("generated_sql", ""), "error": None}
    except ValueError as e:
        logger.warning(f"SQL validation failed: {str(e)}")
        return {"validated_sql": None, "error": str(e)}
    
#sql execution node
#-----------------------------------------------------------

from app.sql_executor import execute_sql
def sql_execution_node(state: AgentState) -> AgentState:
    """
    Node for executing the validated SQL and storing the result
    """
    try:
        logger.info("Executing validated SQL.")
        if state.get("validated_sql"):
            result = execute_sql(state.get("validated_sql", ""))
            logger.info(f"SQL execution successful.")
            return {"result": result, "error": None}
    except Exception as e:
        logger.error(f"Error occurred while executing SQL: {str(e)}")
        return {"result": None, "error": str(e)}



# retriever node
#------------------------------------------------

def retriever_node(state: AgentState) -> AgentState:
    """
    Node for retrieving relevant documents from the vector store based on the question
    """
    logger.info("Retrieving relevant documents from vector store.")
    results = retriever.search(query=state.get("question", ""), limit=2)
    
    if not results:
        print("No results found!")
        return

   
    
    formatted_tables = []

    for doc in results:
        # 1. Get the basic table info
        table_name = doc.metadata.get("source", "unknown_table")
        
        # Add the page_content (summary) as SQL comments so the LLM has business context
        summary_lines = doc.page_content.split('\n')
        comment_block = "\n".join([f"-- {line}" for line in summary_lines])
        
        # Start building the SQL table definition
        schema_ddl = f"CREATE TABLE {table_name} (\n"
        
        try:
            # 2. THE FIX: Parse the stringified JSON back into a Python list
            raw_payload = doc.metadata.get("schema_payload", "[]")
            columns = json.loads(raw_payload)
            
            # 3. Iterate through the parsed list of dictionaries
            column_definitions = []
            for col in columns:
                col_str = f"    {col['name']} {col['type']}"
                
                # Add Primary Key constraint if true
                if col.get("is_pk"):
                    col_str += " PRIMARY KEY"
                    
                # Add Foreign Key constraint if it exists
                if col.get("fk_ref"):
                    col_str += f" REFERENCES {col['fk_ref']}"
                    
                column_definitions.append(col_str)
            
            # Join the columns safely with commas
            schema_ddl += ",\n".join(column_definitions)
            schema_ddl += "\n);"
            
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for {table_name}: {e}")
            schema_ddl += "    -- Error loading columns\n);"

        # Combine the comments and the schema
        formatted_tables.append(f"{schema_ddl}")

    logger.info(f"Retrieved {len(formatted_tables)} relevant documents.")
    return {"retrieved_docs": formatted_tables}

# result summarization node
#------------------------------------------------
def result_summarization_node(state: AgentState) -> AgentState:
    """
    Node for summarizing the SQL results into a human-readable answer
    """
    logger.info("Summarizing SQL results into a human-readable answer.")
    try:
        # THE FIX: Add default=str to safely cast Decimals, Dates, and UUIDs to strings
        safe_json = json.dumps(state.get("result",""), default=str)
        response = provider.generate(prompt_template=DATA_INSIGHT_PROMPT, data_result=safe_json, sql_query=state.get("generated_sql", ""), question=state.get("question", ""))
        summary = response.content.strip()
        logger.info("Result summarization successful.")
        return {"result_summary": summary, "error": None}
    except Exception as e:
        logger.error(f"Error occurred during result summarization: {str(e)}")
        return {"result_summary": None, "error": str(e)}