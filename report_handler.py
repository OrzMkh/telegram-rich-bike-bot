import datetime
import logging
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import urllib.request
import urllib.parse
import json

from database import (
    add_bike_report,
    get_bike_reports,
    get_all_cities,
    get_city_by_name,
    is_user_authorized,
)
from config import DB_PATH, ADMIN_IDS, GROUP_CHAT_IDS
from handlers import get_main_keyboard
from i18n import t, LANG_RU, LANG_UZ, get_date_keyboard_buttons, get_step_nav_buttons

logger = logging.getLogger(__name__)

def translate_uz_to_ru(text: str) -> str:
    if not text or text == "-" or not isinstance(text, str):
        return text

    text_clean = text.strip()
    if not text_clean or text_clean == "-":
        return text_clean

    preset_map = {
        "texnik ko'rik": "Плановое ТО",
        "texnik korik": "Плановое ТО",
        "to": "Плановое ТО",
        "buzildi": "Поломка",
        "buzilgan": "Поломка",
        "nosozlik": "Поломка",
        "tormoz": "Поломка тормозов",
        "mijoz rad etdi": "Отказ клиента",
        "rad etildi": "Отказ клиента",
        "ijara tugadi": "Конец аренды",
        "arenda tugadi": "Конец аренды",
        "akkumulyator": "Проблема с аккумулятором",
        "batareya": "Проблема с аккумулятором",
        "yth": "ДТП / Авария",
        "avariya": "ДТП / Авария",
    }

    lowered = text_clean.lower().strip()
    if lowered in preset_map:
        return preset_map[lowered]

    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ru&dt=t&q=" + urllib.parse.quote(text_clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part[0] in data[0] if part[0])
            return translated if translated else text_clean
    except Exception as e:
        logger.warning(f"Translation failed for '{text_clean}': {e}")
        return text_clean

# Conversation states
(
    SELECT_LANG,
    REPORT_DATE,
    SELECT_CITY,
    ISSUED,
    RETURNED,
    TOTAL_IN_TRIP,
    NEW_BIKES,
    OLD_BIKES,
    BROKEN_BIKES,
    REASONS,
    REASON_COUNT,
    COMMENT,
    CONFIRM,
) = range(13)

CANCEL_TEXTS = ("❌ Отмена", "❌ Bekor qilish", "Отмена", "Bekor qilish")
BACK_TEXTS = ("◀️ Назад", "◀️ Orqaga", "Назад", "Orqaga")
SKIP_TEXTS = ("⏩ Пропустить", "⏩ O'tkazib yuborish")
CONFIRM_TEXTS = ("✅ Отправить", "✅ Yuborish")
RESTART_TEXTS = ("✏️ Заполнить заново", "✏️ Qaytadan to'ldirish")
FINISH_REASONS_TEXTS = ("✅ Завершить ввод причин", "✅ Sabablarni kiritishni yakunlash")
PROCEED_ANYWAY_TEXTS = ("⏩ Всё равно продолжить", "⏩ Baribir davom etish")
ADD_MORE_REASONS_TEXTS = ("➕ Добавить причину", "➕ Yana sabab qo'shish")

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("’", "'").replace("ʼ", "'").replace("ʻ", "'").replace("`", "'")
    return s.strip().lower()

def is_cancel(text: str) -> bool:
    t_norm = normalize_text(text)
    return "bekor" in t_norm or "отмен" in t_norm or any(normalize_text(x) in t_norm for x in CANCEL_TEXTS)

def is_back(text: str) -> bool:
    t_norm = normalize_text(text)
    return "orqaga" in t_norm or "назад" in t_norm or any(normalize_text(x) in t_norm for x in BACK_TEXTS)

def is_confirm(text: str) -> bool:
    t_norm = normalize_text(text)
    return "yubor" in t_norm or "отправ" in t_norm or any(normalize_text(x) in t_norm for x in CONFIRM_TEXTS)

def is_restart(text: str) -> bool:
    t_norm = normalize_text(text)
    return "qaytadan" in t_norm or "заново" in t_norm or "to'ldir" in t_norm or any(normalize_text(x) in t_norm for x in RESTART_TEXTS)

