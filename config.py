import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PERSONALITY_CONTEXT = os.getenv("PERSONALITY_CONTEXT", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env muhitida ko'rsatilmagan")
if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError("ADMIN_ID raqam bo'lishi kerak")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY .env muhitida ko'rsatilmagan")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL PostgreSQL manzili ko'rsatilmagan")

ADMIN_ID = int(ADMIN_ID_RAW)
