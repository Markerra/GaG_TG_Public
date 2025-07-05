import os
import sys
import json
import time
import math
import random
import threading
import subscriptions as subs

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot # type: ignore
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackQueryHandler, CallbackContext # type: ignore

from api import *
from utils import *
from db.db import *
from options import *
from calc.calculator import calculate_mutations, get_min_mass
from parser.parser import extract_info, crops_names, mutation_names

bot = Bot(token=TOKEN)

##############################################################################################################

os.system('clear')
print("Bot started (@grow_a_garden_tgbot)")

# Users

def load_users():
    try:
        with open(USERS_PATH, 'r') as f:
            data = json.load(f)
            # update old format
            if data and isinstance(data[0], int):
                data = [{"chat_id": chat_id, "username": None, "first_name": None} for chat_id in data]
                save_users(data)
            return data
    except FileNotFoundError:
        return []

def save_users(users):
    with open(USERS_PATH, 'w') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(chat_id, username=None, first_name=None):
    users = load_users()
    for user in users:
        if user['chat_id'] == chat_id:
            user['username'] = username
            user['first_name'] = first_name
            save_users(users)
            return
    print(f"New user in database: @{username} {first_name}")
    users.append({'chat_id': chat_id, 'username': username, 'first_name': first_name})
    save_users(users)

def remove_user(chat_id):
    users = load_users()
    users = [user for user in users if user['chat_id'] != chat_id]
    save_users(users)

def get_users():
    return load_users()

# Start

def start(update: Update, context: CallbackContext):
    context.user_data["calc_hint_template"] = None # reset hint status
    help(update, context)
    menu(update, context)

# Restart

def restart(update: Update, context):
    query = update.callback_query
    query.answer()
    if not update.effective_user.username in ADMINS:
        query.edit_message_text("У тебя нет прав на перезапуск бота")
        return
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Главное меню", callback_data='menu')]])
    query.edit_message_text(text="Бот перезапускается...", reply_markup=markup)

    # flush and process restart
    sys.stdout.flush()
    os.execv(sys.executable, ['python'] + sys.argv)

# Main Menu

def main_menu_text():
    return "🏠 *Главное меню*"

def main_menu_markup(update: Update):
    keyboard = [
        [InlineKeyboardButton("➕ Калькулятор", callback_data='calc')],
        [InlineKeyboardButton("🛒 Магазин", callback_data='shop')],
        [InlineKeyboardButton("🔔 Уведомления", callback_data='subscriptions_menu')],
    ]
    if update.effective_user.username in ADMINS:
        keyboard.append([InlineKeyboardButton("⚙️ Настройки", callback_data='options')])
    return InlineKeyboardMarkup(keyboard)

def menu(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    subs.add_subscription(user.id, AUTOSUBSCRIBE_SEED, "seed")
    markup = main_menu_markup(update)
    text = main_menu_text()
    update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')
    reset_temp_flags(context)

# Help

def help(update: Update, context: CallbackContext):
    text = "Возможности бота:" \
    "\n - *Калькулятор по фото* (просто оправь фотографию с растением и мутациями) (все еще разрабатывается)" \
    "\n - *Калькулятор* (удобное меню с выборами разных мутаций и растений, вместо этого можно использовать шаблон сообщения)" \
    "\n - *Уведомления (подписки)* (можно подписаться на любой предмет из списка, и при его появлении в стоке, тебе будет отправлено уведомление)" \
    "\n - *Магазин* (автоматическое обновление магазина каждые 5 минут в реальном времени)"
    update.message.reply_text(text, parse_mode='Markdown')# , reply_markup=markup')
    reset_temp_flags(context)

# Contact

def contact(update: Update, context: CallbackContext):
    reset_temp_flags(context)
    update.message.reply_text("Напиши любое сообщение / пожелание: ")
    context.user_data['waiting_contact'] = True

# Database menu

def database_menu(update, context):
    reset_temp_flags(context)
    query = update.callback_query
    query.answer()
    keyboard = [
        [InlineKeyboardButton("Просмотреть", callback_data="database_view")],
        [InlineKeyboardButton("Добавить растения", callback_data="add_crop")],
        [InlineKeyboardButton("Удалить растения", callback_data="remove_crop")],
        [InlineKeyboardButton("Пользователи", callback_data='users')],
        [InlineKeyboardButton("Назад", callback_data="options")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text("*База данных*", reply_markup=reply_markup, parse_mode="Markdown")

def ask_crop_add_data(update, context):
    query = update.callback_query
    query.answer()
    context.user_data["waiting_crop_data"] = True
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="database_menu")]])
    query.edit_message_text("*База данных*\nВведи данные:\n`name, avg_price, min_value, min_mass`", reply_markup=markup, parse_mode="Markdown")