def get_today_str() -> str:
    return datetime.datetime.now().strftime("%d.%m.%Y")

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if user and not is_user_authorized(user.id, user.username, ADMIN_IDS, DB_PATH):
        await update.message.reply_text(
            t("access_denied", "ru"),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["report"] = {}
    reply_keyboard = [[LANG_RU, LANG_UZ]]

    await update.message.reply_text(
        t("select_lang", "ru"),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return SELECT_LANG

async def lang_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if "🇺🇿" in input_text or "o'zbek" in input_text.lower():
        lang = "uz"
    else:
        lang = "ru"

    context.user_data["report"]["lang"] = lang
    date_buttons = get_date_keyboard_buttons(lang)

    await update.message.reply_text(
        t("step_date", lang),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(date_buttons, resize_keyboard=True, one_time_keyboard=True),
    )
    return REPORT_DATE

async def date_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        return await start_report(update, context)

    match = re.search(r"\d{2}\.\d{2}\.\d{4}", input_text)
    if match:
        report_date = match.group(0)
    else:
        report_date = input_text

    context.user_data["report"]["report_date"] = report_date

    return await prompt_city(update, context, lang, report_date)

async def prompt_city(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, report_date: str) -> int:
    cities = get_all_cities(db_path=DB_PATH)
    cancel_lbl = t("cancel", lang)
    back_lbl = t("back", lang)
    if cities:
        city_buttons = [[c["name"]] for c in cities]
        city_buttons.append([back_lbl, cancel_lbl])
        await update.message.reply_text(
            t("date_selected", lang, date=report_date),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(city_buttons, resize_keyboard=True),
        )
        return SELECT_CITY
    else:
        context.user_data["report"]["city"] = "-"
        reply_keyboard = get_step_nav_buttons(lang)
        await update.message.reply_text(
            t("city_selected", lang, city="-"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return ISSUED

async def city_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        date_buttons = get_date_keyboard_buttons(lang)
        await update.message.reply_text(
            t("step_date", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(date_buttons, resize_keyboard=True, one_time_keyboard=True),
        )
        return REPORT_DATE

    context.user_data["report"]["city"] = input_text
    city_info = get_city_by_name(input_text, db_path=DB_PATH)
    if city_info:
        context.user_data["report"]["has_bike_types"] = city_info.get("has_bike_types", 1)
    else:
        context.user_data["report"]["has_bike_types"] = 1

    reply_keyboard = get_step_nav_buttons(lang)
    await update.message.reply_text(
        t("city_selected", lang, city=input_text),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return ISSUED

def is_valid_non_negative_int(text: str) -> bool:
    return text.strip().isdigit()

async def issued_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        report_date = context.user_data.get("report", {}).get("report_date", get_today_str())
        return await prompt_city(update, context, lang, report_date)

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return ISSUED

    context.user_data["report"]["issued"] = input_text
    reply_keyboard = get_step_nav_buttons(lang)
    await update.message.reply_text(
        t("step_returned", lang),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return RETURNED

async def returned_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        city_name = context.user_data.get("report", {}).get("city", "-")
        reply_keyboard = get_step_nav_buttons(lang)
        await update.message.reply_text(
            t("city_selected", lang, city=city_name),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return ISSUED

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return RETURNED

    context.user_data["report"]["returned"] = input_text
    reply_keyboard = get_step_nav_buttons(lang)
    await update.message.reply_text(
        t("step_total_in_trip", lang),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return TOTAL_IN_TRIP

async def total_in_trip_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        reply_keyboard = get_step_nav_buttons(lang)
        await update.message.reply_text(
            t("step_returned", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return RETURNED

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return TOTAL_IN_TRIP

    context.user_data["report"]["total_in_trip"] = input_text
    has_bike_types = context.user_data["report"].get("has_bike_types", 1)
    reply_keyboard = get_step_nav_buttons(lang)

    if has_bike_types == 0:
        context.user_data["report"]["new_bikes"] = "-"
        context.user_data["report"]["old_bikes"] = "-"
        await update.message.reply_text(
            t("step_broken_bikes", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return BROKEN_BIKES
    else:
        await update.message.reply_text(
            t("step_new_bikes", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return NEW_BIKES

async def new_bikes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        reply_keyboard = get_step_nav_buttons(lang)
        await update.message.reply_text(
            t("step_total_in_trip", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return TOTAL_IN_TRIP

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return NEW_BIKES

    context.user_data["report"]["new_bikes"] = input_text
    reply_keyboard = get_step_nav_buttons(lang)
    await update.message.reply_text(
        t("step_old_bikes", lang),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return OLD_BIKES

async def old_bikes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        reply_keyboard = get_step_nav_buttons(lang)
        await update.message.reply_text(
            t("step_new_bikes", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return NEW_BIKES

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return OLD_BIKES

    context.user_data["report"]["old_bikes"] = input_text
    reply_keyboard = get_step_nav_buttons(lang)
    await update.message.reply_text(
        t("step_broken_bikes_full", lang),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return BROKEN_BIKES

async def broken_bikes_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        has_bike_types = context.user_data.get("report", {}).get("has_bike_types", 1)
        reply_keyboard = get_step_nav_buttons(lang)
        if has_bike_types == 0:
            await update.message.reply_text(
                t("step_total_in_trip", lang),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            )
            return TOTAL_IN_TRIP
        else:
            await update.message.reply_text(
                t("step_old_bikes", lang),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            )
            return OLD_BIKES

    if not is_valid_non_negative_int(input_text):
        await update.message.reply_text(
            t("err_must_be_number", lang),
            parse_mode="Markdown",
        )
        return BROKEN_BIKES

    context.user_data["report"]["broken_bikes"] = input_text
    context.user_data["report"]["reasons_list"] = []
    return await prompt_next_reason(update, context)

async def prompt_next_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rep = context.user_data.get("report", {})
    lang = rep.get("lang", "ru")
    returned_str = rep.get("returned", "0")
    
    try:
        match_digits = re.search(r"\d+", returned_str)
        returned_total = int(match_digits.group(0)) if match_digits else int(returned_str)
    except (ValueError, AttributeError):
        returned_total = 0

    reasons_list = rep.get("reasons_list", [])
    used_sum = sum(item["count"] for item in reasons_list)

    if returned_total > 0 and used_sum >= returned_total:
        formatted_reasons = ", ".join(f"{item['reason']} ({item['count']} шт.)" for item in reasons_list)
        rep["return_reasons"] = formatted_reasons
        reply_keyboard = get_step_nav_buttons(lang, include_skip=True)
        await update.message.reply_text(
            t("step_comment", lang),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
        )
        return COMMENT

    num = len(reasons_list) + 1
    intro_text = t("reasons_intro", lang, total=returned_total, sum=used_sum, num=num)
    if reasons_list:
        intro_text += "\n\n📌 **Уже добавлено:**\n" + "\n".join(f"• {item['reason']} — {item['count']} шт." for item in reasons_list)

    cancel_lbl = t("cancel", lang)
    back_lbl = t("back", lang)
    finish_lbl = t("finish_reasons", lang)

    buttons = []
    if used_sum > 0 or returned_total == 0:
        buttons.append([finish_lbl])
    buttons.append([back_lbl, cancel_lbl])

    await update.message.reply_text(
        intro_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return REASONS

async def reasons_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    reasons_list = context.user_data.get("report", {}).get("reasons_list", [])
    returned_str = context.user_data.get("report", {}).get("returned", "0")
    try:
        match_digits = re.search(r"\d+", returned_str)
        returned_total = int(match_digits.group(0)) if match_digits else int(returned_str)
    except (ValueError, AttributeError):
        returned_total = 0

    used_sum = sum(item["count"] for item in reasons_list)

    if input_text in BACK_TEXTS:
        if reasons_list:
            reasons_list.pop()
            return await prompt_next_reason(update, context)
        else:
            has_bike_types = context.user_data.get("report", {}).get("has_bike_types", 1)
            reply_keyboard = get_step_nav_buttons(lang)
            broken_prompt = t("step_broken_bikes_full", lang) if has_bike_types == 1 else t("step_broken_bikes", lang)
            await update.message.reply_text(
                broken_prompt,
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            )
            return BROKEN_BIKES

    if input_text in PROCEED_ANYWAY_TEXTS or input_text in FINISH_REASONS_TEXTS:
        if input_text in FINISH_REASONS_TEXTS and returned_total > 0 and used_sum != returned_total:
            proceed_lbl = t("proceed_anyway", lang)
            add_more_lbl = t("add_more_reasons", lang)
            cancel_lbl = t("cancel", lang)
            back_lbl = t("back", lang)

            warn_btns = [
                [proceed_lbl],
                [add_more_lbl],
                [back_lbl, cancel_lbl]
            ]
            await update.message.reply_text(
                t("sum_warning", lang, sum=used_sum, total=returned_total),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(warn_btns, resize_keyboard=True),
            )
            return REASONS
        else:
            formatted_reasons = ", ".join(f"{item['reason']} ({item['count']} шт.)" for item in reasons_list) if reasons_list else "-"
            context.user_data["report"]["return_reasons"] = formatted_reasons
            reply_keyboard = get_step_nav_buttons(lang, include_skip=True)
            await update.message.reply_text(
                t("step_comment", lang),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            )
            return COMMENT

    if input_text in ADD_MORE_REASONS_TEXTS:
        return await prompt_next_reason(update, context)

    context.user_data["report"]["current_reason_text"] = input_text

    cancel_lbl = t("cancel", lang)
    back_lbl = t("back", lang)
    rem = max(1, returned_total - used_sum)

    count_btns = []
    if rem > 0 and rem not in (1, 2, 5, 10, 20, 50, 100):
        count_btns.append(["1", "2", "5", "10", str(rem)])
    else:
        count_btns.append(["1", "2", "5", "10"])
    count_btns.append(["20", "50", "100"])
    count_btns.append([back_lbl, cancel_lbl])

    await update.message.reply_text(
        t("reason_count_prompt", lang, reason=input_text),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(count_btns, resize_keyboard=True),
    )
    return REASON_COUNT

async def reason_count_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        return await prompt_next_reason(update, context)

    match = re.search(r"\d+", input_text)
    if not match:
        await update.message.reply_text(
            t("err_invalid_number", lang),
            parse_mode="Markdown",
        )
        return REASON_COUNT

    count_val = int(match.group(0))
    if count_val <= 0:
        await update.message.reply_text(
            t("err_invalid_number", lang),
            parse_mode="Markdown",
        )
        return REASON_COUNT

    reasons_list = context.user_data.get("report", {}).get("reasons_list", [])
    reason_text = context.user_data.get("report", {}).get("current_reason_text", "Причина")
    reasons_list.append({"reason": reason_text, "count": count_val})
    context.user_data["report"].pop("current_reason_text", None)

    return await prompt_next_reason(update, context)

async def comment_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if input_text in CANCEL_TEXTS:
        return await cancel_report(update, context)

    if input_text in BACK_TEXTS:
        returned_str = context.user_data.get("report", {}).get("returned", "0")
        try:
            match_digits = re.search(r"\d+", returned_str)
            returned_total = int(match_digits.group(0)) if match_digits else int(returned_str)
        except (ValueError, AttributeError):
            returned_total = 0

        if returned_total <= 0:
            has_bike_types = context.user_data.get("report", {}).get("has_bike_types", 1)
            reply_keyboard = get_step_nav_buttons(lang)
            broken_prompt = t("step_broken_bikes_full", lang) if has_bike_types == 1 else t("step_broken_bikes", lang)
            await update.message.reply_text(
                broken_prompt,
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            )
            return BROKEN_BIKES
        else:
            return await prompt_next_reason(update, context)

    if input_text in SKIP_TEXTS:
        comment = "-"
    else:
        comment = input_text

    context.user_data["report"]["comment"] = comment

    return await show_summary(update, context)

def format_report_text(rep: dict) -> str:
    # Final published report template is ALWAYS formatted in Russian
    city = rep.get("city", "Ташкент")
    report_date = rep.get("report_date", "")
    issued = rep.get("issued", "0")
    returned = rep.get("returned", "0")
    total_in_trip = rep.get("total_in_trip", "0")
    new_bikes = rep.get("new_bikes", "-")
    old_bikes = rep.get("old_bikes", "-")
    broken_bikes = rep.get("broken_bikes", "0")
    comment = rep.get("comment", "-")
    reasons_list = rep.get("reasons_list", [])
    raw_reasons = rep.get("return_reasons", "-")

    city_info = get_city_by_name(city, db_path=DB_PATH)
    total_fleet = city_info.get("total_bikes", 50) if city_info else 50
    total_bikes_str = str(total_fleet)

    try:
        n_issued = int(re.search(r"\d+", str(issued)).group(0)) if re.search(r"\d+", str(issued)) else 0
        n_broken = int(re.search(r"\d+", str(broken_bikes)).group(0)) if re.search(r"\d+", str(broken_bikes)) else 0
        n_trip = int(re.search(r"\d+", str(total_in_trip)).group(0)) if re.search(r"\d+", str(total_in_trip)) else 0

        # User's formula: (на линии + сломанные) / всего_байков
        on_line = n_issued if n_issued > 0 else n_trip
        total_accounted = on_line + n_broken

        if total_fleet > 0:
            pct = round((total_accounted / total_fleet) * 100)
            share_str = f"{min(pct, 100)}%"
        else:
            share_str = "0%"
    except Exception:
        share_str = "0%"

    lang = rep.get("lang", "ru")
    if lang == "uz":
        if reasons_list:
            for item in reasons_list:
                item["reason"] = translate_uz_to_ru(item["reason"])
        elif raw_reasons != "-" and raw_reasons.strip():
            translated_items = [translate_uz_to_ru(r) for r in raw_reasons.split(", ")]
            raw_reasons = ", ".join(translated_items)

        if comment != "-":
            comment = translate_uz_to_ru(comment)

    lines = [
        f"📋 **Проверьте данные вашего отчёта:**",
        "",
        f"**Гибриды Rich {city}**",
        f"📍  {city}",
        "___________________",
        "",
        f"📅 Дата: {report_date}",
        "",
        "🛵 Отчет",
        "___________________",
        "",
        f"• Выдано: {issued}",
        f"• Вернули: {returned}",
        "• Причины возвратов:"
    ]
    if reasons_list:
        for item in reasons_list:
            lines.append(f"  • {item['reason']} — {item['count']}")
    elif raw_reasons != "-" and raw_reasons.strip():
        for r_item in raw_reasons.split(", "):
            lines.append(f"  • {r_item}")
    else:
        lines.append("  • -")

    lines.extend([
        "",
        f"🛵 В поездке: {total_in_trip}",
        f"🔧 Сломанные: {broken_bikes}",
        "",
        "💬 Комментарий:",
        f"_{comment}_" if comment != "-" else "-",
        "",
        f"🚲 Всего гибридов: {total_bikes_str}",
        f"📊 Доля на линии: {share_str}"
    ])

    return "\n".join(lines)

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rep = context.user_data.get("report", {})
    lang = rep.get("lang", "ru")

    report_content = format_report_text(rep)

    summary_msg = f"📋 **Проверьте данные вашего отчёта:**\n\n{report_content}\n\n"
    summary_msg += t("send_question", lang)

    confirm_lbl = t("confirm", lang)
    restart_lbl = t("restart", lang)
    cancel_lbl = t("cancel", lang)

    reply_keyboard = [
        [confirm_lbl],
        [restart_lbl, cancel_lbl]
    ]

    await update.message.reply_text(
        summary_msg,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
    )
    return CONFIRM

async def confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    lang = context.user_data.get("report", {}).get("lang", "ru")
    if is_cancel(text):
        return await cancel_report(update, context)

    if is_restart(text):
        return await start_report(update, context)

    if is_confirm(text):
        user = update.effective_user
        rep = context.user_data.get("report", {})
        rep["user_id"] = user.id if user else None
        rep["username"] = user.full_name or user.username or f"User_{user.id}" if user else "Partner"
        rep["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Save to SQLite database
        saved_report = add_bike_report(rep, db_path=DB_PATH)

        # 2. Sync to Google Sheets if available
        sheets_sync = context.bot_data.get("sheets_sync")
        if sheets_sync:
            try:
                sheets_sync.append_bike_report(saved_report)
            except Exception as e:
                logger.error(f"Failed to sync report to Google Sheets: {e}")

        final_report_view = format_report_text(rep)

        # 3. Post to Telegram Groups if configured
        target_groups = GROUP_CHAT_IDS or []
        for gid in target_groups:
            try:
                try:
                    await context.bot.send_message(
                        chat_id=gid,
                        text=f"{final_report_view}\n\n👤 **Отправил:** `{rep['username']}`",
                        parse_mode="Markdown"
                    )
                except Exception as md_err:
                    logger.warning(f"Markdown send_message failed for group {gid}: {md_err}, retrying plain text...")
                    clean_text = final_report_view.replace("**", "").replace("_", "").replace("`", "")
                    await context.bot.send_message(
                        chat_id=gid,
                        text=f"{clean_text}\n\n👤 Отправил: {rep['username']}"
                    )
                logger.info(f"Report #{saved_report.get('id')} posted to group {gid}")
            except Exception as e:
                logger.error(f"Failed to post report to group {gid}: {e}")

        main_keyboard = get_main_keyboard(user.id, user.username) if user else None
        success_title = f"🎉 **Отчёт «Байки» (ID #{saved_report.get('id')}) успешно отправлен!**\n\n" if lang == "ru" else f"🎉 **\"Bayklar\" hisoboti (ID #{saved_report.get('id')}) muvaffaqiyatli yuborildi!**\n\n"
        
        await update.message.reply_text(
            success_title + final_report_view,
            parse_mode="Markdown",
            reply_markup=main_keyboard,
        )
        context.user_data.pop("report", None)
        return ConversationHandler.END

    return CONFIRM

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = context.user_data.get("report", {}).get("lang", "ru")
    main_keyboard = get_main_keyboard(user.id, user.username) if user else None
    context.user_data.pop("report", None)
    await update.message.reply_text(
        t("cancel_msg", lang),
        reply_markup=main_keyboard,
    )
    return ConversationHandler.END

async def list_reports_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reports = get_bike_reports(limit=10, db_path=DB_PATH)
    if not reports:
        await update.message.reply_text("📭 В базе пока нет отправленных отчётов.")
        return

    await update.message.reply_text("📋 **Последние 10 отчётов «Байки»:**")
    for r in reports:
        formatted = format_report_text(r)
        await update.message.reply_text(f"🔹 **Отчёт #{r['id']}** (От: {r['username']})\n\n{formatted}", parse_mode="Markdown")

bike_report_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler(["report", "bikes"], start_report),
        MessageHandler(filters.Regex(r"^(📝 Заполнить отчёт.*|📝 Hisobot to'ldirish.*|/байки|/отчет|/отчёт|/report|Заполнить отчёт|Байки)$"), start_report),
    ],
    states={
        SELECT_LANG: [MessageHandler(filters.TEXT & (~filters.COMMAND), lang_step)],
        REPORT_DATE: [MessageHandler(filters.TEXT & (~filters.COMMAND), date_step)],
        SELECT_CITY: [MessageHandler(filters.TEXT & (~filters.COMMAND), city_step)],
        ISSUED: [MessageHandler(filters.TEXT & (~filters.COMMAND), issued_step)],
        RETURNED: [MessageHandler(filters.TEXT & (~filters.COMMAND), returned_step)],
        TOTAL_IN_TRIP: [MessageHandler(filters.TEXT & (~filters.COMMAND), total_in_trip_step)],
        NEW_BIKES: [MessageHandler(filters.TEXT & (~filters.COMMAND), new_bikes_step)],
        OLD_BIKES: [MessageHandler(filters.TEXT & (~filters.COMMAND), old_bikes_step)],
        BROKEN_BIKES: [MessageHandler(filters.TEXT & (~filters.COMMAND), broken_bikes_step)],
        REASONS: [MessageHandler(filters.TEXT & (~filters.COMMAND), reasons_step)],
        REASON_COUNT: [MessageHandler(filters.TEXT & (~filters.COMMAND), reason_count_step)],
        COMMENT: [MessageHandler(filters.TEXT & (~filters.COMMAND), comment_step)],
        CONFIRM: [MessageHandler(filters.TEXT & (~filters.COMMAND), confirm_step)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_report),
        MessageHandler(filters.Regex(r"^(❌ Отмена|❌ Bekor qilish|Отмена|Bekor qilish)$"), cancel_report),
    ],
    allow_reentry=True,
)
