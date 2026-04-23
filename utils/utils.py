#clean raw SQL output from LLM (remove markdown formatting, extra whitespace, etc.)
import re

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

