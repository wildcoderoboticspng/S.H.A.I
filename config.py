```python
"""Central configuration for SHAI."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Identity ---
ASSISTANT_NAME = "Shai"
WAKE_WORDS = ("shai", "hey shai", "shy", "chai")
USER_TITLE = os.getenv("SHAI_USER", "Sir")

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("SHAI_MODEL", "gpt-4o-mini")
MAX_HISTORY = 20

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a witty, loyal, highly capable AI assistant \
in the spirit of JARVIS. You address the user as "{USER_TITLE}".

Rules:
- Be concise. Your replies are spoken aloud, so keep them to 1-3 sentences unless asked for detail.
- Never read out URLs, markdown, code blocks or emoji — speak plain conversational English.
- Use your tools whenever a real action or live data is required. Do not invent facts you could look up.
- If a tool fails, say so briefly and offer an alternative.
- Dry humour is welcome; grovelling is not.
"""

# --- Voice ---
VOICE_ENABLED = True
TTS_RATE = 180
TTS_VOLUME = 1.0
TTS_VOICE = os.getenv("SHAI_TTS_VOICE", "en-GB-RyanNeural")
TTS_RATE_EDGE = os.getenv("SHAI_TTS_RATE", "+0%")
MIC_ENERGY_THRESHOLD = 300
PHRASE_TIME_LIMIT = 12

# --- Storage ---
DATA_DIR = Path.home() / ".shai"
DATA_DIR.mkdir(exist_ok=True)
NOTES_FILE = DATA_DIR / "notes.txt"
LOG_FILE = DATA_DIR / "shai.log"

# --- Location fallback for weather ---
DEFAULT_CITY = os.getenv("SHAI_CITY", "London")
