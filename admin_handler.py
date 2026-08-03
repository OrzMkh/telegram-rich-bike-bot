import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import ADMIN_IDS, DB_PATH
from bot.handlers import get_main_keyboard
from db.database import (
    is_user_admin,
    get_all_cities,
    add_city,
    delete_city,
    toggle_city_bike_types,
    update_city_total_bikes,
    get_all_users,
    authorize_user,
    deauthorize_user,
    get_bike_reports,
)

logger = logging.getLogger(__name__)

# Conversation states for Admin input
WAITING_ADD_CITY = 100
WAITING_ADD_USER = 101
WAITING_EDIT_CITY_TOTAL = 102

def check_admin(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    return is_user_admin(user.id, user.username, ADMIN_IDS, DB_PATH)

def get_admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏙 Управление городами", callback_data="admin_cities")],
        [InlineKeyboardButton("👥 Партнёры и доступы", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Все отчёты", callback_data="admin_reports")],
        [InlineKeyboardButton("❌ Закрыть панель", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_admin(update):
        await update.message.reply_text("⛔️ У вас нет прав администратора.")
        return ConversationHandler.END

    text = (
        "⚙️ **Панель Администратора**\n\n"
        "Выберите действие в меню ниже:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_admin_menu_keyboard())

def render_cities_admin_keyboard(cities):
    text = "🏙 **Настройка городов и общего количества байков:**\n\n"
    keyboard = []
    if not cities:
        text += "Список городов пока пуст.\n"
    else:
        for c in cities:
            has_types = c.get("has_bike_types", 1) == 1
            total_b = c.get("total_bikes", 80)
            status_str = "✅ Новые/Старые" if has_types else "❌ Без типов"
            text += f"• **{c['name']}** — Всего: **{total_b} байков** ({status_str})\n"
            
            keyboard.append([
                InlineKeyboardButton(f"🚲 {c['name']}: Изменить Всего ({total_b})", callback_data=f"admin_set_total_{c['id']}")
            ])
            keyboard.append([
                InlineKeyboardButton(f"🔄 {c['name']}: {'Выкл. Новые/Старые' if has_types else 'Вкл. Новые/Старые'}", callback_data=f"admin_toggle_city_{c['id']}"),
                InlineKeyboardButton(f"❌ Удалить", callback_data=f"admin_del_city_{c['id']}")
            ])

    keyboard.append([InlineKeyboardButton("➕ Добавить новый город", callback_data="admin_add_city")])
    keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data="admin_menu")])
    return text, InlineKeyboardMarkup(keyboard)

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not check_admin(update):
        await query.edit_message_text("⛔️ Доступ запрещён.")
        return

    data = query.data

    if data == "admin_menu":
        await query.edit_message_text(
            "⚙️ **Панель Администратора**\n\nВыберите действие в меню ниже:",
            parse_mode="Markdown",
            reply_markup=get_admin_menu_keyboard(),
        )

    elif data == "admin_close":
        await query.edit_message_text("👋 Админ-панель закрыта.")

    elif data == "admin_cities":
        cities = get_all_cities(db_path=DB_PATH)
        text, reply_markup = render_cities_admin_keyboard(cities)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    elif data.startswith("admin_toggle_city_"):
        city_id = int(data.replace("admin_toggle_city_", ""))
        toggle_city_bike_types(city_id, db_path=DB_PATH)
        cities = get_all_cities(db_path=DB_PATH)
        text, reply_markup = render_cities_admin_keyboard(cities)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

    elif data.startswith("admin_set_total_"):
        city_id = int(data.replace("admin_set_total_", ""))
        cities = get_all_cities(db_path=DB_PATH)
        target_city = next((c for c in cities if c["id"] == city_id), None)
        if target_city:
            context.user_data["editing_city_id"] = city_id
            context.user_data["editing_city_name"] = target_city["name"]
            curr_total = target_city.get("total_bikes", 80)
            await query.edit_message_text(
                f"✍️ **Введите общее количество байков для города «{target_city['name']}»** (текущее: `{curr_total}`):",
                parse_mode="Markdown"
            )
            return WAITING_EDIT_CITY_TOTAL

    elif data == "admin_add_city":
        await query.edit_message_text(
            "✍️ **Введите название нового города** (например: `Коканд` или `Ташкент`):",
            parse_mode="Markdown"
        )
        return WAITING_ADD_CITY

    elif data.startswith("admin_del_city_"):
        city_id = int(data.replace("admin_del_city_", ""))
        delete_city(city_id, db_path=DB_PATH)
        await query.edit_message_text("✅ Город удалён!")

    elif data == "admin_users":
        users = get_all_users(db_path=DB_PATH)
        text = "👥 **Партнёры и Разрешения:**\n\n"
        keyboard = []
        if not users:
            text += "Пока нет настроенных пользователей.\n"
        else:
            for u in users:
                status = "✅ Доступ разрешен" if u["is_active"] == 1 else "⛔️ Доступ закрыт"
                role_str = "👑 Админ" if u["role"] == "admin" else "👤 Партнер"
                text += f"• **{u['full_name'] or u['username']}** (`ID: {u['user_id']}`) — {role_str} ({status})\n"
                if u["is_active"] == 1 and u["role"] != "admin":
                    keyboard.append([InlineKeyboardButton(f"🚫 Отозвать доступ ID {u['user_id']}", callback_data=f"admin_del_user_{u['user_id']}")])

        keyboard.append([InlineKeyboardButton("➕ Добавить партнёра по ID", callback_data="admin_add_user")])
        keyboard.append([InlineKeyboardButton("◀️ В меню", callback_data="admin_menu")])

        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_add_user":
        await query.edit_message_text(
            "✍️ **Введите Telegram ID пользователя**, которому нужно разрешить доступ (например: `123456789`):",
            parse_mode="Markdown"
        )
        return WAITING_ADD_USER

    elif data.startswith("admin_del_user_"):
        uid = int(data.replace("admin_del_user_", ""))
        deauthorize_user(uid, db_path=DB_PATH)
        await query.edit_message_text("🚫 Доступ пользователю отозван.")

    elif data == "admin_reports":
        reports = get_bike_reports(limit=10, db_path=DB_PATH)
        text = "📊 **Последние 10 отчётов:**\n\n"
        if not reports:
            text += "Отчёты отсутствуют."
        else:
            for r in reports:
                city_str = f" [{r['city']}]" if r.get('city') else ""
                text += f"🔹 **Отчёт #{r['id']}**{city_str} от {r['report_date']}\n👤 Партнёр: {r['username']}\n📊 Выдано: {r['issued']} | Вернули: {r['returned']}\n\n"

        keyboard = [[InlineKeyboardButton("◀️ В меню", callback_data="admin_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_city_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    main_kb = get_main_keyboard(user.id, user.username) if user else None
    city_name = update.message.text.strip()
    if add_city(city_name, db_path=DB_PATH):
        await update.message.reply_text(f"🎉 Город **«{city_name}»** успешно добавлен!", parse_mode="Markdown", reply_markup=main_kb)
    else:
        await update.message.reply_text("⚠️ Не удалось добавить город (возможно, он уже существует).", reply_markup=main_kb)

    return ConversationHandler.END

async def handle_city_total_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    main_kb = get_main_keyboard(user.id, user.username) if user else None
    input_text = update.message.text.strip()
    city_id = context.user_data.get("editing_city_id")
    city_name = context.user_data.get("editing_city_name", "город")

    if input_text.isdigit() and int(input_text) > 0:
        new_total = int(input_text)
        update_city_total_bikes(city_id, new_total, db_path=DB_PATH)
        await update.message.reply_text(
            f"🎉 Общее количество байков для города **«{city_name}»** успешно обновлено: **{new_total} шт.**!",
            parse_mode="Markdown",
            reply_markup=main_kb
        )
    else:
        await update.message.reply_text("⚠️ Пожалуйста, введите положительное число (например: 80 или 100).", reply_markup=main_kb)

    context.user_data.pop("editing_city_id", None)
    context.user_data.pop("editing_city_name", None)
    return ConversationHandler.END

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    main_kb = get_main_keyboard(user.id, user.username) if user else None
    input_text = update.message.text.strip()
    if not input_text.isdigit():
        await update.message.reply_text("⚠️ Пожалуйста, введите числовой Telegram ID пользователя.")
        return WAITING_ADD_USER

    uid = int(input_text)
    authorize_user(user_id=uid, username=f"User_{uid}", full_name="Партнёр", role="partner", db_path=DB_PATH)
    await update.message.reply_text(f"✅ Пользователю с Telegram ID `{uid}` успешно разрешен доступ!", parse_mode="Markdown", reply_markup=main_kb)
    return ConversationHandler.END

admin_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler("admin", admin_start),
        CallbackQueryHandler(admin_callback_handler),
    ],
    states={
        WAITING_ADD_CITY: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_city_input)],
        WAITING_EDIT_CITY_TOTAL: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_city_total_input)],
        WAITING_ADD_USER: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_input)],
    },
    fallbacks=[
        CommandHandler("admin", admin_start),
    ],
)
