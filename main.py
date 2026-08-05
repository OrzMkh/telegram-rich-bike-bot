import os
import sys
import logging
import threading
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from server import run_master_server

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8951006941:AAH2Wc2j2AH1aCvui1Bflr7puDStzHtwNNI").strip()

def get_current_web_app_url():
    load_dotenv(override=True)
    return os.getenv("WEB_APP_URL", "https://telegram-master-hub-bot.onrender.com").strip()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Администратор"
    current_url = get_current_web_app_url()

    text = (
        f"👑 **Единый Центр Управления (Master Hub)**\n\n"
        f"Здравствуйте, **{name}**!\n"
        f"Добро пожаловать в единый пульт управления всеми системами и ботами:\n\n"
        f"• 🛵 **FlitGo Байки** — статистика парка, допуски и отчёты\n"
        f"• 📋 **FlitGo Задачи** — отслеживание SLA и задач команды\n"
        f"• 💰 **Налоги & ЗП (ТК РУз)** — расчёт аванса, ЗП и ФОТ по графику\n"
        f"• ⚙️ **Управление ботами** — подключение и привязка токенов\n"
        f"• 💎 **Система Rich** — сервисы и аналитика бренда Rich\n\n"
        f"👇 Нажмите синюю кнопку **«🚀 Открыть Центр Управления»** ниже:"
    )

    inline_kb = [
        [InlineKeyboardButton("🌐 Открыть Центр Управления", web_app=WebAppInfo(url=current_url))]
    ]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )

from telegram.ext import CallbackQueryHandler, MessageHandler, filters
import sqlite3

TASKS_DB_PATH = r"C:\Users\Mujohid\.gemini\antigravity-ide\scratch\telegram-task-manager-bot\tasks.db"
TARGET_CHAT_ID = "-1002638798110"

async def dispute_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    logger.info(f"=== DISPUTE CALLBACK TRIGGERED: {data} from user @{query.from_user.username} ({query.from_user.id}) ===")

    try:
        await query.answer("⚖️ Оспаривание начато!\n\nНапишите в этот чат причину несогласия.", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to answer callback query: {e}")

    if data.startswith("dispute_task_"):
        task_id = data.replace("dispute_task_", "")
        user = query.from_user
        username = f"@{user.username}" if user.username else user.first_name

        context.user_data["awaiting_dispute_for_task"] = task_id

        chat_id = query.message.chat_id if query.message else int(TARGET_CHAT_ID)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚖️ <b>ОСПАРИВАНИЕ ОЦЕНКИ ЗАДАЧИ #{task_id}</b>\n\n"
                     f"👤 <b>{username}</b>, напишите прямо следующим сообщением в этот чат причину вашей оценки / несогласия:\n"
                     f"<i>(Например: Задержка произошла из-за ожидания ответа от курьера...)</i>",
                parse_mode="HTML"
            )
            logger.info(f"Sent dispute prompt for task #{task_id} to chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send dispute prompt message: {e}")


