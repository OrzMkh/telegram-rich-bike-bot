import os
import json
import logging
from config import SPREADSHEET_ID, CREDENTIALS_FILE

logger = logging.getLogger(__name__)

class SheetsSyncManager:
    def __init__(self, spreadsheet_id=SPREADSHEET_ID, credentials_file=CREDENTIALS_FILE):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file
        self.client = None
        self.enabled = False
        self._init_sheets()

    def _init_sheets(self):
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            creds_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json_env:
                s_clean = creds_json_env.strip().strip("'").strip('"')
                info = json.loads(s_clean)
                if isinstance(info.get("private_key"), str):
                    info["private_key"] = info["private_key"].replace("\\n", "\n")
                creds = Credentials.from_service_account_info(info, scopes=scopes)
            elif os.path.exists(self.credentials_file):
                creds = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
            else:
                logger.warning(f"Google credentials file '{self.credentials_file}' not found.")
                return

            self.client = gspread.authorize(creds)
            self.enabled = True
            logger.info("Google Sheets sync initialized successfully for Rich Bot.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets sync: {e}")
            self.enabled = False

    def append_rich_report(self, report: dict):
        if not self.enabled or not self.client:
            return
        try:
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            sheet_title = "Rich Ташкент"
            try:
                sheet = spreadsheet.worksheet(sheet_title)
            except Exception:
                sheet = spreadsheet.add_worksheet(title=sheet_title, rows=1000, cols=20)
                headers = [
                    "ID", "Город", "Дата отчёта", "Выдано гибридов", "Вернули", "Всего на линии",
                    "Новые гибриды", "АКБ / Зарядка", "Сломанные / ТО",
                    "Причины поломок", "Комментарий", "Партнёр", "Время отправки"
                ]
                sheet.insert_row(headers, 1)

            if len(sheet.get_all_values()) == 0:
                headers = [
                    "ID", "Город", "Дата отчёта", "Выдано гибридов", "Вернули", "Всего на линии",
                    "Новые гибриды", "АКБ / Зарядка", "Сломанные / ТО",
                    "Причины поломок", "Комментарий", "Партнёр", "Время отправки"
                ]
                sheet.insert_row(headers, 1)

            row = [
                report.get("id", ""),
                report.get("city", "Ташкент"),
                report.get("report_date", ""),
                report.get("issued", "0"),
                report.get("returned", "0"),
                report.get("total_in_trip", "0"),
                report.get("new_bikes", "0"),
                report.get("batteries_status", "100%"),
                report.get("broken_bikes", "0"),
                report.get("return_reasons", "—"),
                report.get("comment", "—"),
                report.get("username", "Партнёр"),
                report.get("created_at", "")
            ]

            sheet.append_row(row)
            logger.info(f"Rich Report #{report.get('id')} appended to Google Sheets worksheet '{sheet_title}'.")
        except Exception as e:
            logger.error(f"Error appending Rich Report #{report.get('id')} to Google Sheets: {e}")
