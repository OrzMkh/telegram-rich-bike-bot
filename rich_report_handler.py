import datetime
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from database import add_rich_report, get_rich_reports
from config import DB_PATH, CITY, GROUP_CHAT_ID

logger = logging.getLogger(__name__)

(
    REPORT_DATE,
    ISSUED,
    RETURNED,
    TOTAL_IN_TRIP,
    NEW_BIKES,
    BATTERIES,
    BROKEN_BIKES,
    REASONS,
    COMMENT,
    CONFIRM,
) = range(10)

CANCEL_TEXT = "❌ Отмена"
SKIP_TEXT = "⏩ Пропустить"
CONFIRM_TEXT = "✅ Отправить"
RESTART_TEXT = "✏️ Заполнить заново"

def get_today_str() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["rich_report"] = {"city": CITY}
    today = get_today_str()
    reply_keyboard = [[f"📅 Сегодня ({today})"], [CANCEL_TEXT]]
    
    text = (
        f"💎 **Заполнение отчёта «Rich Гибриды» ({CITY})**\n\n"
        "Шаг 1 из 9: **Укажите дату отчёта** (например: `31.07.2026` или нажмите кнопку ниже):"
    )
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return REPORT_DATE

async def date_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)
    
    report_date = get_today_str() if "📅 Сегодня" in text else text
    context.user_data["rich_report"]["report_date"] = report_date

    reply_keyboard = [[CANCEL_TEXT]]
    await update.message.reply_text(
        f"✅ Дата: **{report_date}** | Город: **{CITY}**\n\n"
        "Шаг 2 из 9: **Укажите количество выданных гибридов Rich («Выдано»)**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return ISSUED

async def issued_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["issued"] = text
    reply_keyboard = [[CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 3 из 9: **Укажите количество вернувшихся гибридов Rich («Вернули»)**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return RETURNED

async def returned_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["returned"] = text
    reply_keyboard = [[CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 4 из 9: **Укажите общее количество гибридов в поездке («Всего на линии»)**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return TOTAL_IN_TRIP

async def total_in_trip_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["total_in_trip"] = text
    reply_keyboard = [["0"], [CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 5 из 9: **Укажите количество новых полученных гибридов Rich («Новые гибриды»)**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return NEW_BIKES

async def new_bikes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["new_bikes"] = text
    reply_keyboard = [["⚡️ 100% Все заряжены"], ["🔋 Обычный уровень"], [CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 6 из 9: **Укажите статус аккумуляторов / зарядки (АКБ)**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return BATTERIES

async def batteries_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["batteries_status"] = text
    reply_keyboard = [["0"], [CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 7 из 9: **Укажите количество неисправных / сломанных гибридов Rich**:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return BROKEN_BIKES

async def broken_bikes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    context.user_data["rich_report"]["broken_bikes"] = text
    reply_keyboard = [[SKIP_TEXT], [CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 8 из 9: **Укажите причины поломок / необходимое ТО** (или нажмите «⏩ Пропустить»):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return REASONS

async def reasons_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    reasons = "—" if text == SKIP_TEXT else text
    context.user_data["rich_report"]["return_reasons"] = reasons

    reply_keyboard = [[SKIP_TEXT], [CANCEL_TEXT]]
    await update.message.reply_text(
        "Шаг 9 из 9: **Добавьте комментарий механика / партнёра** (или нажмите «⏩ Пропустить»):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return COMMENT

async def comment_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    comment = "—" if text == SKIP_TEXT else text
    context.user_data["rich_report"]["comment"] = comment

    r = context.user_data["rich_report"]
    summary_text = (
        f"📋 **ПРЕДПРОСМОТР ОТЧЁТА RICH ({CITY})**\n\n"
        f"📅 **Дата:** `{r.get('report_date')}`\n"
        f"📍 **Город:** `{CITY}`\n"
        f"🛵 **Выдано гибридов:** `{r.get('issued')}`\n"
        f"↩️ **Вернули:** `{r.get('returned')}`\n"
        f"⚡️ **Всего на линии:** `{r.get('total_in_trip')}`\n"
        f"✨ **Новые гибриды:** `{r.get('new_bikes')}`\n"
        f"🔋 **Статус АКБ:** `{r.get('batteries_status')}`\n"
        f"🛠 **Сломанные / ТО:** `{r.get('broken_bikes')}`\n"
        f"⚠️ **Причины поломок:** `{r.get('return_reasons')}`\n"
        f"💬 **Комментарий:** `{r.get('comment')}`\n\n"
        "Проверьте данные и нажмите кнопку **«✅ Отправить»** ниже:"
    )

    reply_keyboard = [[CONFIRM_TEXT, RESTART_TEXT], [CANCEL_TEXT]]
    await update.message.reply_text(
        summary_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return CONFIRM

async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == CANCEL_TEXT:
        return await cancel_report(update, context)

    if text == RESTART_TEXT:
        return await start_report(update, context)

    if text == CONFIRM_TEXT:
        user = update.effective_user
        rep = context.user_data.get("rich_report", {})
        rep["user_id"] = user.id if user else None
        rep["username"] = user.full_name or user.username or f"User_{user.id}" if user else "Партнёр"
        rep["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Save to SQLite DB
        saved_report = add_rich_report(rep, db_path=DB_PATH)

        # 2. Sync to Google Sheets
        sheets_sync = context.bot_data.get("sheets_sync")
        if sheets_sync:
            try:
                sheets_sync.append_rich_report(saved_report)
            except Exception as e:
                logger.error(f"Failed to sync Rich Report to Google Sheets: {e}")

        # 3. Post notification to Telegram group if configured
        if GROUP_CHAT_ID and str(GROUP_CHAT_ID) != "0":
            try:
                group_msg = (
                    f"💎 **НОВЫЙ ОТЧЁТ RICH ({CITY})**\n\n"
                    f"👤 **Партнёр:** `{saved_report.get('username')}`\n"
                    f"📅 **Дата:** `{saved_report.get('report_date')}`\n"
                    f"🛵 **Выдано:** `{saved_report.get('issued')}` | ↩️ **Вернули:** `{saved_report.get('returned')}`\n"
                    f"⚡️ **На линии:** `{saved_report.get('total_in_trip')}` | ✨ **Новые:** `{saved_report.get('new_bikes')}`\n"
                    f"🔋 **АКБ:** `{saved_report.get('batteries_status')}` | 🛠 **Сломанные:** `{saved_report.get('broken_bikes')}`\n"
                    f"💬 **Комментарий:** _{saved_report.get('comment')}_\n"
                    f"🆔 **ID отчёта:** `#{saved_report.get('id')}`"
                )
                await context.bot.send_message(
                    chat_id=int(GROUP_CHAT_ID),
                    text=group_msg,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send Rich report to Telegram group: {e}")

        await update.message.reply_text(
            f"🎉 **Отчёт «Rich Гибриды ({CITY})» успешно сохранён!**\n\n"
            f"ID отчёта: `#{saved_report.get('id')}`\n"
            f"Спасибо за работу!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.pop("rich_report", None)
        return ConversationHandler.END

    return CONFIRM

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("rich_report", None)
    await update.message.reply_text(
        "❌ Заполнение отчёта отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def list_reports_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reports = get_rich_reports(limit=10, db_path=DB_PATH)
    if not reports:
        await update.message.reply_text("📭 В базе пока нет отправленных отчётов Rich.")
        return

    text = f"📋 **Последние 10 отчётов Rich ({CITY}):**\n\n"
    for r in reports:
        text += (
            f"🔹 **#{r['id']}** ({r['report_date']}) — `{r['username']}`\n"
            f"   🛵 Выдано: `{r['issued']}` | Вернули: `{r['returned']}` | На линии: `{r['total_in_trip']}`\n"
            f"   🛠 Сломанные: `{r['broken_bikes']}` | 🔋 АКБ: `{r['batteries_status']}`\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")

rich_report_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler("report", start_report),
        MessageHandler(filters.Regex(r"(?i)(report|отчёт|отчет|байк|rich)"), start_report),
    ],
    states={
        REPORT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_step)],
        ISSUED: [MessageHandler(filters.TEXT & ~filters.COMMAND, issued_step)],
        RETURNED: [MessageHandler(filters.TEXT & ~filters.COMMAND, returned_step)],
        TOTAL_IN_TRIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, total_in_trip_step)],
        NEW_BIKES: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_bikes_step)],
        BATTERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, batteries_step)],
        BROKEN_BIKES: [MessageHandler(filters.TEXT & ~filters.COMMAND, broken_bikes_step)],
        REASONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reasons_step)],
        COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, comment_step)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_step)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_report),
        MessageHandler(filters.Regex(r"(?i)(bekor|отмен|cancel)"), cancel_report),
    ],
)
