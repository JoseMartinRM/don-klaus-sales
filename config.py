import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class AppConfig(BaseModel):
    # Meta / Instagram Graph API Settings
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
    META_VERIFY_TOKEN: str = os.getenv("META_VERIFY_TOKEN", "instaflow_verify_token_secure_2026")
    META_PAGE_ID: str = os.getenv("META_PAGE_ID", "")
    INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    GRAPH_API_VERSION: str = os.getenv("GRAPH_API_VERSION", "v20.0")

    # Gemini AI Settings (Free Tier available at aistudio.google.com)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Kill-Switch: Pausa total de automatizaciones para recuperación de Shadowban
    AUTOMATIONS_PAUSED: bool = True

    # Server Settings
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DATABASE_PATH: str = str(BASE_DIR / "instaflow.db")

config = AppConfig()

