import requests # type: ignore
import json
from utils import find_match_name, get_names
from datetime import datetime, timezone, timedelta
from options import SEEDS_PATH, GEAR_PATH, EGGS_PATH, ESHOPS_PATH, EVENTS_PATH

with open(SEEDS_PATH, 'r', encoding='utf-8') as f:
    seeds = json.load(f)

with open(GEAR_PATH, 'r', encoding='utf-8') as f:
    gears = json.load(f)

with open(EGGS_PATH, 'r', encoding='utf-8') as f:
    eggs = json.load(f)

with open(EVENTS_PATH, 'r', encoding='utf-8') as f:
    events = json.load(f)

with open(ESHOPS_PATH, 'r', encoding='utf-8') as f:
    eshops = json.load(f)

all_data = None
prev_data = None

rarities = {
    "Prismatic": 0,
    "Divine": 1,
    "Mythical": 2,
    "Legendary": 3,
    "Rare": 4,
    "Uncommon": 5,
    "Common": 6,
}

ip = "http://38.180.92.40:80"
ip2 = "https://api.joshlei.com/v2/growagarden"

def GetAllData():
    global all_data, prev_data

    changes = {}
    
    # get stock data
    stock_url = ip2 + '/stock'
    stock_response = requests.get(stock_url)

    if not stock_response.ok:
        print(f"There was an error trying to get stock data from api: {stock_response.status_code}")
        all_data = prev_data
        return {"status": stock_response.status_code, "changes": {}}

    stock_data = stock_response.json()

    prev_data = all_data
    all_data = {
        "seeds": stock_data.get("seed_stock", []),
        "gear": stock_data.get("gear_stock", []),
        "eggs": stock_data.get("egg_stock", {}),
        'eshop': stock_data.get('eventshop_stock'),
        'weather': FetchWeather()
    }

    if prev_data and all_data != prev_data:
        print("Data changed")
        changes["seeds_changed"] = all_data['seeds'] != prev_data['seeds']
        if changes["seeds_changed"]:
            print("Seeds changed")

        changes["gear_changed"] = all_data['gear'] != prev_data['gear']
        if changes["gear_changed"]:
            print("Gear changed")

        changes["eggs_changed"] = all_data['eggs'] != prev_data['eggs']
        if changes["eggs_changed"]:
            print("Eggs changed")

        changes["eshop_changed"] = all_data['eshop'] != prev_data['eshop']
        if changes["eshop_changed"]:
            print("Event shop changed")

        changes["weather_changed"] = all_data['weather'] != prev_data['weather']
        if changes["weather_changed"]:
            print("Weather changed")
    else:
        changes["seeds_changed"] = False
        changes["gear_changed"] = False
        changes["eggs_changed"] = False
        changes["event_changed"] = False
    
    return {"status": stock_response.status_code, "changes": changes}

def GetStock():
    data = all_data['seeds']
    lines = []
    
    for seed in data:
        name = seed["display_name"]
        count = seed["quantity"]
        lines.append(f" - *{name}* [[x{count}]] Стоимость: {_get_seed_price(name)}¢")

    return "\n".join(lines) # returns a strings

def FetchStock():
    seeds = all_data['seeds']
    data = []
    for seed in seeds:
        name = seed["display_name"]
        count = seed["quantity"]
        data.append({"quantity": count, "name": name})
    return data

def GetGear():
    data = all_data['gear']
    lines = []
    
    for seed in data:
        name = seed["display_name"]
        count = seed["quantity"]
        lines.append(f" - *{name}* [[x{count}]] Стоимость: {_get_seed_price(name)}¢")

    return "\n".join(lines) # returns a strings

def FetchGear():
    gear_list = all_data['gear']
    data = []
    for gear in gear_list:
        name = gear["display_name"]
        count = gear["quantity"]
        data.append({"quantity": count, "name": name})
    return data

def GetEggs():
    data = all_data['eggs']
    lines = []
    
    for seed in data:
        name = seed["display_name"]
        count = seed["quantity"]
        lines.append(f" - *{name}* [[x{count}]]")

    return "\n".join(lines) # returns a strings
    
def FetchEggs():
    eggs = all_data['eshop']
    data = []
    for egg in eggs:
        name = egg["display_name"]
        count = egg["quantity"]
        data.append({"quantity": count, "name": name})
    return data

def GetEventShop():
    data = all_data['event']
    lines = []
    
    for seed in data:
        name = seed["display_name"]
        count = seed["quantity"]
        lines.append(f" - *{name}* [[x{count}]]")

    return "\n".join(lines) # returns a strings

def FetchEventShop():
    eggs = all_data['eshop']
    data = []
    for egg in eggs:
        name = egg["display_name"]
        count = egg["quantity"]
        data.append({"quantity": count, "name": name})
    return data

def GetWeather():
    #url = ip + '/weather'  
    #response = requests.get(url)

    #response.raise_for_status()  # throws an exception

    data = all_data['weather']

    iso_time = data.get('lastUpdated') # last updated date from json
    if iso_time:
        # formatting
        dt_utc = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        # translating to MSK
        dt_msk = dt_utc.astimezone(timezone(timedelta(hours=3)))
        # formatting
        human_time = dt_msk.strftime('%H:%M:%S')
    else:
        human_time = 'Неизвестно'

    
    type = data.get('type', 'Неизвестно')
    active = data.get('active')
    effects = []
    if active:
        effects = ', '.join(data.get('effects', []))
        mutations = next((item.get('mutation') for item in events if item['name'] == 'Thunderstorm'), [])
        active = 'Да'
    else:
        active = 'Нет'
    mutations_str = ', '.join(mutations)
    info = {
        "type": type,
        "active": active,
        "effects": effects,
        "mutations": mutations
    }
    print(f"Тип погоды: {type}")
    print(f"Активно: {active}")
    if len(mutations) == 0:
        print(f"Мутация: {mutations_str}")
    elif len(mutations) > 0:
        print(f"Мутации: {mutations_str}")
    print(f"Обновлено: {human_time} (МСК)")

    return info

def FetchWeather():
    url = ip2 + '/weather'  
    response = requests.get(url)

    data = response.json()

    weather_list = data.get('weather', [])

    # find active weather (first that has active = True)
    active_weather = next((w for w in weather_list if w['active']), None)

    if active_weather:
        type = active_weather.get('weather_id', 'unknown')
        name = find_match_name(type, get_names(events), 55)
        active = True
        # get mutations by weather name from events.json
        mutations = next((item.get('mutation') for item in events if item['name'] == name), [])
        # lastUpdated тоже нет → можем сами сгенерить или оставить None
        last_updated = None
    else:
        type = 'normal'  # как в старом
        name = find_match_name(type, get_names(events), 55)
        active = False
        mutations = []
        last_updated = None

    mutations_str = ', '.join(mutations)

    info = {
        'name': name,
        'type': type,
        'active': active,
        'mutations': mutations,
        'last_updated': last_updated
    }
    return info

def _get_seed_price(seed_name):
    for seed in seeds:
        if seed['name'] == seed_name:
            return seed['price']
  
    return None

def Test():
    url = ip2 + "/stock"
    response = requests.get(url)

    data = response.json()

    print(data)