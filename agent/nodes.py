""" Agent nodes for handling different stages of the SQL generation and execution process """
#sql generation node
from llm.prompts import FEW_SHOT_COT_PROMPT, DATA_INSIGHT_PROMPT, VIZ_SYSTEM_PROMPT
from llm.llm_provider import GroqLlamaProvider, VertexAIGeminiProvider
from agent.state import AgentState
from utils.loggers import get_logger
from rag.pinecone_impl import PineconeWrapper
import json
from utils.utils import extract_pure_sql
from app.sql_executor import execute_sql
from app.sql_validator import validate_sql

# Initialize logger
logger = get_logger(__name__)
#initialize retriever object
retriever = PineconeWrapper()
# Initialize LLM providers (you can swap these out as needed)
gemini_engine = VertexAIGeminiProvider()

groq_engine = GroqLlamaProvider()   #llama-3.1-8b-instant

#sql generation node
#---------------------------------------------------------
async def sql_generation_node(state: AgentState) -> AgentState:
    """
    Node for generating SQL from the question and schema prompt
    """
    try:
        logger.info(f"Generating SQL for the question: {state.get('question','')}")
        response = await gemini_engine.agenerate(prompt_template=FEW_SHOT_COT_PROMPT,schema = state.get("retrieved_docs",[]),question = state.get("question",""))
        input_tokens=response.usage_metadata.get("input_tokens", 0)
        output_tokens=response.usage_metadata.get("output_tokens", 0)
        
        # 3. Clean the output (Replace the logic we lost from sql_agent)
        raw_output = response.content

        #check does llm returned list of blocks
        if isinstance(raw_output, list):
            raw_sql = raw_output[0].get("text", "")
        else:
            raw_sql = raw_output.strip()
        
        # Safely strip markdown if the LLM disobeys the prompt
        final_sql = extract_pure_sql(raw_sql)
        
        # 4. Return the cleaned SQL back to the graph state
        
        logger.info(f"Generated SQL: {final_sql}")
        logger.info(f"SQL generation completed. Input tokens: {input_tokens}, Output tokens: {output_tokens}")

        return {"generated_sql": final_sql, "input_tokens": input_tokens, "output_tokens": output_tokens}
    except Exception as e:  
        logger.error(f"Error occurred during SQL generation: {str(e)}")
        return {"generated_sql": None, "input_tokens": 0, "output_tokens": 0, "error": str(e)}

#sql validation node
#---------------------------------------------------------
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
    results = retriever.search(query=state.get("question", ""), limit=5)
    
    
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
    #logger.debug(f"Formatted table schemas for LLM:\n{formatted_tables}")
    return {"retrieved_docs": formatted_tables}


# result summarization node
#------------------------------------------------
async def result_summarization_node(state: AgentState) -> AgentState:
    """
    Node for summarizing the SQL results into a human-readable answer
    """
    logger.info("Summarizing SQL results into a human-readable answer.")
    try:
        # THE FIX: Add default=str to safely cast Decimals, Dates, and UUIDs to strings
        safe_json = json.dumps(state.get("result",""), default=str)
        response = await groq_engine.agenerate(prompt_template=DATA_INSIGHT_PROMPT, sql_result=safe_json, sql_query=state.get("generated_sql", ""), question=state.get("question", ""))
        summary = response.content.strip()
        logger.info("Result summarization successful.")
        return {"result_summary": summary, "error": None}
    except Exception as e:
        logger.error(f"Error occurred during result summarization: {str(e)}")
        return {"result_summary": None, "error": str(e)}
    

# Visualization config generation node (for generating chart config from SQL results)
#---------------------------------------------

async def visualization_recommender_node(state: AgentState):
    results = state.get("result", [])
    
    # If no data returned, skip visualization
    if not results:
        return {"visualization_config": {"suggested_visualizations": []}}
        
    columns = list(results[0].keys())
    sample_data = results[:3] 
    
    # Invoke the bound LLM (No JSON parsing required!)
    try:
        # This returns a validated Pydantic object
        logger.info(f"Working on Visualisation Configuration..")
        response_obj = await gemini_engine.quick_agenerate(prompt_template=VIZ_SYSTEM_PROMPT, columns=columns, sample_data=sample_data, question=state.get("question", ""))
        
        # Convert the Pydantic object back to a standard Python dictionary for the state
        viz_config = response_obj.model_dump() 
        logger.info(f"viz_config after model_dump: {viz_config}")
    except Exception as e:
        print(f"Failed to generate valid visualization schema: {e}")
        viz_config = {"suggested_visualizations": []}
        
    return {"viz_config": viz_config}