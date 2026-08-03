import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json").strip()
MASTER_HUB_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "telegram-master-hub-bot", "bike_reports.db"))
DB_PATH = os.getenv("DB_PATH", MASTER_HUB_DB).strip()

# Admin IDs (comma-separated IDs or usernames in env)
raw_admins = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = [a.strip() for a in raw_admins.split(",") if a.strip()]

raw_groups = os.getenv("GROUP_CHAT_ID", "-4946205555,-4573236562").strip()
GROUP_CHAT_IDS = [g.strip() for g in raw_groups.split(",") if g.strip()]
