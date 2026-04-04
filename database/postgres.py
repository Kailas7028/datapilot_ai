from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .base import BaseDatabase

class PostgresDatabase(BaseDatabase):
    def __init__(self, connection_url: str):
        self.engine = create_engine(connection_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def connect(self) -> None:
        # SQLAlchemy connects lazily, but we can verify the connection here
        with self.engine.connect() as conn:
            pass 

    def get_schema_metadata(self) -> str:
        # This is where you write the SQL to fetch table names/columns
        # For Postgres, querying information_schema.columns
        query = r"""
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
        results = self.execute_query(query)
        # Format the results into a string for the LLM
        return results

    def execute_query(self, query: str) -> list:
        with self.SessionLocal() as session:
            result = session.execute(text(query))
            # Convert rows to a list of dictionaries for JSON responses
            return [dict(row._mapping) for row in result]

    def close(self) -> None:
        self.engine.dispose()