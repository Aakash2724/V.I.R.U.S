import json
from groq import Groq
import os

client = Groq(api_key=os.environ.get("GROQ_API_KEY", "your-api-key"))
# If there's no GROQ_API_KEY it will fail, hopefully it picks it up from the environment or .env
