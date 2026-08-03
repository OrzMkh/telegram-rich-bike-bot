import datetime

LANG_RU = "🇷🇺 Русский"
LANG_UZ = "🇺🇿 O'zbekcha"

MESSAGES = {
    "ru": {
        "select_lang": "🌐 **Выберите язык / Tilni tanlang:**",
        "access_denied": "⚠️ **Доступ ограничен!**\nУ вас нет прав для отправки отчётов. Обратитесь к администратору.",
        "step_date": "📝 **Заполнение отчёта «Байки»**\n\nШаг 1 из 10: **Выберите или введите дату отчёта** (выберите готовую дату ниже или введите вручную, например: `31.07.2026`):",
        "today": "Сегодня",
        "yesterday": "Вчера",
        "day_before": "Позавчера",
        "cancel": "❌ Отмена",
        "back": "◀️ Назад",
        "skip": "⏩ Пропустить",
        "confirm": "✅ Отправить",
        "restart": "✏️ Заполнить заново",
        "date_selected": "✅ Дата: **{date}**\n\nШаг 2 из 10: **Выберите город из списка**:",
        "city_selected": "✅ Город: **{city}**\n\nШаг 3: **Укажите количество выданных байков («Выдано»)**:",
        "step_returned": "Шаг 4: **Укажите количество вернувшихся байков («Вернули»)**:",
        "step_total_in_trip": "Шаг 5: **Укажите общее количество байков в поездке («Всего в поездке»)**:",
        "step_new_bikes": "Шаг 6: **Укажите количество новых байков на линии («Новые байки на линии»)**:",
        "step_old_bikes": "Шаг 7: **Укажите количество старых байков на линии («Старые байки на линии»)**:",
        "step_broken_bikes": "Шаг 6: **Укажите количество сломанных байков («Количество сломанных байков»)**:",
        "step_broken_bikes_full": "Шаг 8: **Укажите количество сломанных байков («Количество сломанных байков»)**:",
        "step_reasons": "Шаг 9: **Опишите причины возврата байков («Причины возврата байков»)**:",
        "reasons_intro": "📝 **Шаг 9: Причины возврата байков**\nВернули по отчёту: **{total} шт.**\nУказано по причинам: **{sum} шт.** из **{total} шт.**\n\nВведите причину №{num} (например: «Плановое ТО» или «Конец аренды»):",
        "reason_count_prompt": "Укажите количество байков по причине «**{reason}**» (например: 1, 5, 10, 50, 100):",
        "err_invalid_number": "⚠️ Пожалуйста, введите положительное число (например: 1, 5, 10, 50, 100).",
        "err_must_be_number": "⚠️ **Пожалуйста, введите только число (0 или больше)!**\nБуквы и текст не допускаются. Например: `0`, `1`, `5`, `12`, `100`.",
        "sum_warning": "⚠️ **Внимание:** Сумма по причинам (**{sum} шт.**) не совпадает с количеством вернувшихся байков (**{total} шт.**).",
        "proceed_anyway": "⏩ Всё равно продолжить",
        "add_more_reasons": "➕ Добавить причину",
        "finish_reasons": "✅ Завершить ввод причин",
        "step_comment": "Шаг 10: **Введите комментарий** (если есть необходимость) или нажмите «Пропустить»:",
        "summary_title": "📋 **Проверьте данные вашего отчёта «Байки»:**\n\n",
        "date_lbl": "📅 **Дата:** ",
        "city_lbl": "🏙 **Город:** ",
        "issued_lbl": "📤 **Выдано:** ",
        "returned_lbl": "📥 **Вернули:** ",
        "total_in_trip_lbl": "🚴 **Всего в поездке:** ",
        "new_bikes_lbl": "🆕 **Новые байки на линии:** ",
        "old_bikes_lbl": "🚴‍♂️ **Старые байки на линии:** ",
        "broken_bikes_lbl": "🛠 **Сломанных байков:** ",
        "reasons_lbl": "📝 **Причины возврата:** ",
        "comment_lbl": "💬 **Комментарий:** ",
        "send_question": "\n\nОтправить отчёт?",
        "success_msg": "🎉 **Отчёт «Байки» успешно отправлен!**\n\nID отчёта в базе: `#{id}`\nСпасибо за работу!",
        "cancel_msg": "❌ Заполнение отчёта отменено."
    },
    "uz": {
        "select_lang": "🌐 **Tilni tanlang / Выберите язык:**",
        "access_denied": "⚠️ **Ruxsat cheklangan!**\nSizda hisobot yuborish huquqi yo'q. Administratorga murojaat qiling.",
        "step_date": "📝 **\"Bayklar\" hisobotini to'ldirish**\n\n1-bosqich: **Hisobot sanasini tanlang yoki kiriting** (pastdagi tayyor sanani tanlang yoki qo'lda kiriting, masalan: `31.07.2026`):",
        "today": "Bugun",
        "yesterday": "Kecha",
        "day_before": "O'ldingi kun",
        "cancel": "❌ Bekor qilish",
        "back": "◀️ Orqaga",
        "skip": "⏩ O'tkazib yuborish",
        "confirm": "✅ Yuborish",
        "restart": "✏️ Qaytadan to'ldirish",
        "date_selected": "✅ Sana: **{date}**\n\n2-bosqich: **Ro'yxatdan shaharni tanlang**:",
        "city_selected": "✅ Shahar: **{city}**\n\n3-bosqich: **Berilgan bayklar sonini kiriting (\"Berildi\")**:",
        "step_returned": "4-bosqich: **Qaytarilgan bayklar sonini kiriting (\"Qaytarildi\")**:",
        "step_total_in_trip": "5-bosqich: **Safardagi jami bayklar sonini kiriting (\"Safarda\")**:",
        "step_new_bikes": "6-bosqich: **Liniyadagi yangi bayklar sonini kiriting (\"Yangi bayklar\")**:",
        "step_old_bikes": "7-bosqich: **Liniyadagi eski bayklar sonini kiriting (\"Eski bayklar\")**:",
        "step_broken_bikes": "6-bosqich: **Buzilgan bayklar sonini kiriting (\"Buzilgan bayklar\")**:",
        "step_broken_bikes_full": "8-bosqich: **Buzilgan bayklar sonini kiriting (\"Buzilgan bayklar\")**:",
        "step_reasons": "9-bosqich: **Bayklar qaytarilish sabablari**:",
        "reasons_intro": "📝 **9-bosqich: Bayklar qaytarilish sabablari**\nHisobot bo'yicha qaytarildi: **{total} ta**\nSabablar bo'yicha kiritildi: **{sum} ta** / **{total} ta**\n\n{num}-sababni kiriting (masalan: \"Texnik ko'rik\"):",
        "reason_count_prompt": "«**{reason}**» sababi bo'yicha bayklar sonini kiriting (masalan: 1, 5, 10, 50, 100):",
        "err_invalid_number": "⚠️ Iltimos, musbat son kiriting (masalan: 1, 5, 10, 50, 100).",
        "err_must_be_number": "⚠️ **Iltimos, faqat son kiriting (0 yoki undan katta)!**\nHarflar va matn kiritish mumkin emas. Masalan: `0`, `1`, `5`, `12`, `100`.",
        "sum_warning": "⚠️ **Diqqat:** Sabablar bo'yicha bayklar yig'indisi (**{sum} ta**) qaytarilgan bayklar soniga (**{total} ta**) teng emas.",
        "proceed_anyway": "⏩ Baribir davom etish",
        "add_more_reasons": "➕ Yana sabab qo'shish",
        "finish_reasons": "✅ Sabablarni kiritishni yakunlash",
        "step_comment": "10-bosqich: **Izoh kiriting** (zarur bo'lsa) yoki \"O'tkazib yuborish\" tugmasini bosing:",
        "summary_title": "📋 **\"Bayklar\" hisobotingiz ma'lumotlarini tekshiring:**\n\n",
        "date_lbl": "📅 **Sana:** ",
        "city_lbl": "🏙 **Shahar:** ",
        "issued_lbl": "📤 **Berildi:** ",
        "returned_lbl": "📥 **Qaytarildi:** ",
        "total_in_trip_lbl": "🚴 **Safarda:** ",
        "new_bikes_lbl": "🆕 **Yangi bayklar:** ",
        "old_bikes_lbl": "🚴‍♂️ **Eski bayklar:** ",
        "broken_bikes_lbl": "🛠 **Buzilgan bayklar:** ",
        "reasons_lbl": "📝 **Qaytarish sabablari:** ",
        "comment_lbl": "💬 **Izoh:** ",
        "send_question": "\n\nHisobotni yuborasizmi?",
        "success_msg": "🎉 **\"Bayklar\" hisoboti muvaffaqiyatli yuborildi!**\n\nBazasidagi hisobot ID: `#{id}`\nRahmat!",
        "cancel_msg": "❌ Hisobot to'ldirish bekor qilindi."
    }
}

