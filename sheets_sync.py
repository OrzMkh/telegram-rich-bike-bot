import os
import logging
from config import SPREADSHEET_ID, CREDENTIALS_FILE

logger = logging.getLogger(__name__)

HEADERS = [
    "ID",
    "Город",
    "Дата",
    "Выдано",
    "Вернули",
    "Всего в поездке",
    "Новые байки",
    "Старые байки",
    "Сломанные",
    "Причины возврата",
    "Комментарий",
    "Партнёр",
    "Время отправки"
]

class SheetsSyncManager:
    def __init__(self, spreadsheet_id=SPREADSHEET_ID, credentials_file=CREDENTIALS_FILE):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file
        self.client = None
        self.enabled = False
        self._init_sheets()

    def _init_sheets(self):
        import json
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = None
            creds_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json_env:
                try:
                    s_clean = creds_json_env.strip()
                    if (s_clean.startswith("'") and s_clean.endswith("'")) or (s_clean.startswith('"') and s_clean.endswith('"')):
                        s_clean = s_clean[1:-1].strip()
                    info = json.loads(s_clean)
                    if isinstance(info.get("private_key"), str):
                        info["private_key"] = info["private_key"].replace("\\n", "\n")
                    creds = Credentials.from_service_account_info(info, scopes=scopes)
                    logger.info("Loaded Google credentials from GOOGLE_CREDENTIALS_JSON env var.")
                except Exception as e:
                    logger.error(f"Failed to parse GOOGLE_CREDENTIALS_JSON: {e}")

            if not creds and os.path.exists(self.credentials_file):
                creds = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)

            if not creds:
                logger.warning(f"Google Sheets credentials file '{self.credentials_file}' not found. Sheets sync disabled.")
                self.enabled = False
                return

            self.client = gspread.authorize(creds)
            self.enabled = True
            logger.info("Google Sheets integration initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            self.enabled = False

    def append_bike_report(self, report: dict):
        if not self.enabled or not self.client:
            return
        try:
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            city_name = report.get("city", "").strip()

            target_name = f"Байки {city_name}" if city_name and city_name != "-" else "Байки"
            sheet = None
            try:
                sheet = spreadsheet.worksheet(target_name)
            except Exception:
                pass

            if not sheet:
                sheet = spreadsheet.add_worksheet(title=target_name, rows=1000, cols=20)
                sheet.insert_row(HEADERS, 1)

            existing = sheet.get_all_values()
            if not existing:
                sheet.insert_row(HEADERS, 1)

            row = [
                report.get("id", ""),
                report.get("city", ""),
                report.get("report_date", ""),
                report.get("issued", ""),
                report.get("returned", ""),
                report.get("total_in_trip", ""),
                report.get("new_bikes", ""),
                report.get("old_bikes", ""),
                report.get("broken_bikes", ""),
                report.get("return_reasons", ""),
                report.get("comment", ""),
                report.get("username", ""),
                report.get("created_at", "")
            ]
            sheet.append_row(row)
            logger.info(f"Bike report #{report.get('id')} appended to Google Sheets ('{sheet.title}').")
        except Exception as e:
            logger.error(f"Error appending report #{report.get('id')} to Google Sheets: {e}")
