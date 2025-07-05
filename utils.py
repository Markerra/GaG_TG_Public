import re
import json
from options import MUTATIONS_PATH
from rapidfuzz import process, fuzz
from calc.calculator import mutation_bonuses
from calc.calculator import get_min_mass

# e. g. parse_template("Tomato - Gold, Wwet, Celestial 2.3kg 3x")
def parse_template(text):
    # some AI stuff that idk
    pattern = r"^(.*?)\s*-\s*([\w\s,]+?)(?:\s*(\d+(?:[.,]\d+)?)(?:kg)?)?(?:\s*(\d+)x)?$"
    match = re.match(pattern, text.strip())
    print()
    if not match:
        return None
    plant = match.group(1).strip()
    mutations = [m.strip() for m in match.group(2).split(",")]
    kg = float(match.group(3).replace(',', '.')) if match.group(3) else get_min_mass(plant)
    # if text has not *x at the end then count = 1
    count = int(match.group(4)) if match.group(4) else 1
    
    with open(MUTATIONS_PATH, 'r', encoding='utf-8') as f:
        mutations_json = json.load(f)
    
    mutations = _match_mutations(mutations, [item["name"] for item in mutations_json])
    return {
        "plant": plant,
        "mutations": mutations,
        "kg": kg,
        "count": count
    }

def get_names(data):
    if isinstance(data, str):
        with open(data, 'r', encoding='utf-8') as f:
            items = json.load(f)
    else:
        items = data

    return [n['name'] for n in items]

def find_match_name(line, names_list, min_score=75):
    # create a dict where keys are names without spaces, values are original names
    names_search = {name.replace(" ", ""): name for name in names_list}
    # try to find the best match for the input line (without spaces) among names
    match, score, _ = process.extractOne(
        line.replace(" ", ""),
        names_search.keys(),
        scorer=fuzz.ratio
    )
    if score > min_score:
        return names_search[match]
    return None

def reset_temp_flags(context):
    for key in ['calc_state', 'calc_crop', 'calc_mutations', 'calc_mass', 'calc_count', 
                'waiting_crop_data', 'waiting_remove_crop_data', 'waiting_db_filename',
                'waiting_contact', 'contact_reply_id', 'waiting_for_mail', 'mail_text']:
        context.user_data[key] = None

def has_duplicates(lst):
    return len(lst) != len(set(lst))

def escape_markdown(text):
    return re.sub(r'([_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!])', r'\\\1', text)

def correct_mass(string):
    string = string.replace(',', '.')
    match = re.search(r"[-+]?\d*\.?\d+", string)
    if match:
        number = float(match.group())
        return number
    else:
        return string

# get best match for mutations
def _match_mutations(names, mutations, threshold = 80):
    result = []
    for name in names:
        match, score, _ = process.extractOne(name.replace(" ", ""), mutations, scorer=fuzz.ratio)
        if score > threshold:
            result.append(match)
        else:
            result.append('Default')
    return result