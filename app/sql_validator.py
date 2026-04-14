import sqlparse
import re
FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE"
}

ALLOWED_START = ("SELECT", "WITH")


def validate_sql(query: str):
    """
    Validate generated SQL before execution
    """

    parsed = sqlparse.parse(query)

    if not parsed:
        raise ValueError("Invalid SQL")

    statement = parsed[0]
    first_token = statement.tokens[0].value.upper()

    # Only allow SELECT queries
    if not first_token.startswith(ALLOWED_START):
        raise ValueError("Only SELECT queries are allowed")

    # Block dangerous operations
    upper_query = query.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, upper_query):
            raise ValueError(f"Forbidden keyword detected: {keyword}")

    return True