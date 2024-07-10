import os

class Config:
  OLLAMA_API_URL = os.getenv('OLLAMA_API_URL')
  CHROMA_DB_URL = os.getenv('CHROMA_DB_URL')

config = Config()