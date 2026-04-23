""" Agent nodes for handling different stages of the SQL generation and execution process """
#sql generation node
from urllib import response

from llm.prompts import FEW_SHOT_COT_PROMPT, DATA_INSIGHT_PROMPT, VIZ_SYSTEM_PROMPT, ROUTER_PROMPT, SQL_RETRY_PROMPT
from llm.llm_provider import GroqLlamaProvider, VertexAIGeminiProvider, Gemini3PreviewProvider, FallbackProvider
from agent.state import AgentState
from utils.loggers import get_logger
from rag.pinecone_impl import PineconeWrapper
import json
from utils.utils import extract_pure_sql
from app.sql_executor import execute_sql
from app.sql_validator import validate_sql
from langsmith import traceable
from langchain_core.messages import AIMessage
from google.api_core import exceptions

# Initialize logger
logger = get_logger(__name__)
#initialize retriever object
retriever = PineconeWrapper()

# Initialize LLM providers (you can swap these out as needed)
gemini_engine = VertexAIGeminiProvider()   #vertexai gemini-2.5-pro
gemini3_engine = Gemini3PreviewProvider() # Free tier gemini-3.1-pro-preview for lightweight tasks
groq_engine = GroqLlamaProvider()   #llama-3.1-8b-instant
fallback_provider = FallbackProvider() #mistral-7b-instant-v0.1 for fallback

#sql generation node
#---------------------------------------------------------
async def sql_generation_node(state: AgentState) -> AgentState:
    """
    Node for generating SQL from the question and schema prompt
    """
    try:
        logger.info(f"Generating SQL for the question: {state.get('question','')}")
        history = state.get("messages", [])[:-1]  # Get all messages except the latest one which is the current question
        response = await gemini3_engine.agenerate(prompt_template=FEW_SHOT_COT_PROMPT,schema = state.get("retrieved_docs",[]),question = state.get("question",""), chat_history=history)
        input_tokens=response.usage_metadata.get("input_tokens", 0)
        output_tokens=response.usage_metadata.get("output_tokens", 0)

        # Count Total Tokens for one question-answer cycle (for cost estimation and monitoring)
        input_tokens = state.get("input_tokens", 0) + input_tokens
        output_tokens = state.get("output_tokens", 0) + output_tokens

        # # 3. Clean the output 
        # raw_output = response.content

        # #check does llm returned list of blocks
        # if isinstance(raw_output, list):
        #     raw_sql = raw_output[0].get("text", "")
        # else:
        #     raw_sql = raw_output.strip()
        
        # Safely strip markdown if the LLM disobeys the prompt
        final_sql = extract_pure_sql(response.content)
        
        # 4. Return the cleaned SQL back to the graph state
        
        logger.info(f"Generated SQL: {final_sql}")
        logger.info(f"SQL generation completed. Input tokens: {input_tokens}, Output tokens: {output_tokens}")

        return {"generated_sql": final_sql, "input_tokens": input_tokens, "output_tokens": output_tokens}
    
    # Handle specific API errors that indicate the primary LLM is unavailable and route to fallback
    except (exceptions.ServiceUnavailableError, exceptions.Resourceexhausted) as api_error:
        logger.error(f"Routing to fallback mistral llm due to : {str(api_error)}")
        try:
            response = await fallback_provider.agenerate(prompt_template=FEW_SHOT_COT_PROMPT,schema = state.get("retrieved_docs",[]),question = state.get("question",""), chat_history=history)
            input_tokens=response.usage_metadata.get("input_tokens", 0)
            output_tokens=response.usage_metadata.get("output_tokens", 0)
            # Safely strip markdown if the LLM disobeys the prompt
            final_sql = extract_pure_sql(response.content)
            logger.info(f"Generated SQL: {final_sql}")
            logger.info(f"SQL generation completed. Input tokens: {input_tokens}, Output tokens: {output_tokens}")

            return {"generated_sql": final_sql, "input_tokens": input_tokens, "output_tokens": output_tokens}
        except Exception as fallback_error:
            logger.error(f"Error in fallback provider: {str(fallback_error)}")

        return {"generated_sql": None, "input_tokens": 0, "output_tokens": 0, "error": f"API error: {str(api_error)}"}

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
@traceable(name="sql_execution_node")  # This decorator will automatically create a trace for this node in LangSmith, allowing you to see the input and output of this node in the trace view.
async def sql_execution_node(state: AgentState) -> AgentState:
    """
    Node for executing the validated SQL and storing the result
    """
    try:
        logger.info("Executing validated SQL.")
        org_id = state.get("org_id")  # Replace with dynamic org_id in production
        validate_sql = state.get("validated_sql")
        if validate_sql:
            result = await execute_sql(validate_sql, org_id)
            logger.info(f"SQL execution successful.")
            return {"result": result, "error": None}
        else:
            raise ValueError("No validated SQL to execute or organization ID not provided.")
    except Exception as e:
        logger.error(f"Error occurred while executing SQL: {str(e)}")
        return {"result": None, "error": str(e)}
    