def ask_crop_remove_data(update, context):
    query = update.callback_query
    query.answer()
    context.user_data["waiting_remove_crop_data"] = True
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="database_menu")]])
    query.edit_message_text("*База данных*\nВведи *название* растения", reply_markup=markup, parse_mode="Markdown")

def ask_db_filename(update, context):
    query = update.callback_query
    query.answer()
    context.user_data["waiting_db_filename"] = True
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="database_menu")]])
    query.edit_message_text("Введи *название* файла:", reply_markup=markup, parse_mode="Markdown")


# Monitoring

def _check_stock(changes):
    from datetime import datetime, timezone
    utcnow = datetime.now(tz=timezone.utc).strftime('%H:%M:%S')
    print(f"checking stock [{utcnow} UTC]")

    #print("cahnges:")
    #print(changes)

    try:
        fseeds = FetchStock()
        fgear = FetchGear()
        feggs = FetchEggs()
        feshop = FetchEventShop()

        current_stock = {}
        for item in fseeds + fgear + feggs + feshop:
            current_stock[item['name']] = item['quantity']

        user_notifications = {}

        for usr in get_users():
            chat_id = usr['chat_id']
            user_subs = subs.get_subscriptions(chat_id, "all")
            filtered_items = []

            for type_, items in user_subs.items():
                for item in items:
                    if item in current_stock:
                        qty = current_stock[item]
                        if (
                            (type_ == 'seed' and changes.get("seeds_changed")) or
                            (type_ == 'gear' and changes.get("gear_changed")) or
                            (type_ == 'egg' and changes.get("eggs_changed")) or
                            (type_ == 'eshop' and changes.get("eshop_changed"))
                        ):
                            filtered_items.append((item, qty))

            if filtered_items:
                user_notifications[chat_id] = filtered_items

        for chat_id, items in user_notifications.items():
            message = NewItemsMessage(items)
            try:
                print(f"sended {items} to #{chat_id}")
                bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            except Exception as e:
                print(f"There was an error while attempting to send a message to #{chat_id}: {e}")

    except Exception as e:
        print(f"There was an error while attempting to refresh the stock: {e}")


def _check_weather(changes):
    from datetime import datetime, timezone

    utcnow = datetime.now(tz=timezone.utc)
    print(f"checking weather [{utcnow.strftime('%H:%M:%S')} UTC]")

    try:

        fweather = FetchWeather()

        if not changes.get("weather_changed"):
            return
        
        if not fweather.get('active'):
            return

        weather_data = {
            'name': fweather.get('name'),
            'mutations': fweather.get('mutations', [])
        }

        user_notifications = {}

        for usr in get_users():
            chat_id = usr['chat_id']
            user_subs = subs.get_subscriptions(chat_id, "weather")
            if weather_data['name'] in user_subs:
                user_notifications[chat_id] = weather_data

        for chat_id, weather in user_notifications.items():
            message = NewWeatherMessage(weather)
            try:
                print(f"sended weather '{weather['name']}' to #{chat_id}")
                bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            except Exception as e:
                print(f"There was an error while attempting to send weather to #{chat_id}: {e}")

    except Exception as e:
        print(f"There was an error while attempting to refresh the weather: {e}")


