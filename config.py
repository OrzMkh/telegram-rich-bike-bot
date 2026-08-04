import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8803642782:AAHiSsVxnleQIrOytksRHTVmH_vWWYtcKSg").strip()
DB_PATH = os.getenv("DB_PATH", "rich_bikes.db").strip()
CITY = os.getenv("CITY", "Ташкент").strip()
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "-1002638798110").strip()

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "14lJVvDmK9LOAERAo9twp3Ak-FEdvlrzu-8FywP2dTn4").strip()
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json").strip()
