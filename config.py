import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from root directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    HOST: str = os.getenv("HOST", "127.0.0.1").strip()
    PORT: int = int(os.getenv("PORT", "8000"))
    
    @property
    def is_groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here")

settings = Settings()