def monitor():
    def monitor_sleep(start, interval=CHECK_INTERVAL):
        now = datetime.now(tz=timezone.utc)
        elapsed = (now - start).total_seconds()
        remainder = elapsed % interval
        sleep_time = interval - remainder
        time.sleep(sleep_time)

    while True:
        start = datetime(2025, 1, 1, 0, 0, 8, 0, tzinfo=timezone.utc)

        result = GetAllData()
        status = result["status"]
        changes = result["changes"]

        if status == 429:
            monitor_sleep(start, interval=CHECK_INTERVAL*2)
            continue

        _check_stock(changes)
        _check_weather(changes)

        monitor_sleep(start)


def NewItemsMessage(items):
    # items: list of tuples (name, quantity)
    seeds_list = []
    gear_list = []
    eggs_list = []

    seed_names = set(seed['name'] for seed in seeds)
    gear_names = set(gear['name'] for gear in gears)
    egg_names = set(egg['name'] for egg in eggs)

    # sorting
    for name, quantity in items:
        if name in seed_names:
            seeds_list.append(f"*{name}* [[x{quantity}]]")
        elif name in gear_names:
            gear_list.append(f"*{name}* [[x{quantity}]]")
        elif name in egg_names:
            eggs_list.append(f"*{name}* [[x{quantity}]]")
        else:
            #seeds_list.append(f"*{name}* [[x{quantity}]]")
            pass

    message = []
    if seeds_list:
        message.append("🌱 Новые семена:\n - " + "\n - ".join(seeds_list))
    if gear_list:
        message.append("🛠️ Новое снаряжение:\n - " + "\n - ".join(gear_list))
    if eggs_list:
        message.append("🥚 Новые яйца:\n - " + "\n - ".join(eggs_list))
    return "\n\n".join(message) if message else "🛒 В магазине появились новые товары"

def NewWeatherMessage(weather):
    # weather: dict {name, mutations}
    mutations_str = ', '.join(weather['mutations'])
    if len(weather['mutations']) == 0: # if only 1 mutation
        return f"⛅️ Текущая погода:\n - *{weather['name']}*, Мутация: {weather['mutations']}"
    elif len(weather['mutations']) > 0: # if more than 1
        return f"⛅️ Текущая погода:\n - *{weather['name']}*, Мутации: {mutations_str}"

# Calculator

def show_crops_menu(update: Update, context: CallbackContext, page=0, per_page=6):
    with open(CROPS_PATH, 'r', encoding='utf-8') as f:
        crops = [c['name'] for c in json.load(f)]
    
    total_pages = math.ceil(len(crops) / per_page)
    start = page * per_page
    end = start + per_page
    page_crops = crops[start:end]
    keyboard = [[InlineKeyboardButton(name, callback_data=f'calc_crop_{name}')] for name in page_crops]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'calc_crops_page_{page-1}'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'calc_crops_page_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton('❌ Отмена', callback_data='menu')])

    text = '➕ *Калькулятор*\nВыбери растение:'
    markup = InlineKeyboardMarkup(keyboard)

    old_message = update.callback_query.message
    old_text = old_message.text
    old_markup = old_message.reply_markup

    # sending a message (ensure that messages doesn't equals each other)
    if update.callback_query and (text != old_text and (old_markup is None or markup.to_dict() != old_markup.to_dict())):
        update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
    else:
        update.message.reply_text(text=text, reply_markup=markup, parse_mode='Markdown')
    
    # hint
    if not context.user_data.get("calc_hint_template"):
        hint = 'Подсказка: где угодно можно отправить сообщение типа \n`Растение - Мутация1, Мутация2.. 2.5kg 5x`\n(кг или кол-во можно *не* указывать)'
        hint_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Скрыть", callback_data="hide")]])
        bot.send_message(chat_id=update._effective_chat.id, text=hint, reply_markup=hint_markup, parse_mode='Markdown')
        context.user_data["calc_hint_template"] = True

