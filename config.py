import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token (set in .env or environment variable)
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Command prefix
PREFIX = "!"

# Owner user ID (hardcoded)
OWNER_ID = 1214456066687893506

# Database file name
DB_FILE = "tournament.db"

# Default alert minutes before round end if not specified
DEFAULT_ALERT_MINUTES = 5
