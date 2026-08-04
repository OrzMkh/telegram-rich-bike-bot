import asyncio
import logging
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config import BOT_TOKEN, DB_PATH, CITY
from database import init_db
from sheets_sync import SheetsSyncManager
from rich_report_handler import (
    rich_report_conversation_handler,
    list_reports_handler,
    start_report,
    cancel_report,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared webhooks for clean Rich Bot polling.")
    except Exception as e:
        logger.warning(f"Could not clear webhook: {e}")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        super().end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"OK - Rich Bike Bot ({CITY}) is running".encode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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

async def start_handler(update: Update, context):
    user = update.effective_user
    name = user.first_name if user else "Партнёр"
    welcome_text = (
        f"💎 **Бот отчётов Rich Гибриды ({CITY})**\n\n"
        f"Здравствуйте, **{name}**!\n"
        f"Этот бот предназначен для заполнения и учёта отчётов по **гибридам Rich** в городе {CITY}.\n\n"
        f"📌 **Доступные команды:**\n"
        f"• `/report` — Заполнить новый отчёт по гибридам Rich\n"
        f"• `/reports` — Просмотреть последние отчёты\n"
        f"• `/cancel` — Отменить заполнение отчёта\n\n"
        f"👇 Для начала заполнения отправьте `/report` или словесный запрос (например: *отчёт*):"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

def main():
    threading.Thread(target=start_health_server, daemon=True).start()

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing!")
        sys.exit(1)

    init_db(DB_PATH)
    logger.info(f"Initialized SQLite database at '{DB_PATH}'.")

    sheets_sync = SheetsSyncManager()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.bot_data["sheets_sync"] = sheets_sync

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("reports", list_reports_handler))
    application.add_handler(rich_report_conversation_handler)

    application.add_handler(MessageHandler(filters.Regex(r"(?i)(bekor|отмен|cancel)"), cancel_report))
    application.add_handler(MessageHandler(filters.Regex(r"(?i)(qaytadan|заново)"), start_report))

    logger.info(f"Rich Bike Bot ({CITY}) started. Listening for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