def show_mutations_menu(update, context, page=0, per_page=8):
    if page is None:
        page = context.user_data.get('calc_mut_page', 0)
    with open(MUTATIONS_PATH, 'r', encoding='utf-8') as f:
        mutations = [m['name'] for m in json.load(f)]
    selected = context.user_data.get('calc_mutations', [])
    total_pages = math.ceil(len(mutations) / per_page)
    start = page * per_page
    end = start + per_page
    page_mut = mutations[start:end]
    keyboard = []
    for mut in page_mut:
        prefix = '✅' if mut in selected else '❎'
        keyboard.append([InlineKeyboardButton(f'{prefix} {mut}', callback_data=f'calc_mut_{mut}')])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'calc_mut_page_{page-1}'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'calc_mut_page_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton('✅ Готово', callback_data='calc_mut_done'),
        InlineKeyboardButton('❌ Отмена', callback_data='menu')
    ])
    text = '➕ *Калькулятор*\nВыбери мутации:'
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
    else:
        update.message.reply_text(text=text, reply_markup=markup, parse_mode='Markdown')

# Buttons

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)

    query.answer()
    data = query.data

    match data:
        case "hide":
            context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
            return
        
        case "menu":
            reset_temp_flags(context)
            text = main_menu_text()
            markup = main_menu_markup(update)

        case "shop":
            text = "🛒 *Магазин*\nВыбери категорию:"
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Семена", callback_data='seeds')],
                [InlineKeyboardButton("🛠️ Снаряжение", callback_data='gear')],
                [InlineKeyboardButton("🥚 Яйца", callback_data='eggs')],
                [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]
            ])

        case "seeds":
            text = "🌱 Текущие семена в стоке:\n" + GetStock()
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='shop')]])

        case "gear":
            text = "🛠️ Текущее снаряжение в стоке:\n" + GetGear()
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='shop')]])

        case "eggs":
            text = "🥚 Текущие яйца в стоке:\n" + GetEggs()
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='shop')]])

        case "options":
            if not user.username in ADMINS:
                return
            user = update.effective_user
            text = "⚙️ *Настройки*"
            markup = [ 
                [InlineKeyboardButton("Рассылка", callback_data='mail')],
                [InlineKeyboardButton("База данных", callback_data='database_menu')],
                [InlineKeyboardButton("Перезапуск бота", callback_data='restart')],
                [InlineKeyboardButton("Главное меню", callback_data='menu')],
            ]
            markup = InlineKeyboardMarkup(markup)

        case "restart":
            restart(update, context)
            return

        case "database_menu":
            database_menu(update, context)
            return
        
        case "add_crop":
            ask_crop_add_data(update, context)
            return

        case "remove_crop":
            ask_crop_remove_data(update, context)
            return

        case "database_view":
            ask_db_filename(update, context)
            return

        case "users":
            lines = []
            users_count = 0
            for user in get_users():
                users_count += 1
            #    uname = user.get('username') or user.get('first_name') or str(user['chat_id'])
            #    uid = str(user['chat_id'])
            #    escaped_uname = escape_markdown(uname)
            #    lines.append(f" - @{escaped_uname} [[{uid}]]")
            #text = "Список всех пользователей: \n"
            #text += "\n".join(lines)
            text = f"Количество пользователей: {users_count}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='database_menu')]])

        case "mail":
            context.user_data['waiting_for_mail'] = True
            text = "Введите сообщение: "
            query.edit_message_text(text=text, parse_mode='Markdown')
            return
        
        case "mail_confirm":
            users = get_users()
            text_to_send = context.user_data.get('mail_text', '')
            success_count = 0
            for user in users:
                try:
                    context.bot.send_message(chat_id=user['chat_id'], text=text_to_send, parse_mode='Markdown')
                    success_count += 1
                except Exception as e:
                    print(f"Не удалось отправить сообщение {user['chat_id']}: {e}")
            text = (f"✅ Рассылка отправлена {success_count} пользователям.")
            context.user_data['waiting_for_mail'] = False
            context.user_data['mail_text'] = None
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("Главное меню", callback_data='menu')]])

        case "subscriptions_menu":
            subs.subscriptions(update, context)
            return
        
        case "subscriptions_category":
            text = "🔔 *Уведомления*\nВыбери категорию:"
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌱 Семена", callback_data='subs_seeds')],
                [InlineKeyboardButton("🛠️ Снаряжение", callback_data='subs_gear')],
                [InlineKeyboardButton("🥚 Яйца", callback_data='subs_eggs')],
                [InlineKeyboardButton("🛍️ Магазин событий", callback_data='subs_eshop')],
                [InlineKeyboardButton("🌦️ Погода", callback_data='subs_events')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='subscriptions_menu')],
            ])
            query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
            return

        case 'unsubscribe_all':
            subs.remove_all_subscriptions(user_id, "all")
            query.answer("Вы отписались от всего ✅")
            subs.subscriptions(update, context)
            return

        case _:
            if data.startswith("reply_"):
                user_id = int(data.split("_")[1])

                context.user_data['contact_reply_id'] = user_id

                query.answer()
                query.message.reply_text("Напиши ответное сообщение:")
                return
            
            if data == "subs_seeds" or \
            data.startswith("seeds_subs_page_") or \
            data.startswith("seeds_subscribe_") or \
            data.startswith("seeds_unsubscribe_"):
                subs.handle_seeds_subscriptions(update, context)
                return

            if (
            data.startswith("eggs_subs_page_")
            or data.startswith("eggs_subscribe_")
            or data.startswith("eggs_unsubscribe_")
            or data == "subs_eggs"):
                subs.handle_eggs_subscriptions(update, context)
                return

            if (
            data.startswith("gear_subs_page_")
            or data.startswith("gear_subscribe_")
            or data.startswith("gear_unsubscribe_")
            or data == "subs_gear"):
                subs.handle_gear_subscriptions(update, context)
                return
            
            if (
            data.startswith("eshop_subs_page_")
            or data.startswith("eshop_subscribe_")
            or data.startswith("eshop_unsubscribe_")
            or data == "subs_eshop"):
                subs.handle_eshop_subscriptions(update, context)
                return
            
            if (
            data.startswith("events_subs_page_")
            or data.startswith("events_subscribe_")
            or data.startswith("events_unsubscribe_")
            or data == "subs_events"):
                subs.handle_events_subscriptions(update, context)
                return
            
            if data == 'calc':
                context.user_data['calc_state'] = 'choose_crop'
                context.user_data['calc_mutations'] = []
                show_crops_menu(update, context)
                return
            
            if data.startswith('calc_crops_page_'):
                page = int(data.split('_')[-1])
                show_crops_menu(update, context, page=page)
                return
            
            if data.startswith('calc_crop_'):
                crop = data[len('calc_crop_'):]
                context.user_data['calc_crop'] = crop
                context.user_data['calc_state'] = 'choose_mutations'
                context.user_data['calc_mutations'] = []
                show_mutations_menu(update, context)
                return
            
            if data.startswith('calc_mut_page_'):
                page = int(data.split('_')[-1])
                if context.user_data.get('calc_mut_page', 0) != page:
                    context.user_data['calc_mut_page'] = page
                    show_mutations_menu(update, context, page=page)
                else:
                    pass
                return
            
            if data == 'calc_mut_done':
                context.user_data['calc_mut_page'] = 0
                crop = context.user_data.get('calc_crop')
                mutations = context.user_data.get('calc_mutations', [])
                context.user_data['calc_state'] = 'waiting_for_mass'
                context.user_data['calc_mass'] = None
                context.user_data['calc_count'] = None
                # print(crop)
                text = f'Введите массу в кг (по умолчанию {get_min_mass(crop)}кг):'
                query.edit_message_text(text=text)
                # print("calc_state: " + context.user_data['calc_state'])
                return
            
            if data.startswith('calc_mut_'):
                mut = data[len('calc_mut_'):]
                selected = context.user_data.get('calc_mutations', [])
                if mut in selected:
                    selected.remove(mut)
                else:
                    selected.append(mut)
                context.user_data['calc_mutations'] = selected
                page = context.user_data.get('calc_mut_page', 0)
                show_mutations_menu(update, context, page=page)
                return
    
        #case _:
        #    text = "Неизвестная команда."
        #    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Главное меню", callback_data='menu')]])

    query.edit_message_text(text=text, parse_mode='Markdown', reply_markup=markup)

