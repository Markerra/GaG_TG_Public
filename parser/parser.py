from calc.calculator import calculate_mutations, get_min_mass
from PIL import Image, ImageEnhance
from rapidfuzz import process, fuzz
import pytesseract
import json
import re

# import all mutations with multipliers from mutations.json
with open('db/mutations.json', 'r', encoding='utf-8') as f:
    mutation_names = {c['name']: c for c in json.load(f)}

# import all data from crops.json
with open('db/crops.json', 'r', encoding='utf-8') as f:
    crops_names = {c['name']: c for c in json.load(f)}

# get best match for crops
def find_match(line, crops):
    # create a dict where keys are crop names without spaces, values are original crop names
    crops_search = {k.replace(" ", ""): k for k in crops.keys()}
    # try to find the best match for the input line (without spaces) among crop names
    match, score, _ = process.extractOne(line.replace(" ", ""), crops_search.keys(), scorer=fuzz.ratio)
    if score > 70:
        orig_name = crops_search[match]
        return orig_name
    return None

def extract_info(image_path, mass = None, convert=True, contrast_val=4.1):
    # character whitelist
    img = Image.open(image_path)
    if convert:
        img = img.convert('L')
    img = img.resize((img.width * 2, img.height * 2))
    sharpness = ImageEnhance.Sharpness(img)
    contrast = ImageEnhance.Contrast(img)
    img = img.point(lambda x: 0 if x < 180 else 255).convert('1')
    img = contrast.enhance(contrast_val)
    # img = sharpness.enhance(1.2)
    config = '-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz¢+ '
    text = pytesseract.image_to_string(img, lang='eng', config=config)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    crop = None
    mutations_array = []
    price = None

    for i, line in enumerate(lines):
        best = find_match(line, crops_names)
        if best:
            crop = best
            # Попробуем взять следующие строки как мутации (если они есть)
            # Например, если строка после crop — это мутация
            for mut_line in lines[i+1:]:
                # Если строка похожа на мутацию (есть в mutation_names или fuzzy match)
                mut_best, score, _ = process.extractOne(mut_line, mutation_names.keys(), scorer=fuzz.ratio)
                if score > 70:
                    mutations_array.append(mut_best)
                else:
                    break  # если строка не похожа на мутацию — остановиться
            break

    print("RAW: ")
    print(lines)
    
    for line in lines:
        best = find_match(line, crops_names)
        if best:
            crop = best
            break

    img.save("parser/tmp/parsed.png")
    
    line_detected = False
    for line in lines:
        if not line_detected and '+' in line:
            # replace all spaces and +, filter, etc.
            line_detected = True
            # print("RAW: " +line)
            cleaned = re.sub(r'\++', '+', line.replace(' ', '+'))
            mutations = [m for m in cleaned.split('+') if m]
            for mutation in mutations:
                if mutation in mutation_names:
                    mutations_array.append(mutation)

    for i, line in enumerate(lines):
        # crop name
        if crop is None and re.match(r'^[A-Za-z ]+$', line):
            crop = line
            continue
        # mutations
        if mutations_array is None and '+' in line:
            mutations_array = [m.strip() for m in line.split('+')]
            continue

        price_match = re.search(r'([\d,]+)¢', line)
        if price_match:
            #price = price_match.group(1).replace(',', '')
            print ("price was found: " + price)
        elif crop and mutations_array:
            price = calculate_mutations(crop, mutations_array, mass, quantity=1, debug=False)
    #print("CROP: " + crop)
    #print("MUTATIONS: " )
    #print(mutations_array)
    return {
        'crop': crop,
        'mass': get_min_mass(crop),
        'mutations': mutations_array,
        'price': price if price else None
    }
