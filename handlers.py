import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import DB_PATH, ADMIN_IDS
from database import is_user_admin

logger = logging.getLogger(__name__)

def get_main_keyboard(user_id: int, username: str = None) -> ReplyKeyboardMarkup:
    is_admin = is_user_admin(user_id, username, ADMIN_IDS, DB_PATH) if user_id else False
    buttons = [["📝 Заполнить отчёт (Rich)"]]
    if is_admin:
        buttons.append(["/admin", "/reports"])
    else:
        buttons.append(["/reports", "/help"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = get_main_keyboard(user.id, user.username if user else None)

    help_text = (
        "💎 <b>Бот отчётов Rich Байки (Ташкент)</b>\n\n"
        "Учёт и ежедневная отчётность по гибридам Rich в городе Ташкент.\n\n"
        "<b>📋 Команды бота:</b>\n"
        "• <code>/report</code> или кнопка ниже — <b>Заполнить отчёт Rich</b>\n"
        "• <code>/reports</code> — <b>Просмотреть историю отчётов</b>\n"
        "• <code>/cancel</code> — <b>Отменить ввод</b>\n"
    )

    if user and is_user_admin(user.id, user.username, ADMIN_IDS, DB_PATH):
        help_text += "• <code>/admin</code> — <b>Панель администратора</b>\n"

    await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=keyboard)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)