def handle_message(update: Update, context: CallbackContext):
    parsed = parse_template(update.message.text)
    if parsed:
        # reset all flags
        reset_temp_flags(context)

        crop = parsed['plant']
        mutations = parsed['mutations']
        mass = parsed['kg']
        count = parsed['count']
        if not mass or mass <= 0.00000001 or mass > KG_LIMIT:
            mass = get_min_mass(crop)
        if count <= 0 or count > QUANTITY_LIMIT:
            update.message.reply_text(f'Некорректное количество')
            return
        try:
            result = calculate_mutations(crop, mutations, mass, count)
            if result is not None:
                mutations_str = ", ".join(mutations)
                if len(mutations_str) <= 1:
                    mutations_str = "Default"
                update.message.reply_text(
                    f'*{crop}* {mass}кг ({mutations_str}) [[x{count}]]\nСтоимость: *{result}¢*',
                    parse_mode='Markdown'
                )
            else:
                update.message.reply_text('Произошла ошибка, попопробуй еще раз')
        except Exception as e:
            update.message.reply_text(f'Ошибка при расчёте: {e}')
        return 
    
    # handle contact command message
    if context.user_data.get('waiting_contact'):

        text = update.message.text
        from_user = update.message.from_user
        user_id = from_user.id
        username = f"@{from_user.username}" if from_user.username else from_user.first_name
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ответить", callback_data=f"reply_{user_id}")]
        ])
        
        context.user_data['contact_text'] = text
        context.user_data['waiting_contact'] = None

        # sending a message to my chat id
        context.bot.send_message(
            chat_id=DEV_CHAT_ID,
            text=f"Сообщение от {username}:\n`{text}`",
            reply_markup=markup,
            parse_mode='Markdown'
        )

        update.message.reply_text("Сообщение отправлено")

    # handle a contact reply message
    if context.user_data.get('contact_reply_id'):
        contact_reply_id = context.user_data.get('contact_reply_id')
        
        text = update.message.text
        from_user = update.message.from_user
        user_id = from_user.id
        username = f"@{from_user.username}" if from_user.username else from_user.first_name

        # get user's message from global dispatcher
        user_data = context.dispatcher.user_data[contact_reply_id] # get a user's *id from msg* data
        user_msg = user_data['contact_text'] if user_data['contact_text'] else "Сообщение не найдено :("

        # header text
        header = f"*📩 Вам пришел ответ от {username}*"

        context.bot.send_message(chat_id=contact_reply_id, parse_mode='Markdown',
        text=f"{header}\n\nВы: \n `{user_msg}`\nОтвет:\n `{text}`")

        update.message.reply_text("Ответ успешно был отправлен")
        context.user_data['contact_reply_id'] = None
    
    # get a crop name from message
    if context.user_data.get('calc_state') == 'choose_crop':
        crop_query = update.message.text.strip().lower()
        with open('db/crops.json', 'r', encoding='utf-8') as f:
            crops = [c['name'] for c in json.load(f)]
        matches = [c for c in crops if crop_query in c.lower()]

        print("calc crop query: " + crop_query)
        if crop_query in CROP_EXCEPTIONS:
            for c in crops:
                if c.lower() == crop_query:
                    context.user_data['calc_crop'] = c
                    context.user_data['calc_state'] = 'choose_mutations'
                    context.user_data['calc_mutations'] = []
                    show_mutations_menu(update, context)
                    return

        if len(matches) == 1:
            context.user_data['calc_crop'] = matches[0]
            context.user_data['calc_state'] = 'choose_mutations'
            context.user_data['calc_mutations'] = []
            show_mutations_menu(update, context)
            return

        elif len(matches) > 1:
            update.message.reply_text('Найдено несколько растений:\n' + '\n'.join(matches) + '\nПожалуйста, уточните название.')
            return

        else:
            update.message.reply_text('Растение не найдено. Попробуйте ещё раз или выберите из списка.')
            return
    
    # get a calc count
    if context.user_data.get('calc_state') == 'waiting_for_mass':
        mass_str = update.message.text.replace(',', '.').strip()
        try:
            mass = float(correct_mass(mass_str))
            if mass <= 0.00000001 or mass > KG_LIMIT:
                raise ValueError
        except Exception:
            mass = get_min_mass(context.user_data['calc_crop'])
        context.user_data['calc_mass'] = mass
        context.user_data['calc_state'] = 'waiting_for_count'
        update.message.reply_text(f'Введите количество (по умолчанию 1):')
        return

    # printing calc result (from menu)
    if context.user_data.get('calc_state') == 'waiting_for_count':
        count_str = update.message.text.strip()
        try:
            count = int(count_str)
            if count < 1 or count > QUANTITY_LIMIT:
                count = 1
        except Exception:
            count = 1
        context.user_data['calc_count'] = count
        crop = context.user_data.get('calc_crop')
        mutations = context.user_data.get('calc_mutations', [])
        mass = context.user_data.get('calc_mass')
        try:
            result = calculate_mutations(crop, mutations, mass, count)
            if result is not None:
                mutations_str = ", ".join(mutations)
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]
                ])
                update.message.reply_text(f'*{crop}* {mass}кг ({mutations_str}) [[x{count}]]\nСтоимость: *{result}¢*', reply_markup=markup, parse_mode='Markdown')
            else:
                update.message.reply_text('Произошла ошибка, попопробуй еще раз')
        except Exception as e:
            update.message.reply_text(f'Ошибка при расчёте: {e}')
        # reset status
        context.user_data['calc_state'] = None
        context.user_data['calc_crop'] = None
        context.user_data['calc_mutations'] = []
        context.user_data['calc_mass'] = None
        context.user_data['calc_count'] = None
        return
    
    if context.user_data.get("waiting_crop_data"):
        text = update.message.text
        try:
            name, avg_price, min_value, min_mass = [x.strip() for x in text.split(",")]
            add_crop(name, int(avg_price), int(min_value), float(min_mass))
            update.message.reply_text(f"Растение *{name}* успешно добавлено", parse_mode="Markdown")
        except Exception as e:
            update.message.reply_text(f"Ошибка при добавлении растения: {e}")
        return

    if context.user_data.get("waiting_remove_crop_data"):
        try:
            remove_crop(update.message.text.strip())
            update.message.reply_text(f"Растение *{text.strip()}* успешно удалено", parse_mode="Markdown")
        except Exception as e:
            update.message.reply_text(f"Ошибка: {e}")
        return

    if context.user_data.get("waiting_db_filename"):
        try:
            data = database_view(update.message.text.strip())
            context.user_data["waiting_db_filename"] = False
            update.message.reply_text(f"\n```json\n{data}\n```", parse_mode="Markdown")
        except Exception as e:
            update.message.reply_text(f"Ошибка: {e}")
        return

    if context.user_data.get('waiting_for_mail'):
        user_text = update.message.text
        print(f"mail text: {user_text}")
        context.user_data['mail_text'] = user_text

        text = "Вы уверены что хотите отправить сообщение этим пользователям: \n"
        lines = []

        for user in get_users():
            uname = user.get('username')
            uid = str(user['chat_id'])
            if uname:
                escaped_uname = escape_markdown(uname)
                lines.append(f" - @{escaped_uname} [[{uid}]]")

        text += "\n".join(lines)

        escaped_user_text = escape_markdown(user_text)
        text = f"{text}\n`{escaped_user_text}`"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Подвердить", callback_data='mail_confirm')],
            [InlineKeyboardButton("Отмена", callback_data='menu')],
        ])
        update.message.reply_text(text=text, parse_mode='Markdown', reply_markup=markup)

