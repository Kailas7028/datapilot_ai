# test_retrieval.py
from rag.chromadb_impl import ChromaDBWrapper
import json

def run_search_test():
    # 1. Connect to our existing database
    print("Connecting to Vector DB...")
    vector_db = ChromaDBWrapper()
    
    # 2. Define a natural language question
    question = "What is the total amount of all paid invoices for subscriptions that are on an 'annual' billing cycle?"
    print(f"\nQuestion: {question}")
    print("-" * 50)
    
    # 3. Search ChromaDB for the top 3 most relevant tables
    results = vector_db.search(query=question, limit=2)
    
    if not results:
        print("No results found!")
        return

    # 4. Print out what the AI thinks are the best tables
    # for i, doc in enumerate(results, 1):
    #     source = doc.metadata.get("source", "Unknown Table")
    #     # Print the table name and the first 150 characters of the summary
    #     print(f"🥇 Rank {i}: {source}")
    #     print(f"Table Data: {doc.metadata}")
    #     print(f"📝 Summary: {doc.page_content}...\n

    
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

    # Join all tables together with a double newline
    return formatted_tables
if __name__ == "__main__":
    for i in run_search_test():
        print(i)