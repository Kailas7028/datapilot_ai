import os
from dotenv import load_dotenv

load_dotenv()



# OpenAI API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Google Cloud configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")  # Default to us-central1 if not set
