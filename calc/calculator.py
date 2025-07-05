import json
from calc.formulas import *
from options import PRICE_LIMIT

# import all mutations with multipliers from mutations.json
with open('db/mutations.json', 'r', encoding='utf-8') as f:
    mutation_bonuses = {m['name']: m.get('mult', 1) for m in json.load(f)}

# import all data from crops.json
with open('db/crops.json', 'r', encoding='utf-8') as f:
    crops = {c['name']: c for c in json.load(f)}

# returns a whole crop's structure (or None)
def _get_crop_by_name(name):
    return crops.get(name)

# e.g. calculate_mutations("Green Apple", ["Rainbow", "Wet", "Celestial"])
def calculate_mutations(name, mutations, mass = None, quantity = 1, debug=True):

    crop = _get_crop_by_name(name)
    if crop is None:
        if debug:
            print(f"Crop {name} was not found in database")
        return
    
    # if mass is null then take mass from database, if it was not found mass = 1.0
    if mass is None:
        mass = crop.get('min_mass', 1.0)

    # print(f"{name}'s info: avg_price={crop['avg_price']}, min_value={crop['min_value']}, min_mass={crop['min_mass']}")

    if validate_mutations(mutations, fruit_name=name):
        total_multiplier = calc_total_multiplier(mutations, mutation_bonuses)
        price = calc_price(
            fruit_constant=crop['avg_price'],
            min_mass=crop['min_mass'],
            min_value=crop['min_value'],
            mass=mass,
            mutations=mutations,
            mutation_bonuses=mutation_bonuses,
            fruit_name=name
        )

        total_value = int(price * quantity)
        total_str = f"{total_value:,}".replace(",", " ")
        if PRICE_LIMIT > 0 and total_value > PRICE_LIMIT:
            total_str = "9 999 999 999"
        if debug:
            print(f"Calculated {name} with {mutations} {mass}kg {quantity}x")
            print(f"Total multiplier: {total_multiplier}")
            print(f"Price: {total_str}")
        return total_str
    else:
        print(f"Error: wrong mutations combo: {mutations}")

def get_min_mass(name):
    crop = _get_crop_by_name(name)
    if crop is None:
        print(f"Crop {name} was not found in database")
        return
    mass = crop.get('min_mass', 1.0)
    crop.get('mass')
    return mass