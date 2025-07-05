import math
from options import MUT_FILTER

EXCLUSIVE_GROUPS = [
    ["Gold", "Rainbow"],
    ["Chilled", "Wet", "Frozen"]
]

def get_growth_multiplier(mutations):
    if "Rainbow" in mutations:
        return 50
    if "Gold" in mutations:
        return 20
    return 1

def filter_mutations(mutations, mutation_bonuses):
    if not MUT_FILTER:
        return mutations
    group = [m for m in ["Chilled", "Wet", "Choc", "Moonlit", "Frozen"] if m in mutations]
    if group:
        max_mut = max(group, key=lambda m: mutation_bonuses.get(m, 0))
        filtered = [m for m in mutations if m not in group or m == max_mut]
        return filtered
    return mutations

def sum_environmental_mutations(mutations, mutation_bonuses):
    growths = {"Gold", "Rainbow", "Ripe"}
    return sum(
        (mutation_bonuses.get(m, 1) - 1)
        for m in mutations if m in mutation_bonuses and m not in growths
    )

def calc_total_multiplier(mutations, mutation_bonuses):
    growth_mult = get_growth_multiplier(mutations)
    env_bonus = sum_environmental_mutations(mutations, mutation_bonuses)
    return growth_mult * (1 + env_bonus)

def calc_price(fruit_constant, min_mass, min_value, mass, mutations, mutation_bonuses, fruit_name=None):
    total_multiplier = calc_total_multiplier(mutations, mutation_bonuses)
    if mass <= min_mass:
        return min_value * total_multiplier
    else:
        return min_value * (mass ** 2) / (min_mass ** 2) * total_multiplier

def validate_mutations(mutations, fruit_name=None):
    if not MUT_FILTER:
        return True
    for group in EXCLUSIVE_GROUPS:
        count = sum(1 for m in group if m in mutations)
        if count > 1:
            return False
    if "Dawnbound" in mutations and fruit_name and fruit_name.lower() != "sunflower":
        return False
    return True