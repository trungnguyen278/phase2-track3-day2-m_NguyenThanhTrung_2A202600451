import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

REDIS_URL = os.getenv("REDIS_URL", "")  # vd: redis://localhost:6379/0; rỗng → JSON fallback

PROFILE_PATH = DATA_DIR / "profile_store.json"
EPISODIC_PATH = DATA_DIR / "episodic_log.json"
CHROMA_PATH = str(DATA_DIR / "chroma_db")
SEMANTIC_COLLECTION = "semantic_kb"
EPISODIC_COLLECTION = "episodic_kb"

SHORT_TERM_MAX_TURNS = 8
MEMORY_TOKEN_BUDGET = 1200
