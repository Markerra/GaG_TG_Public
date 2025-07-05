from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot # type: ignore
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackQueryHandler, CallbackContext # type: ignore
from api import seeds, eggs, gears, events, eshops, rarities
from options import SUBS_PATH
import json
import os

subscription_types = [
    "seed",
    "gear",
    "egg",
    "event",
    "weather"
]

def load_subscriptions():
    if not os.path.exists(SUBS_PATH):
        return {}
    with open(SUBS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_subscriptions(subscriptions):
    with open(SUBS_PATH, 'w', encoding='utf-8') as f:
        json.dump(subscriptions, f, ensure_ascii=False, indent=2)

def add_subscription(chat_id, item, type):
    subs = load_subscriptions()
    chat_id_str = str(chat_id)
    if chat_id_str not in subs or not isinstance(subs[chat_id_str], dict):
        subs[chat_id_str] = {}
    if type not in subs[chat_id_str]:
        subs[chat_id_str][type] = []
    if item not in subs[chat_id_str][type]:
        subs[chat_id_str][type].append(item)
    save_subscriptions(subs)

def remove_subscription(chat_id, item):
    subs = load_subscriptions()
    chat_id_str = str(chat_id)
    for type in subs[chat_id_str]:
        if chat_id_str in subs and item in subs[chat_id_str][type]:
            subs[chat_id_str][type].remove(item)
            if not subs[chat_id_str]:
                del subs[chat_id_str]
            save_subscriptions(subs)

def remove_all_subscriptions(chat_id, type):
    subs = load_subscriptions()
    chat_id_str = str(chat_id)
    if type == "all":
        if chat_id_str in subs:
            del subs[chat_id_str]
            save_subscriptions(subs)
    else:
        if chat_id_str in subs and type in subs[chat_id_str]:
            del subs[chat_id_str][type]
            save_subscriptions(subs)

def get_subscriptions(chat_id, type):
    subs = load_subscriptions()
    user_subs = subs.get(str(chat_id), {})
    if type == "all":
        return user_subs
    else:
        return user_subs.get(type, [])

# Subscriptions

def subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id

    text = "🔔 *Уведомления*\nТвои подписки:\n"
    user_subs = get_subscriptions(user_id, "all")
    if not user_subs:
        text += "Пока что подписок нет.."
    else:
        type_names = {
            "seed": "*Cемена*",
            "gear": "*Снаряжение*",
            "egg":  "*Яйца*",
            "weather": "*Погода*"
        }
        lines = []
        for type_key in ["seed", "egg", "gear", "weather"]:
            items = user_subs.get(type_key, [])
            if items:
                lines.append(f"{type_names.get(type_key, type_key)}:")
                for name in sorted(items):
                    lines.append(f" - {name}")
        text += "\n".join(lines)

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Настроить уведомления", callback_data='subscriptions_category')],
        [InlineKeyboardButton("🗑 Отписаться от всего", callback_data='unsubscribe_all')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='menu')],
    ])
    query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')

def handle_seeds_subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    # Получаем подписки пользователя
    user_subs = get_subscriptions(user_id, "seed")
    seeds_per_page = 6

    # Парсим текущую страницу из data (если есть)
    import re
    page_match = re.search(r"_page_(\d+)$", data)
    if page_match:
        page = int(page_match.group(1))
    elif data.startswith("seeds_subs_page_"):
        page = int(data.split("_")[-1])
    else:
        page = 0

    # Обработка подписки
    if data.startswith("seeds_subscribe_"):
        # Вырезаем имя семени (без _page_х)
        seed_name = re.sub(r"^seeds_subscribe_(.+?)_page_\d+$", r"\1", data)
        add_subscription(user_id, seed_name, "seed")
        query.answer(f"✅ Подписались на {seed_name}")
        user_subs = get_subscriptions(user_id, "seed")

    # Обработка отписки
    elif data.startswith("seeds_unsubscribe_"):
        seed_name = re.sub(r"^seeds_unsubscribe_(.+?)_page_\d+$", r"\1", data)
        remove_subscription(user_id, seed_name)
        query.answer(f"❎ Отписались от {seed_name}")
        user_subs = get_subscriptions(user_id, "seed")

    # Перерисовка меню подписок
    if data == "subs_seeds" or \
       data.startswith("seeds_subs_page_") or \
       data.startswith("seeds_subscribe_") or \
       data.startswith("seeds_unsubscribe_"):

        seeds_sorted = sorted(seeds, key=lambda s: rarities.get(s['rarity'], 100))
        total_pages = (len(seeds_sorted) + seeds_per_page - 1) // seeds_per_page
        start = page * seeds_per_page
        end = start + seeds_per_page
        page_seeds = seeds_sorted[start:end]

        keyboard = []
        for seed in page_seeds:
            name = seed['name']
            rarity = seed.get('rarity', '')
            subscribed = name in user_subs
            text_prefix = "✅" if subscribed else "❎"
            text = f"{text_prefix} {name} ({rarity})"
            # Добавляем текущую страницу в callback_data
            if subscribed:
                callback_data = f"seeds_unsubscribe_{name}_page_{page}"
            else:
                callback_data = f"seeds_subscribe_{name}_page_{page}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"seeds_subs_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"seeds_subs_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("Назад", callback_data='subscriptions_category')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Выберите семена для подписки/отписки (страница {page+1}/{total_pages}):",
            reply_markup=reply_markup
        )
    else:
        query.answer("Неизвестная команда")

