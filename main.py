import asyncio
import logging
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import ApplicationBuilder, CommandHandler, PrefixHandler

from config import BOT_TOKEN, DB_PATH
from db.database import init_db
from db.sheets_sync import SheetsSyncManager
from bot.handlers import start_handler, help_handler
from bot.report_handler import (
    bike_report_conversation_handler,
    list_reports_handler,
)
from bot.admin_handler import admin_conversation_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared existing webhooks for clean polling.")
    except Exception as e:
        logger.warning(f"Could not clear webhook: {e}")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Bike Report Bot is running")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    HTTPServer.allow_reuse_address = True
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP server running on port {port}.")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start health check server on port {port}: {e}")

async def group_id_handler(update, context):
    chat = update.effective_chat
    if chat:
        await update.message.reply_text(
            f"📌 **ID этой группы:** `{chat.id}`\n\n"
            f"Чтобы бот отправлял отчёты сюда, укажите этот ID в `.env`:\n`GROUP_CHAT_ID={chat.id}`",
            parse_mode="Markdown"
        )

def main():
    threading.Thread(target=start_health_server, daemon=True).start()

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
    from bot.report_handler import cancel_report, start_report
    application.add_handler(MessageHandler(filters.Regex(r"(?i)(bekor|отмен|cancel)"), cancel_report))
    application.add_handler(MessageHandler(filters.Regex(r"(?i)(qaytadan|заново)"), start_report))

    application.add_handler(PrefixHandler("/", ["start"], start_handler))
    application.add_handler(PrefixHandler("/", ["help"], help_handler))
    application.add_handler(PrefixHandler("/", ["reports", "отчеты", "отчёты"], list_reports_handler))
    application.add_handler(CommandHandler("group_id", group_id_handler))

    # 6. Run Bot
    logger.info("Telegram Bike Report Bot started. Polling for updates...")
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
