import hashlib
import json
import time
from typing import Iterator
from psycopg2.extras import RealDictCursor
from langchain_core.documents import Document

from app.db import get_connection
from agent.summary_agent import SummaryAgent
from rag.chromadb_impl import ChromaDBWrapper
from utils.loggers import get_logger

# Initialize Centralized Logger
logger = get_logger(__name__)

# ==========================================
# HELPER: Data Drift Detector
# ==========================================
def generate_metadata_hash(table_description: str, columns: list) -> str:
    """Generates a SHA256 hash capturing the full state of the table's metadata."""
    sorted_cols = sorted(columns, key=lambda x: x['name'])
    payload = {
        "description": table_description or "",
        "columns": sorted_cols
    }
    payload_string = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload_string).hexdigest()


class SchemaIndexer:
    """Manages the extraction, summarization, and storage of database schemas."""
    
    def __init__(self):
        self.summary_agent = SummaryAgent()
        self.vector_db = ChromaDBWrapper()
        logger.info("SchemaIndexer initialized and connected to Vector DB.")

    # def _createDocument(self, content: str, source: str, description: str = None, hashcode: str = None) -> Document:
    #     """Helper method to create a LangChain Document with consistent metadata."""
    #     return Document(
    #         page_content=content, 
    #         metadata={
    #             "source": source, 
    #             "description": description or "", 
    #             "hashcode": hashcode or ""
    #         }
    #     )

    def _createDocument(self,tid: str, summary: str, table_data: dict, hashcode: str) -> Document:
        """Safely splits data between embedding vectors and metadata storage."""
        
        
        
        # 1. PAGE CONTENT: Strictly for the Embedding Model (Keep under 256 tokens)
        # We only include the table name, description, and the LLM's semantic summary.
        searchable_text = f"Table Name: {tid}\n"
        searchable_text += f"Description: {table_data.get('table_description', 'None')}\n"
        searchable_text += f"Summary: {summary}"

        # 2. METADATA: The Payload for the SQL Agent (Unlimited size)
        # We store the massive column definitions as a raw JSON string.
        # The Vector DB will NOT embed this, it will just hand it back when the table is found.
        return Document(
            page_content=searchable_text, 
            metadata={
                "source": tid, 
                "hashcode": hashcode,
                "schema_payload": json.dumps(table_data[tid].get("columns")) 
            }
        )

    def sync_schema_to_vectordb(self) -> Document:
        """Fetches schema, checks for drift, summarizes via LLM, and streams results."""
        logger.info("Starting schema extraction from PostgreSQL...")
        
        # 1. DEFINE THE ADVANCED METADATA QUERY
        sql_query = r"""
        SELECT 
            c.table_schema AS schema_name, 
            c.table_name, 
            c.column_name, 
            c.data_type,
            -- Check if this column is a Primary Key
            CASE WHEN (
                SELECT tc.constraint_type
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc
                  ON kcu.constraint_name = tc.constraint_name
                WHERE kcu.table_schema = c.table_schema
                  AND kcu.table_name = c.table_name
                  AND kcu.column_name = c.column_name
                  AND tc.constraint_type = 'PRIMARY KEY'
                LIMIT 1
            ) IS NOT NULL THEN TRUE ELSE FALSE END AS is_primary_key,
            -- Check if this column is a Foreign Key, and get what it points to
            (
                SELECT ccu.table_schema || '.' || ccu.table_name || '(' || ccu.column_name || ')'
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc
                  ON kcu.constraint_name = tc.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE kcu.table_schema = c.table_schema
                  AND kcu.table_name = c.table_name
                  AND kcu.column_name = c.column_name
                  AND tc.constraint_type = 'FOREIGN KEY'
                LIMIT 1
            ) AS foreign_key_reference,
            obj_description((c.table_schema || '.' || c.table_name)::regclass, 'pg_class') AS table_description
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        ORDER BY c.table_schema, c.table_name, c.ordinal_position;
        """
        # 2. FETCH FROM DB
        conn = None
        rows = []
        try:
            conn = get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql_query)
                rows = cursor.fetchall()
        except Exception as e:
            logger.error(f"FATAL: Database connection failed. Details: {e}")
            return            
        finally:
            if conn:
                conn.close()

        # 3. INITIALIZE AND POPULATE THE TABLES DICTIONARY
        tables = {}
        for row in rows:
            tid = f"{row['schema_name']}.{row['table_name']}"
            if tid not in tables:
                tables[tid] = {
                    "schema_name": row["schema_name"],
                    "table_name": row["table_name"],
                    "table_description": row["table_description"] or "",
                    "columns": []
                }
            
            col_def = {
                "name": row["column_name"],
                "type": row["data_type"],
                "is_pk": row["is_primary_key"],
                "fk_ref": row["foreign_key_reference"] # Will be None if it's not a Foreign Key
            }
            tables[tid]["columns"].append(col_def)

        logger.info(f"Successfully extracted {len(tables)} tables. Starting ingestion.")

        # 4. PROCESS, SUMMARIZE, AND SAVE
        docs=[]
        for index, (tid, data) in enumerate(tables.items(), 1):
            
            # -> DATA DRIFT CHECK <-
            current_hash = generate_metadata_hash(data.get("table_description"), data["columns"])
            existing_meta = self.vector_db.get_metadata_by_id(tid)
            
            # If the table exists and the columns/description haven't changed, skip it!
            if existing_meta and existing_meta.get("hashcode") == current_hash:
                logger.debug(f"[{index}/{len(tables)}] ⏭️ SKIP: {tid} (No schema changes detected)")
                continue

            logger.info(f"[{index}/{len(tables)}] 🤖 LLM: Generating summary for {tid}...")
            try: 
                # Call the LLM
                summary_text = self.summary_agent.summarize_table(table_info=data)
                
                # Build the Document
                doc = self._createDocument(
                    tid=tid,
                    table_data=tables, 
                    summary=summary_text, 
                    hashcode=current_hash
                )
                
                # THE SAVE STATE: Save to Vector DB immediately
                self.vector_db.upsert([doc])
                docs.append(doc)
            
                # API Rate Limits
                time.sleep(2.5) 
         
                
            except Exception as e:
                logger.error(f"[{index}/{len(tables)}] ❌ ERROR on {tid}: {e}")
                continue
        return docs


if __name__ == "__main__":
    dm = SchemaIndexer()
    for doc in dm.sync_schema_to_vectordb():
        print(f"ingested: {doc.metadata.get('source')} (hash={doc.metadata.get('hashcode')})")