def handle_eggs_subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    user_subs = get_subscriptions(user_id, "egg")
    eggs_per_page = 6

    if data.startswith("eggs_subs_page_"):
        page = int(data.split("_")[-1])
    elif "_page_" in data:
        # extract page from subscribe/unsubcribe
        page = int(data.split("_page_")[-1])
    else:
        page = 0

    if data.startswith("eggs_subscribe_"):
        egg_name = data[len("eggs_subscribe_"):].split("_page_")[0]
        add_subscription(user_id, egg_name, "egg")
        query.answer(f"✅ Подписались на {egg_name}")
        user_subs = get_subscriptions(user_id, "egg")

    elif data.startswith("eggs_unsubscribe_"):
        egg_name = data[len("eggs_unsubscribe_"):].split("_page_")[0]
        remove_subscription(user_id, egg_name)
        query.answer(f"❎ Отписались от {egg_name}")
        user_subs = get_subscriptions(user_id, "egg")

    if data == "subs_eggs" or \
       data.startswith("eggs_subs_page_") or \
       data.startswith("eggs_subscribe_") or \
       data.startswith("eggs_unsubscribe_"):

        eggs_sorted = sorted(eggs, key=lambda e: rarities.get(e['rarity'], 100))
        total_pages = (len(eggs_sorted) + eggs_per_page - 1) // eggs_per_page
        start = page * eggs_per_page
        end = start + eggs_per_page
        page_eggs = eggs_sorted[start:end]

        keyboard = []
        for egg in page_eggs:
            name = egg['name']
            subscribed = name in user_subs
            text_prefix = "✅" if subscribed else "❎"
            text = f"{text_prefix} {name}"
            callback_data = f"eggs_unsubscribe_{name}_page_{page}" if subscribed else f"eggs_subscribe_{name}_page_{page}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"eggs_subs_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"eggs_subs_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("Назад", callback_data='subscriptions_category')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Выберите яйца для подписки/отписки (страница {page+1}/{total_pages}):",
            reply_markup=reply_markup
        )
    else:
        query.answer("Неизвестная команда")


def handle_gear_subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    user_subs = get_subscriptions(user_id, "gear")
    gear_per_page = 6

    if data.startswith("gear_subs_page_"):
        page = int(data.split("_")[-1])
    elif "_page_" in data:
        page = int(data.split("_page_")[-1])
    else:
        page = 0

    if data.startswith("gear_subscribe_"):
        gear_name = data[len("gear_subscribe_"):].split("_page_")[0]
        add_subscription(user_id, gear_name, "gear")
        query.answer(f"✅ Подписались на {gear_name}")
        user_subs = get_subscriptions(user_id, "gear")

    elif data.startswith("gear_unsubscribe_"):
        gear_name = data[len("gear_unsubscribe_"):].split("_page_")[0]
        remove_subscription(user_id, gear_name)
        query.answer(f"❎ Отписались от {gear_name}")
        user_subs = get_subscriptions(user_id, "gear")

    if data == "subs_gear" or \
       data.startswith("gear_subs_page_") or \
       data.startswith("gear_subscribe_") or \
       data.startswith("gear_unsubscribe_"):

        gears_sorted = sorted(gears, key=lambda g: rarities.get(g['rarity'], 100))
        total_pages = (len(gears_sorted) + gear_per_page - 1) // gear_per_page
        start = page * gear_per_page
        end = start + gear_per_page
        page_gears = gears_sorted[start:end]

        keyboard = []
        for gear in page_gears:
            name = gear['name']
            rarity = gear.get('rarity', '')
            subscribed = name in user_subs
            text_prefix = "✅" if subscribed else "❎"
            text = f"{text_prefix} {name} ({rarity})"
            callback_data = f"gear_unsubscribe_{name}_page_{page}" if subscribed else f"gear_subscribe_{name}_page_{page}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"gear_subs_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"gear_subs_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("Назад", callback_data='subscriptions_category')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Выберите снаряжение для подписки/отписки (страница {page+1}/{total_pages}):",
            reply_markup=reply_markup
        )
    else:
        query.answer("Неизвестная команда")