def image_handler(update, context):
    # 0. send a message (please wait..)
    #text = "Пожалуйста подождите.."
    text = "Эта функция все еще в разработке, (примерное время ожидания: 2-3 дня)"
    update.message.reply_text(text)
    return
    sent = bot.send_message(chat_id=update._effective_chat.id, text=text)
    wait_message_id = sent.message_id  # save msg id

    # 1. ensure that tmp directory exists
    tmp_dir = "parser/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    # 2. generate unique file name
    chat_id = update._effective_chat.id
    user_id = update.effective_user.id if update.effective_user else "anon"
    timestamp = int(time.time() * 1000)
    file_path = f"{tmp_dir}/photo_{user_id}_{timestamp}.jpg"


    # 3. saving photo
    print(f"image_handler for {user_id}: started..")
    photo = update.message.photo[-1]  # biggest image (by size)
    file_path = "parser/tmp_photo.jpg"
    photo.get_file().download(file_path)

    # 4. get a mass from message (if it has)
    mass = None
    if update.message.caption:
        try:
            if str.isnumeric(update.message.caption):
                mass = float(update.message.caption.replace(',', '.').strip())
        except Exception:
            pass

    # 5. parse an image
    print(f"image_handler for {user_id}: parsing an image..")
    if os.path.isfile(file_path):
        file_not_found = False
        att = 1
        max_attempts = random.randint(10, 15)
        contrast_mult = random.uniform(0.1, 0.3)
        sections =  4 # how many sections with different settings
        att_section = 6 # how many tries in every section (with)

        for section in range(sections):
            for attempt in range(1, att_section + 1):
                att = section * att_section + attempt  # общий номер попытки

                base_contrast = 3.5
                if section % 2 == 0:
                    contrast_val = base_contrast + attempt * contrast_mult
                else:
                    contrast_val = base_contrast - attempt * contrast_mult

                convert = section < (sections / 2)

                info = extract_info(file_path, mass, convert=convert, contrast_val=contrast_val)

                print(f"attempt #{att}, section {section + 1}, contrast {contrast_val}, convert {convert}")

                if info['crop'] in crops_names and any(mut in info['mutations'] for mut in mutation_names):
                    if not has_duplicates(info['mutations']):
                        print("Found valid data, breaking.")
                        break
            else:
                continue

            break

    else:
        file_not_found = True

    crop = info['crop']
    mutations = info['mutations']
    price = info['price']

    if mass is None:
        mass = info['mass']

    if file_not_found:
        print(f"image_handler for {user_id}: there was an error trying to get info from photo..")
        bot.edit_message_text(chat_id=chat_id, message_id=wait_message_id, text= 
        "Изображение не найдено")
        return

    if not crop or not mutations:
        print(f"image_handler for {user_id}: there was an error trying to get info from photo..")
        bot.edit_message_text(chat_id=chat_id, message_id=wait_message_id, text= 
        "Не удалось распознать растение или мутации на фото. Попробуй обрезать изображение, оставив только нужные данные, или попробуй отправить версию с более высоким качеством")
        os.remove(file_path)
        return
    
    # delete the "please wait" message
    try:
        bot.delete_message(chat_id=update._effective_chat.id, message_id=wait_message_id)
    except Exception:
        pass

    # send a message
    mutations_str = ", ".join(mutations)
    update.message.reply_text(
        f'*{crop}* {mass}кг ({mutations_str})\nСтоимость: *{price}¢*',
        parse_mode='Markdown'
    )

    # delete a temporary file
    #os.remove(file_path)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("menu", menu))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("contact", contact))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.photo, image_handler)) # calculator (parser.py)
    
    threading.Thread(target=monitor, daemon=True).start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()