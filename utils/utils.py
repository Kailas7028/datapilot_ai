#clean raw SQL output from LLM (remove markdown formatting, extra whitespace, etc.)
import re
import decimal
from datetime import date, datetime
import uuid

def extract_pure_sql(raw_llm_output: str) -> str:
    """Removes SQL comments and markdown, returning only the executable code."""
     # 3. Clean the output 
        
    #check does llm returned list of blocks
    if isinstance(raw_llm_output, list):
        raw_sql = raw_llm_output[0].get("text", "")
    else:
        raw_sql = raw_llm_output.strip()
    
    # 1. Strip the /* ... */ comment block (re.DOTALL lets it read across multiple lines)
    clean_sql = re.sub(r"/\*.*?\*/", "", raw_sql, flags=re.DOTALL)
    
    # 2. Strip standard inline comments (-- comment) just in case
    clean_sql = re.sub(r"--.*", "", clean_sql)
    
    # 3. Remove markdown backticks if the LLM hallucinated them
    clean_sql = clean_sql.replace("```sql", "").replace("```", "")
    
    # 4. Strip extra whitespace and newlines
    return clean_sql.strip()



#=======================================================================================
# Utility function to chunk large dictionaries into smaller pieces for batch processing
#=======================================================================================
from itertools import islice

def chunk_dictionary(data_dict, chunk_size):
    """Yields successive chunks from a dictionary."""
    it = iter(data_dict)
    for i in range(0, len(data_dict), chunk_size):
        yield {k: data_dict[k] for k in islice(it, chunk_size)}

#=================================================================================
#DB result sanitization
#=================================================================================
def sanitize_record(record_dict: dict) -> dict:
    """Recursively converts PostgreSQL specific types to JSON-safe Python types."""
    for key, value in record_dict.items():
        if isinstance(value, decimal.Decimal):
            # Convert decimals to float so Pandas and JSON can read them
            record_dict[key] = float(value)
        elif isinstance(value, (date, datetime)):
            # Convert dates to string format (YYYY-MM-DD)
            record_dict[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            # Convert UUID objects to strings
            record_dict[key] = str(value)
    return record_dict