#------------------------------------------------------------------------------------------
# Retry Node (for handling retries in case of errors during SQL generation, validation, or execution)
#------------------------------------------------------------------------------------------
async def retry_node(state: AgentState) -> AgentState:
    """
    Node for handling retries in case of errors during SQL generation, validation, or execution
    """
    try:
        error = state.get("error")
        if error and state["retries"] < 2:  # Retry up to 3 times
            retries_count = state.get("retries", 0) + 1
            logger.info(f"Retrying due to error: {error}")
            # Clear the error and relevant fields to trigger a retry in the graph
            retry_result = await gemini3_engine.agenerate(prompt_template=SQL_RETRY_PROMPT, error_message=error, question=state.get("question", ""), schema=state.get("retrieved_docs", []))
            # Count Total Tokens for one question-answer cycle (for cost estimation and monitoring)
            new_in_tokens = retry_result.usage_metadata.get("input_tokens", 0)
            new_out_tokens = retry_result.usage_metadata.get("output_tokens", 0)
            total_input = state.get("input_tokens", 0) + new_in_tokens
            total_output = state.get("output_tokens", 0) + new_out_tokens

            raw_output = retry_result.content
            #check does llm returned list of blocks
            if isinstance(raw_output, list):
                raw_sql = raw_output[0].get("text", "")
            else:
                raw_sql = raw_output.strip()
            
            # Safely strip markdown if the LLM disobeys the prompt
            final_sql = extract_pure_sql(raw_sql)
            logger.info(f"Regenerated SQL: {final_sql}")
            logger.info(f"SQL Regeneration completed. Input tokens: {total_input}, Output tokens: {total_output}")

            return {"generated_sql": final_sql, "input_tokens": total_input, "output_tokens": total_output, "error": None, "retries": retries_count}
            
        else:
            # No error, no retry needed
            return {}
    except Exception as e:
        logger.error(f"Error in retry node: {str(e)}")
        return state  # Return the original state if retry logic fails
    
#------------------------------------------------------------------------------------------
# Retriever Node (for fetching relevant documents from the vector store based on the question)
#------------------------------------------------------------------------------------------

def retriever_node(state: AgentState) -> dict:
    """
    Node for retrieving relevant documents from the vector store based on the question
    """
    try:
        logger.info("Retrieving relevant documents from vector store.")
    
        org_id = state.get("org_id")  
        if not org_id:
            raise ValueError("Organization ID is required for retrieval.")
        
        # Pinecone fetches up to 5 tables
        results = retriever.search(query=state.get("question"), limit=5, tenant_id=org_id)
    
        if not results:
            logger.info("No results found!")
            return {"retrieved_docs": []}
        
        formatted_tables = []

        # 1. Start the loop
        for doc in results:
            table_name = doc.metadata.get("source", "unknown_table")
            
            # 2. Put the try-except INSIDE the loop so one bad table doesn't ruin the batch
            try:
                summary_lines = doc.page_content.split('\n')
                comment_block = "\n".join([f"-- {line}" for line in summary_lines])
                
                schema_ddl = f"{comment_block}\nCREATE TABLE {table_name} (\n"
            
                raw_payload = doc.metadata.get("schema_payload", "[]")
                columns = json.loads(raw_payload)
                
                column_definitions = []
                for col in columns:
                    col_str = f"    {col['name']} {col['type']}"
                    
                    if col.get("is_pk"):
                        col_str += " PRIMARY KEY"
                        
                    if col.get("fk_ref"):
                        col_str += f" REFERENCES {col['fk_ref']}"
                        
                    column_definitions.append(col_str)
                
                schema_ddl += ",\n".join(column_definitions)
                schema_ddl += "\n);"
                
                # 3. THE FIX: Append INSIDE the loop
                formatted_tables.append(schema_ddl)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON for {table_name}: {e}")
                formatted_tables.append(f"-- Error loading columns for {table_name}")
            except Exception as e:
                logger.error(f"Unexpected error processing document {table_name}: {e}")
                formatted_tables.append(f"-- Unexpected error loading columns for {table_name}")

        logger.info(f"Retrieved {len(formatted_tables)} relevant documents.")
        return {"retrieved_docs": formatted_tables}
        
    except Exception as e:
        logger.error(f"Retrieval node failed: {e}")
        return {"retrieved_docs": []}


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
        # 3. Create the AI memory block
        ai_memory = f"Previously generated SQL:\n{state.get('generated_sql', '')}\n\nSummary:\n{summary}"
        logger.info("Result summarization successful.")
        return {"result_summary": summary, "error": None, "messages": [AIMessage(content=ai_memory)]}
    except Exception as e:
        logger.error(f"Error occurred during result summarization: {str(e)}")
        return {"result_summary": None, "error": str(e), "messages": []}

    
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

#-----------------------------------------------------------------
# ROUTER NODE
#-----------------------------------------------------------------
async def router_master(state: AgentState) -> AgentState:
    question = state.get("question", "")
    logger.info(f"Routing question...:{question}")
    try:
        router_result = await groq_engine.router_master(prompt_template=ROUTER_PROMPT , question=question)
        logger.debug(f" Router Decison : {router_result.decision}")
        return {"router_decision":router_result.decision.strip().lower()}
    
    except Exception as e:
        logger.error(f"Router node failed: {str(e)}. Defaulting to 'analytics'.")
        return {"router_decision": "analytics"}
    



#----------------------------------------------------------------
# Chat Node
#----------------------------------------------------------------
def chat_node(state: AgentState):
    # A simple, static welcome message
    logger.info(f" Chat node activated for question : '{state.get('question')}' ")
    welcome_message = (
        "Hello! 👋 I am Datapilot, your AI Data Assistant.\n\n"
        "I can help you analyze your database using natural language. "
        "Try asking me things like:\n"
        "- *'Show me the top 10 products with the highest sales.'*\n"
        "- *'What was the total revenue grouped by year?'*\n"
        "- *'Which region has the highest discounts?'*\n\n"
        "How can I help you explore your data today?"
    )
    
    # We return empty/null values for the database fields so the UI doesn't crash!
    return {
        "result_summary": welcome_message,
        "generated_sql": "-- No SQL required for chat",
        "result": [],  # Empty DataFrame
        "viz_config": {"suggested_visualizations": []} # No charts
    }