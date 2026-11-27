import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
PERSONALITY_CONTEXT = os.getenv("PERSONALITY_CONTEXT", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env muhitida ko'rsatilmagan")
if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError("ADMIN_ID raqam bo'lishi kerak")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY .env muhitida ko'rsatilmagan")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL PostgreSQL manzili ko'rsatilmagan")

ADMIN_ID = int(ADMIN_ID_RAW)