async def dispute_reason_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    awaiting_task_id = context.user_data.get("awaiting_dispute_for_task")
    if not awaiting_task_id:
        return

    reason_text = update.message.text.strip()
    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    context.user_data.pop("awaiting_dispute_for_task", None)

    try:
        conn = sqlite3.connect(TASKS_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE tasks SET is_disputed = 1, rating_comment = rating_comment || ' [Оспаривание от ' || ? || ': ' || ? || ']' WHERE id = ?", (username, reason_text, awaiting_task_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update dispute in DB: {e}")

    await update.message.reply_text(
        f"✅ <b>АРГУМЕНТ СОХРАНЁН И ОТПРАВЛЕН!</b>\n\n"
        f"Ваше пояснение по задаче #{awaiting_task_id} передано на пересмотр супервайзеру:\n"
        f"💬 <i>«{reason_text}»</i>",
        parse_mode="HTML"
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def set_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = (user.username or "").lower().replace("@", "").strip()

    if username not in ["orzmkh", "isslamov", "axi0603", "silent_trickster"]:
        await update.message.reply_text("⛔ У вас нет прав для изменения пароля.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("🔑 **Использование команды:**\n`/setpassword НОВЫЙ_ПАРОЛЬ`\n\nПример: `/setpassword 9999`", parse_mode="Markdown")
        return

    new_pwd = args[0].strip()
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    pwd_set = False
    for line in lines:
        if line.startswith("MASTER_APP_PASSWORD="):
            new_lines.append(f"MASTER_APP_PASSWORD={new_pwd}\n")
            pwd_set = True
        else:
            new_lines.append(line)

    if not pwd_set:
        new_lines.append(f"\nMASTER_APP_PASSWORD={new_pwd}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    import server
    server.MASTER_APP_PASSWORD = new_pwd

    await update.message.reply_text(f"✅ **Пароль успешно обновлён!**\n\n🔑 Новый пароль доступа: `{new_pwd}`", parse_mode="Markdown")

from zoneinfo import ZoneInfo
import datetime

async def send_daily_10am_tasks_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Executing daily 10:00 AM tasks digest...")
    if not os.path.exists(TASKS_DB_PATH):
        return

    try:
        conn = sqlite3.connect(TASKS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, task_text, assignee, priority, sla_deadline FROM tasks WHERE status != 'Done' ORDER BY assignee, id ASC")
        rows = c.fetchall()
        conn.close()

        if not rows:
            msg = (
                "🌅 <b>Утренний отчёт по задачам (10:00 AM)</b>\n\n"
                "🎉 <b>Отличная работа!</b> На сегодня нет активных задач в работе."
            )
        else:
            tasks_by_assignee = {}
            for r in rows:
                tid, text, assignee, priority, sla = r[0], r[1], r[2], r[3], r[4]
                if assignee not in tasks_by_assignee:
                    tasks_by_assignee[assignee] = []
                tasks_by_assignee[assignee].append((tid, text, priority, sla))

            lines = ["🌅 <b>Ежедневный список задач на сегодня (10:00 AM)</b>\n"]
            for assignee, tasks in tasks_by_assignee.items():
                lines.append(f"👤 <b>Исполнитель: {assignee}</b> ({len(tasks)} задач)")
                for tid, text, priority, sla in tasks:
                    prio_icon = "🔴" if priority == "High" else ("🟡" if priority == "Medium" else "🟢")
                    lines.append(f"  • #{tid} {prio_icon} <b>{text}</b> (⏱ SLA: {sla})")
                lines.append("")

            lines.append("🚀 Желаем продуктивного рабочего дня!")
            msg = "\n".join(lines)

        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=msg,
            parse_mode="HTML"
        )
        logger.info(f"Daily 10:00 AM digest sent to {TARGET_CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to send daily 10am digest: {e}")

async def send_digest_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Формирование и отправка утренней сводки в группу...")
    await send_daily_10am_tasks_digest(context)

import asyncio

async def daily_reminder_loop(app):
    while True:
        try:
            tz_tashkent = datetime.timezone(datetime.timedelta(hours=5))
            now = datetime.datetime.now(tz_tashkent)
            target = now.replace(hour=10, minute=0, second=0, microsecond=0)
            if now >= target:
                target += datetime.timedelta(days=1)
            
            seconds_until_target = (target - now).total_seconds()
            logger.info(f"Daily 10:00 AM reminder loop sleeping for {seconds_until_target:.1f} seconds...")
            await asyncio.sleep(seconds_until_target)

            class FakeContext:
                def __init__(self, bot):
                    self.bot = bot
            await send_daily_10am_tasks_digest(FakeContext(app.bot))
        except Exception as e:
            logger.error(f"Error in daily_reminder_loop: {e}")
            await asyncio.sleep(60)

from rich_bot import setup_rich_bot_application

def run_rich_bot():
    try:
        rich_app = setup_rich_bot_application()
        logger.info("Rich Hybrid Bot starting polling on token 8803642782...")
        rich_app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
    except Exception as e:
        logger.error(f"Rich Hybrid Bot thread error: {e}")

async def post_init_callback(application):
    asyncio.create_task(daily_reminder_loop(application))
    logger.info("Started native daily 10:00 AM asyncio reminder task.")
    url = get_current_web_app_url()
    try:
        from telegram import MenuButtonWebApp, WebAppInfo
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🚀 Master Hub App", web_app=WebAppInfo(url=url))
        )
        logger.info(f"Successfully updated Telegram Menu Button to: {url}")
    except Exception as e:
        logger.error(f"Failed to set Telegram Menu Button: {e}")

def main():
    port = int(os.getenv("PORT", "8085"))
    threading.Thread(target=run_master_server, args=(port,), daemon=True).start()
    threading.Thread(target=run_rich_bot, daemon=True).start()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init_callback)
        .build()
    )

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("setpassword", set_password_handler))
    application.add_handler(CommandHandler("senddigest", send_digest_command_handler))
    application.add_handler(CallbackQueryHandler(dispute_callback_handler, pattern="^dispute_task_"))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), dispute_reason_input_handler))

    logger.info("Master Hub Bot started. Listening for commands...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)

if __name__ == "__main__":
    main()
