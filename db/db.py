import json
from options import CROPS_PATH, DB_PATH
import os

def add_crop(name, avg_price, min_value, min_mass, path=CROPS_PATH):
    # Проверяем, что файл есть, если нет — создаём пустой список
    if not os.path.exists(path):
        data = []
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    # Формируем новый фрукт
    new_fruit = {
        "name": name,
        "avg_price": avg_price,
        "min_value": min_value,
        "min_mass": min_mass
    }

    # Добавляем новый фрукт в список
    data.append(new_fruit)

    # Перезаписываем файл с обновленным списком
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Растение '{name}' добавлено в {path}")

def remove_crop(name):
    file_path = CROPS_PATH
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл {file_path} не найден")
    with open(file_path, "r", encoding="utf-8") as f:
        crops = json.load(f)

    # удаляем по имени (без учёта регистра, можно добавить)
    new_crops = [crop for crop in crops if crop['name'] != name]
    if len(new_crops) == len(crops):
        raise ValueError(f"Фрукт {name} не найден в базе")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(new_crops, f, ensure_ascii=False, indent=4)
    print(f"Удалён фрукт: {name}")

def database_view(filename):
    file_path = DB_PATH + filename
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл {file_path} не найден")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False, indent=2)