def handle_eshop_subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    user_subs = get_subscriptions(user_id, "eshop")
    eshop_per_page = 6

    text = ""

    if eshops:
        text = f"Выберите снаряжение для подписки/отписки (страница {page+1}/{total_pages}):"
    else:  # if current event shop doesn't have items in it
        text = "В текущем магазине нет никаких товаров для подписки"

    if data.startswith("eshop_subs_page_"):
        page = int(data.split("_")[-1])
    elif "_page_" in data:
        page = int(data.split("_page_")[-1])
    else:
        page = 0

    if data.startswith("eshop_subscribe_"):
        eshop_name = data[len("gear_subscribe_"):].split("_page_")[0]
        add_subscription(user_id, eshop_name, "eshop")
        query.answer(f"✅ Подписались на {gear_name}")
        user_subs = get_subscriptions(user_id, "eshop")

    elif data.startswith("eshop_unsubscribe_"):
        gear_name = data[len("eshop_unsubscribe_"):].split("_page_")[0]
        remove_subscription(user_id, eshop_name)
        query.answer(f"❎ Отписались от {eshop_name}")
        user_subs = get_subscriptions(user_id, "eshop")

    if data == "subs_eshop" or \
       data.startswith("eshop_subs_page_") or \
       data.startswith("eshop_subscribe_") or \
       data.startswith("eshop_unsubscribe_"):

        eshops_sorted = sorted(eshops, key=lambda g: rarities.get(g['rarity'], 100))
        total_pages = (len(eshops_sorted) + eshop_per_page - 1) // eshop_per_page
        start = page * eshop_per_page
        end = start + eshop_per_page
        page_eshops = eshops_sorted[start:end]

        keyboard = []
        for eshop in page_eshops:
            name = eshop['name']
            rarity = eshop.get('rarity', '')
            subscribed = name in user_subs
            text_prefix = "✅" if subscribed else "❎"
            text = f"{text_prefix} {name} ({rarity})"
            callback_data = f"eshop_unsubscribe_{name}_page_{page}" if subscribed else f"eshop_subscribe_{name}_page_{page}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"eshop_subs_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"eshop_subs_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("Назад", callback_data='subscriptions_category')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=text,
            reply_markup=reply_markup
        )
    else:
        query.answer("Неизвестная команда")

def handle_events_subscriptions(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    user_subs = get_subscriptions(user_id, "weather")
    events_per_page = 7
    page = 0

    if data.startswith("events_subs_page_"):
        page = int(data.split("_")[-1])

    elif data.startswith("events_subscribe_") or data.startswith("events_unsubscribe_"):
        parts = data.split("_")
        page = int(parts[-1])
        event_name = "_".join(parts[2:-1])

        if parts[1] == "subscribe":
            add_subscription(user_id, event_name, "weather")
            query.answer(f"✅ Подписались на {event_name}")
        else:
            remove_subscription(user_id, event_name)
            query.answer(f"❎ Отписались от {event_name}")

        user_subs = get_subscriptions(user_id, "weather")

    if data == "subs_events" or \
       data.startswith("events_subs_page_") or \
       data.startswith("events_subscribe_") or \
       data.startswith("events_unsubscribe_"):

        total_pages = (len(events) + events_per_page - 1) // events_per_page
        start = page * events_per_page
        end = start + events_per_page
        page_events = events[start:end]

        keyboard = []
        for event in page_events:
            name = event['name']
            subscribed = name in user_subs
            text_prefix = "✅" if subscribed else "❎"
            if subscribed:
                callback_data = f"events_unsubscribe_{name}_{page}"
            else:
                callback_data = f"events_subscribe_{name}_{page}"
            text = f"{text_prefix} {name}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"events_subs_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"events_subs_page_{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([InlineKeyboardButton("Назад", callback_data='subscriptions_category')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text=f"Выберите погоду для подписки/отписки (страница {page+1}/{total_pages}):",
            reply_markup=reply_markup
        )
    else:
        query.answer("Неизвестная команда")