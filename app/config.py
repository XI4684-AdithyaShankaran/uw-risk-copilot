from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=str(ENV_FILE))

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_DIR = DATA_DIR / "db"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"

DB_PATH = DB_DIR / "uw_risk.db"
PROPERTIES_CSV = RAW_DIR / "properties.csv"
GUIDELINES_PDF = RAW_DIR / "underwriting_guidelines.pdf"

GEMINI_MODEL_NAME = "models/gemini-3-flash-preview"
GEMINI_EMBEDDING_MODEL_NAME = "models/gemini-embedding-001"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_TIMEOUT_MS = 60_000
