import hashlib
import json
import asyncio
import time
from langchain_core.documents import Document
from agent.summary_agent import SummaryAgent
from rag.pinecone_impl import PineconeWrapper
from utils.loggers import get_logger, org_id_var, user_id_var
from app.tenant_db import get_tenant_pool

logger = get_logger(__name__)

def generate_metadata_hash(table_description: str, columns: list) -> str:
    sorted_cols = sorted(columns, key=lambda x: x['name'])
    payload = {
        "description": table_description or "",
        "columns": sorted_cols
    }
    payload_string = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload_string).hexdigest()

class SchemaIndexer:
    def __init__(self):
        self.summary_agent = SummaryAgent()
        self.vector_db = PineconeWrapper()
        logger.info("SchemaIndexer initialized.")

    def _createDocument(self, tid: str, summary: str, table_data: dict, hashcode: str) -> Document:
        searchable_text = f"Table Name: {tid}\nDescription: {table_data.get('table_description', 'None')}\nSummary: {summary}"
        return Document(
            page_content=searchable_text, 
            metadata={
                "source": tid, 
                "hashcode": hashcode,
                "schema_payload": json.dumps(table_data.get("columns", [])) 
            }
        )

    async def sync_schema_to_vectordb(self, org_id: str, user_id: str = "system"):
        # 1. SET CONTEXT FOR LOGS
        org_id_var.set(org_id)
        user_id_var.set(user_id)
        
        logger.info(f"Starting schema extraction for {org_id}...")
        
        sql_query = r"""
        SELECT 
            c.table_schema AS schema_name, 
            c.table_name, 
            c.column_name, 
            c.data_type,
            CASE WHEN (
                SELECT tc.constraint_type FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
                WHERE kcu.table_schema = c.table_schema AND kcu.table_name = c.table_name
                AND kcu.column_name = c.column_name AND tc.constraint_type = 'PRIMARY KEY' LIMIT 1
            ) IS NOT NULL THEN TRUE ELSE FALSE END AS is_primary_key,
            (
                SELECT ccu.table_schema || '.' || ccu.table_name || '(' || ccu.column_name || ')'
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
                WHERE kcu.table_schema = c.table_schema AND kcu.table_name = c.table_name
                AND kcu.column_name = c.column_name AND tc.constraint_type = 'FOREIGN KEY' LIMIT 1
            ) AS foreign_key_reference,
            obj_description((c.table_schema || '.' || c.table_name)::regclass, 'pg_class') AS table_description
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        ORDER BY c.table_schema, c.table_name, c.ordinal_position;
        """

        # 2. FETCH FROM DB (Using ASYNCPG only)
        rows = []
        try:
            pool = await get_tenant_pool(org_id)
            async with pool.acquire() as conn:
                records = await conn.fetch(sql_query)
                rows = [dict(record) for record in records]
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return
        # REMOVED: finally release_connection (handled by 'async with')

        # 3. POPULATE TABLES
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
            tables[tid]["columns"].append({
                "name": row["column_name"],
                "type": row["data_type"],
                "is_pk": row["is_primary_key"],
                "fk_ref": row["foreign_key_reference"]
            })
        
        # THE GHOST VECTOR PURGE 
        try:
            # 1. Get what SHOULD exist (from Postgres)
            active_postgres_tables = set(tables.keys())
            
            # 2. Get what ACTUALLY exists (from Pinecone)
            existing_pinecone_vectors = set(self.vector_db.get_all_ids(tenant_id=org_id))
            
            # 3. Find the Ghosts (In Pinecone, but no longer in Postgres)
            ghost_vectors = existing_pinecone_vectors - active_postgres_tables
            
            if ghost_vectors:
                logger.warning(f"Found {len(ghost_vectors)} ghost vectors for {org_id}. Purging: {ghost_vectors}")
                # You already have the delete method in your base class! [cite: 353, 354]
                self.vector_db.delete(doc_ids=list(ghost_vectors), tenant_id=org_id)
            else:
                logger.info("No ghost vectors found. Namespace is clean.")
                
        except Exception as e:
            logger.error(f"Ghost vector purge failed for {org_id}: {e}")
            

        # 4. PROCESS AND UPSERT
        docs = []
        for index, (tid, data) in enumerate(tables.items(), 1):
            current_hash = generate_metadata_hash(data.get("table_description"), data["columns"])
            existing_meta = self.vector_db.get_metadata_by_id(tid, tenant_id=org_id)

            if existing_meta and existing_meta.get("hashcode") == current_hash:
                logger.debug(f"[{index}/{len(tables)}] ⏭️ SKIP: {tid}")
                continue

            logger.info(f"[{index}/{len(tables)}] 🤖 LLM Summary: {tid}...")
            try: 
                summary_text = self.summary_agent.summarize_table(table_info=data)
                doc = self._createDocument(tid=tid, summary=summary_text, table_data=data, hashcode=current_hash)
                
                self.vector_db.upsert([doc], tenant_id=org_id)
                docs.append(doc)
                await asyncio.sleep(1.0) # Non-blocking sleep for async
            except Exception as e:
                logger.error(f"Error on {tid}: {e}")
                
        logger.info(f"Indexing complete for {org_id}. {len(docs)} tables updated.")
        return docs