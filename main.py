import os
import json
import sqlite3
import logging
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import ApplicationBuilder, CommandHandler, PrefixHandler

from config import BOT_TOKEN, DB_PATH
from database import init_db
from sheets_sync import SheetsSyncManager
from handlers import start_handler, help_handler
from report_handler import (
    bike_report_conversation_handler,
    list_reports_handler,
)
from admin_handler import admin_conversation_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Shared secret for internal API calls from Master Hub
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared existing webhooks for clean polling.")
    except Exception as e:
        logger.warning(f"Could not clear webhook: {e}")


class BotAPIHandler(BaseHTTPRequestHandler):
    """HTTP API server that exposes user data to the Master Hub app."""

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/users":
            # GET users - open for master hub (no secret needed for reads)
            self._get_users()
        elif path == "/health" or path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK - Fleet Bike Bot is running")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/users/toggle_access":
            self._check_auth_and_serve(self._toggle_access)
        elif path == "/api/users/change_role":
            self._check_auth_and_serve(self._change_role)
        elif path == "/api/users/delete":
            self._check_auth_and_serve(self._delete_user)
        else:
            self.send_error(404, "Not Found")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        pass

    def _check_auth_and_serve(self, handler_fn):
        secret = self.headers.get("X-Internal-Secret", "")
        if secret != INTERNAL_API_SECRET:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
            return
        handler_fn()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return {}

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _get_users(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT user_id, username, full_name, role, is_active FROM users ORDER BY rowid ASC")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            self._send_json(rows)
        except Exception as e:
            logger.error(f"API get_users error: {e}")
            self._send_json([], status=500)

    def _toggle_access(self):
        payload = self._read_json_body()
        user_id = payload.get("user_id")
        is_active = payload.get("is_active", 1)
        if user_id is None:
            self._send_json({"error": "user_id required"}, status=400)
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
            conn.commit()
            conn.close()
            self._send_json({"status": "ok"})
        except Exception as e:
            logger.error(f"API toggle_access error: {e}")
            self._send_json({"error": str(e)}, status=500)

    def _change_role(self):
        payload = self._read_json_body()
        user_id = payload.get("user_id")
        role = payload.get("role", "partner")
        if user_id is None or role not in ("admin", "partner"):
            self._send_json({"error": "Invalid params"}, status=400)
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET role = ?, is_active = 1 WHERE user_id = ?", (role, user_id))
            conn.commit()
            conn.close()
            self._send_json({"status": "ok"})
        except Exception as e:
            logger.error(f"API change_role error: {e}")
            self._send_json({"error": str(e)}, status=500)

    def _delete_user(self):
        payload = self._read_json_body()
        user_id = payload.get("user_id")
        if user_id is None:
            self._send_json({"error": "user_id required"}, status=400)
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            self._send_json({"status": "ok"})
        except Exception as e:
            logger.error(f"API delete_user error: {e}")
            self._send_json({"error": str(e)}, status=500)


def start_api_server():
    port = int(os.getenv("PORT", "8080"))
    HTTPServer.allow_reuse_address = True
    try:
        server = HTTPServer(("0.0.0.0", port), BotAPIHandler)
        logger.info(f"Fleet Bot API server running on port {port}.")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start API server on port {port}: {e}")


async def group_id_handler(update, context):
    chat = update.effective_chat
    if chat:
        await update.message.reply_text(
            f"📌 **ID этой группы:** `{chat.id}`\n\n"
            f"Чтобы бот отправлял отчёты сюда, укажите этот ID в `.env`:\n`GROUP_CHAT_ID={chat.id}`",
            parse_mode="Markdown"
        )


def main():
    threading.Thread(target=start_api_server, daemon=True).start()

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not configured in environment or .env file!")
        print("\n[!] ERROR: BOT_TOKEN is missing. Please set BOT_TOKEN in your .env file.\n")
        sys.exit(1)

    # 1. Initialize SQLite Database
    init_db(DB_PATH)
    logger.info(f"Initialized SQLite database at '{DB_PATH}'.")

    # 2. Initialize Google Sheets Sync
    sheets_sync = SheetsSyncManager()

    # 3. Build Telegram Bot Application
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.bot_data["sheets_sync"] = sheets_sync

    # 4. Register Conversation Handlers
    application.add_handler(admin_conversation_handler)
    application.add_handler(bike_report_conversation_handler)

    # 5. Register Command Handlers
    from telegram.ext import MessageHandler, filters
    from report_handler import cancel_report, start_report
    application.add_handler(MessageHandler(filters.Regex(r"(?i)(bekor|отмен|cancel)"), cancel_report))
    application.add_handler(MessageHandler(filters.Regex(r"(?i)(qaytadan|заново)"), start_report))

    application.add_handler(PrefixHandler("/", ["start"], start_handler))
    application.add_handler(PrefixHandler("/", ["help"], help_handler))
    application.add_handler(PrefixHandler("/", ["reports", "отчеты", "отчёты"], list_reports_handler))
    application.add_handler(CommandHandler("group_id", group_id_handler))

    # 6. Run Bot
    logger.info("Telegram Fleet Bike Report Bot started. Polling for updates...")
    try:
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        if "Conflict" in str(e):
            logger.error("=========================================================================")
            logger.error(" ОШИБКА КОНФЛИКТА (telegram.error.Conflict):")
            logger.error(" С этим BOT_TOKEN одновременно запущена ДРУГАЯ копия бота!")
            logger.error(" Остановите запущенную копию или измените BOT_TOKEN в файле .env.")
            logger.error("=========================================================================")
        else:
            logger.error(f"Bot execution error: {e}")


if __name__ == "__main__":
    main()