def t(key: str, lang: str = "ru", **kwargs) -> str:
    lang_dict = MESSAGES.get(lang, MESSAGES["ru"])
    msg = lang_dict.get(key, MESSAGES["ru"].get(key, ""))
    if kwargs:
        return msg.format(**kwargs)
    return msg

def get_date_keyboard_buttons(lang: str = "ru") -> list:
    now = datetime.datetime.now()
    today_str = now.strftime("%d.%m.%Y")
    yesterday_str = (now - datetime.timedelta(days=1)).strftime("%d.%m.%Y")
    day_before_str = (now - datetime.timedelta(days=2)).strftime("%d.%m.%Y")
    day3_str = (now - datetime.timedelta(days=3)).strftime("%d.%m.%Y")
    day4_str = (now - datetime.timedelta(days=4)).strftime("%d.%m.%Y")

    today_lbl = t("today", lang)
    yesterday_lbl = t("yesterday", lang)
    day_before_lbl = t("day_before", lang)
    cancel_lbl = t("cancel", lang)

    return [
        [f"📅 {today_lbl} ({today_str})"],
        [f"📅 {yesterday_lbl} ({yesterday_str})", f"📅 {day_before_lbl} ({day_before_str})"],
        [f"📅 {day3_str}", f"📅 {day4_str}"],
        [cancel_lbl]
    ]

def get_step_nav_buttons(lang: str = "ru", include_skip: bool = False) -> list:
    back_lbl = t("back", lang)
    cancel_lbl = t("cancel", lang)
    skip_lbl = t("skip", lang)

    buttons = []
    if include_skip:
        buttons.append([skip_lbl])
    buttons.append([back_lbl, cancel_lbl])
    return buttons
