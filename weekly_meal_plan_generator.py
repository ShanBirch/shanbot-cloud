import os
from datetime import datetime, date
import argparse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import re as _re
from urllib.parse import quote as _urlquote
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption
import re

from client_configs import (
    ALL_CLIENT_DATA,
    ALL_CLIENT_MEAL_ROTATIONS
)
from utils import calculate_age, calculate_targets_by_sex, enrich_preparation_text, maybe_generate_meal_image

LOGO_PATH = r"C:\\Users\\Shannon\\OneDrive\\Documents\\cocos logo.png"
OUTPUT_DIR = "meal plans"


def calculate_meal_times():
    return {
        'breakfast': '7:30 AM',
        'lunch': '12:30 PM',
        'snack': '3:00 PM',
        'dinner': '7:00 PM',
    }


def get_meal_plan_text(client_data: dict, week: int = 1):
    name = client_data["name"]
    dob = client_data["dob"]
    sex = client_data["sex"]
    weight_kg = client_data["weight_kg"]
    height_cm = client_data["height_cm"]
    activity_factor = client_data["activity_factor"]
    goal_description = client_data["goal_description"]
    dietary_type = client_data["dietary_type"]

    target_calories = client_data.get("target_calories")
    target_protein_g = client_data.get("target_protein_g")

    age = calculate_age(dob)
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        sex, weight_kg, height_cm, age, activity_factor, 500, target_calories=target_calories, target_protein_g=target_protein_g)

    times = calculate_meal_times()

    wk = int(week)

    client_meal_rotations = ALL_CLIENT_MEAL_ROTATIONS.get(name)

    if not client_meal_rotations:
        print(f"Error: Meal rotations not defined for client '{name}'.")
        return ""

    # Dynamically get client-specific meal rotations
    lunches_mon_wed = client_meal_rotations.get("lunches_mon_wed", {})
    lunches_thu_sat = client_meal_rotations.get("lunches_thu_sat", {})
    dinners_rot = client_meal_rotations.get("dinners", {})
    breakfasts_rot = client_meal_rotations.get("breakfasts", {})
    snacks_rot = client_meal_rotations.get("snacks", {})

    # Use modulo for simpler rotation if few meals are provided for 6 weeks
    # Ensure num_... variables are not zero to avoid division errors
    num_lunches_mon_wed = len(lunches_mon_wed) if lunches_mon_wed else 1
    num_lunches_thu_sat = len(lunches_thu_sat) if lunches_thu_sat else 1
    num_dinners = len(dinners_rot) if dinners_rot else 1
    num_breakfasts = len(breakfasts_rot) if breakfasts_rot else 1
    num_snacks = len(snacks_rot) if snacks_rot else 1

    # Initialize meal details for all 7 days based on rotations
    day_meals_content = [{} for _ in range(7)]

    for day_idx in range(7):
        current_day_num = day_idx + 1  # Day 1 to Day 7

        # Breakfast: Rotate through available breakfasts with batch pattern (Mon-Wed / Thu-Sat)
        if current_day_num <= 3:  # Mon-Wed: Use breakfast 1
            breakfast = breakfasts_rot.get(
                1, ("Generic Breakfast", "", "", ""))
        elif current_day_num <= 6:  # Thu-Sat: Use breakfast 2
            breakfast = breakfasts_rot.get(2, breakfasts_rot.get(
                1, ("Generic Breakfast", "", "", "")))
        else:  # Sunday: No breakfast (special day)
            breakfast = ("—", "—", "Sunday reset – no breakfast today.", "—")

        # Lunch: Handle Linda's specific Mon-Wed/Thu-Sat lunch batches if applicable, otherwise general rotation
        if "lunches_mon_wed" in client_meal_rotations and "lunches_thu_sat" in client_meal_rotations:
            if current_day_num <= 3:  # Mon-Wed
                lunch = client_meal_rotations["lunches_mon_wed"].get(
                    (wk - 1) % num_lunches_mon_wed + 1,
                    client_meal_rotations["lunches_mon_wed"].get(
                        1, ("Generic Lunch (Mon-Wed)", "", "", ""))
                )
            else:  # Thu-Sat
                lunch = client_meal_rotations["lunches_thu_sat"].get(
                    (wk - 1) % num_lunches_thu_sat + 1,
                    client_meal_rotations["lunches_thu_sat"].get(
                        1, ("Generic Lunch (Thu-Sat)", "", "", ""))
                )
        elif "lunches" in client_meal_rotations:  # General lunch rotation for other clients
            lunches_general_rot = client_meal_rotations.get("lunches", {})
            num_lunches_general = len(
                lunches_general_rot) if lunches_general_rot else 1
            lunch = lunches_general_rot.get(
                (wk - 1) % num_lunches_general + 1,
                lunches_general_rot.get(1, ("Generic Lunch", "", "", ""))
            )
        else:  # Fallback if no specific lunch rotations are found
            lunch = ("Generic Lunch", "", "", "")

        # Dinner: For list-based week dinners, map Mon–Tue, Wed–Thu, Fri–Sat to 3 distinct dinners
        dinner_week_key = (wk - 1) % num_dinners + 1
        if isinstance(dinners_rot.get(dinner_week_key), list):
            dinner_options_for_week = dinners_rot.get(
                dinner_week_key, dinners_rot.get(1, []))
            # We want exactly three distinct dinners repeated for two nights each
            if dinner_options_for_week:
                if current_day_num in (1, 2):
                    pair_index = 0
                elif current_day_num in (3, 4):
                    pair_index = 1
                elif current_day_num in (5, 6):
                    pair_index = 2
                else:  # Sunday handled below as cheat; fallback to last option if needed
                    pair_index = 2
                dinner = dinner_options_for_week[pair_index % len(
                    dinner_options_for_week)]
            else:
                dinner = ("Generic Dinner", "", "", "")
        else:
            # Single meal per week entry
            dinner = dinners_rot.get(
                dinner_week_key,
                dinners_rot.get(1, ("Generic Dinner", "", "", ""))
            )

        # Snack: Rotate through available snacks
        snack = snacks_rot.get(
            (wk - 1) % num_snacks + 1,
            snacks_rot.get(1, ("Generic Snack", "", "", ""))
        )

        day_meals_content[day_idx] = {
            "breakfast": breakfast,
            "lunch": lunch,
            "snack": snack,
            "dinner": dinner,
        }

    # Build the full meal plan text
    full_plan_text = ""
    for i in range(7):
        current_day_num = i + 1
        day_label = f"DAY {current_day_num}"
        meals = day_meals_content[i]

        if current_day_num == 7:  # Sunday special case
            full_plan_text += f"WEEK {wk} - {day_label} MEAL PLAN\n\n"
            full_plan_text += f"Breakfast\nMeal: —\nIngredients: —\nPreparation: Sunday reset – no breakfast today.\nMacros: —\n\n"
            full_plan_text += f"Lunch (12:00 PM – early lunch)\nMeal: {meals['lunch'][0]}\nIngredients:\n{meals['lunch'][1]}\nPreparation: {meals['lunch'][2]}\n{meals['lunch'][3]}\n\n"
            full_plan_text += f"Dinner (Cheat Meal)\nMeal: Flexible Choice within Guidelines\nGuidelines:\n- Add a protein (tofu/tempeh/beans) and plenty of veg\n- Favour baked/grilled over deep-fried\n- Pause at comfortable fullness; hydrate well\n- Enjoy mindfully – back on plan tomorrow\nMacros: Flexible\n\n"
        else:
            full_plan_text += f"WEEK {wk} - {day_label} MEAL PLAN\n\n"
            b_ing = [line.strip('- ').strip()
                     for line in meals['breakfast'][1].split('\n') if line.strip()]
            l_ing = [line.strip('- ').strip()
                     for line in meals['lunch'][1].split('\n') if line.strip()]
            s_ing = [line.strip('- ').strip()
                     for line in meals['snack'][1].split('\n') if line.strip()]
            d_ing = [line.strip('- ').strip()
                     for line in meals['dinner'][1].split('\n') if line.strip()]

            b_ing_block = convert_ingredients_units_for_client(
                name, meals['breakfast'][1])
            l_ing_block = convert_ingredients_units_for_client(
                name, meals['lunch'][1])
            s_ing_block = convert_ingredients_units_for_client(
                name, meals['snack'][1])
            d_ing_block = convert_ingredients_units_for_client(
                name, meals['dinner'][1])

            full_plan_text += f"Breakfast ({times['breakfast']})\nMeal: {meals['breakfast'][0]}\nIngredients:\n{b_ing_block}\nPreparation: {enrich_preparation_text(meals['breakfast'][2], b_ing)}\n{meals['breakfast'][3]}\n\n"
            full_plan_text += f"Lunch ({times['lunch']})\nMeal: {meals['lunch'][0]}\nIngredients:\n{l_ing_block}\nPreparation: {enrich_preparation_text(meals['lunch'][2], l_ing)}\n{meals['lunch'][3]}\n\n"
            full_plan_text += f"Afternoon Snack ({times['snack']})\nMeal: {meals['snack'][0]}\nIngredients:\n{s_ing_block}\nPreparation: {enrich_preparation_text(meals['snack'][2], s_ing)}\n{meals['snack'][3]}\n\n"
            full_plan_text += f"Dinner ({times['dinner']})\nMeal: {meals['dinner'][0]}\nIngredients:\n{d_ing_block}\nPreparation: {enrich_preparation_text(meals['dinner'][2], d_ing)}\n{meals['dinner'][3]}\n\n"

        full_plan_text += f"Daily Totals (Day {current_day_num}):\nCalories: {target_cal}\nProtein: ~{target_protein}g\nCarbs: ~{target_carbs}g\nFats: ~{target_fats}g\n\n"

    # Shopping List - Clean, organized format for Vlad
    shopping_list_text = f"INGREDIENT SHOPPING LIST – WEEK {wk}\n\n"
    shopping_list_text += """Proteins & Alternatives:
• Firm Tofu 1kg
• Tempeh 300g
• High-Protein Soy Yogurt 4 x 160g
• Plant Protein Powder 500g
• Nutritional Yeast 125g (B12-fortified)
• Red Lentils 500g (dry)
• Green Lentils 500g (dry)
• Hummus (high-protein) 400g

Pantry & Grains:
• Unsweetened Soy Milk 3L (B12-fortified)
• Jasmine Rice 1kg
• Red Rice 500g
• Black Rice 500g
• Quinoa 1kg
• Basmati Rice 500g
• Rice Noodles 400g
• Vetta SMART Protein Pasta 500g
• Large Wholemeal Tortillas (pack)
• Wholemeal Pita Bread (pack)
• Thai Red Curry Paste 200g
• Red Curry Paste 200g
• Light Coconut Milk 400ml x 2
• Peanut Butter 375g
• Almond Butter 200g
• Mixed Nuts & Seeds 500g (almonds, cashews, walnuts, pumpkin seeds)
• Dark Chocolate (80-95% cocoa) 200g
• Olive Oil 250ml
• Sesame Oil 100ml
• Soy Sauce 250ml
• Apple Cider Vinegar 250ml
• Lime Juice 250ml
• Tomato Passata 700ml
• Crispy Fried Shallots 100g
• Dried Fruit (no added sugar) 200g

Legumes & Canned:
• Chickpeas (No Added Salt) 4 x 420g
• Black Beans 2 x 400g

Produce & Fresh/Frozen:
• Baby Spinach 500g
• Mixed Asian Greens (Bok Choy, Broccoli, Snow Peas) 1kg
• Mushrooms 500g
• Capsicum (mixed colors) 6
• Onions 1kg
• Tomatoes 1kg
• Mixed Roasted Vegetables 1kg (zucchini, capsicum, eggplant)
• Avocado 4
• Bananas 1kg
• Mixed Greens 300g
• Cucumber 2
• Fresh Coriander (bunch)
• Fresh Parsley (bunch)
• Fresh Mint (bunch)
• Fresh Basil (bunch)
• Fresh Ginger 100g
• Spring Onions (bunch)
• Edamame (shelled) 400g
• Roasted Corn & Capsicum Salsa 400g
• Spicy Salsa 400g
• Vegan Feta Cheese 200g
• Vegan Cheese (shredded) 200g
• Lemon/Lime 6

Supplements (optional):
• Algal Oil (DHA/EPA omega-3)
• B12 Supplement (methylcobalamin or cyanocobalamin)

"""
    full_plan_text += shopping_list_text

    # Nutrition Guide (same as before)
    nutrition_guide_text = """
PLANT-BASED NUTRITION GUIDE

Understanding Plant-Based Protein & Macro Balancing

Most plant proteins come bundled with either carbohydrates (legumes, grains) or fats (nuts, seeds). Hitting targets is 100% doable – it just needs smart choices:

Protein Sources

Focus on protein-dense options first: tofu, tempeh, seitan, TVP/soy mince, high-protein pasta, and fortified soy yogurt. Use a clean plant protein powder when convenient.

Macro Control

• Use protein isolates (powers) for grams without extra carbs/fats.<br/>• Choose high-protein product swaps (e.g., protein pasta vs standard).<br/>• Combine foods across the day to cover amino acids (grains + legumes).<br/>• Use a simple protein powder when convenient for grams without extra carbs/fats.<br/>

Iron (non-heme)

Prioritise chickpeas, lentils, beans, tofu/tempeh, spinach and pumpkin seeds. Add vitamin C at meals (capsicum, lemon, berries) to boost absorption. Avoid tea/coffee 60 minutes around iron-rich meals.<br/>

Vitamin B12

Use fortified foods (soy milk, nutritional yeast) and a reliable B12 supplement (weekly or daily) to maintain levels.<br/>

Omega-3 Strategy

Daily ALA from flax, chia and hemp. For direct DHA/EPA, add an algal oil supplement (vegan). This supports brain, mood and endurance.<br/>

Additional Notes for Vlad:

• Focus on spicy, varied plant-based meals with fermented foods.<br/>
• Prioritize high-protein options to support body recomposition goals.<br/>
• Hydration is key, especially with high activity levels.
"""
    full_plan_text += nutrition_guide_text

    return full_plan_text


def extract_day_meals(text: str, day_type: str) -> dict:
    meals = {}
    lines = text.split('\n')
    current_day = None
    current_meal = None
    current_content = []
    for raw in lines:
        l = raw.strip()
        if not l:
            continue
        # Generic week header matcher (works for WEEK 1..6)
        if l.startswith('WEEK ') and ' - DAY ' in l and day_type in l:
            current_day = day_type
            current_meal = None
            current_content = []
            continue
        if l.startswith('WEEK ') and ' - DAY ' in l and day_type not in l:
            if current_day == day_type and current_meal and current_content:
                meals[current_meal] = '\n'.join(current_content).strip()
            current_day = None
            current_meal = None
            current_content = []
            continue
        if current_day == day_type:
            if l.startswith('Breakfast') or l.startswith('Lunch') or l.startswith('Afternoon Snack') or l.startswith('Dinner'):
                if current_meal and current_content:
                    meals[current_meal] = '\n'.join(current_content).strip()
                current_meal = l.split('(')[0].strip()
                current_content = []
            elif l.startswith('INGREDIENT SHOPPING LIST') or l.startswith('NUTRITIONAL'):
                if current_meal and current_content:
                    meals[current_meal] = '\n'.join(current_content).strip()
                break
            elif current_meal:
                current_content.append(l)
    if current_day == day_type and current_meal and current_content:
        meals[current_meal] = '\n'.join(current_content).strip()
    return meals


def format_meal_content(content: str) -> str:
    if not content:
        return ""
    lines = content.split('\n')
    formatted = []
    for l in lines:
        l = l.strip()
        if l.startswith('Calculation:'):
            continue
        # Drop any embedded totals from the source text to avoid duplicates
        if l.startswith('Daily Totals') or l.startswith('Calories:') or l.startswith('Protein:') or l.startswith('Carbs:') or l.startswith('Fats:'):
            continue
        if l.startswith('Meal:') or l.startswith('Ingredients:') or l.startswith('Preparation:') or l.startswith('Macros:') or l.startswith('Guidelines:'):
            formatted.append(f"<b>{l}</b>")
        elif l.startswith('- '):
            formatted.append(f"  {l}")
        else:
            formatted.append(l)
    return '<br/>'.join(formatted)


def _normalize_item_for_search(raw: str) -> str:
    s = raw.strip()
    # Remove parenthetical notes
    s = _re.sub(r"\([^)]*\)", "", s)
    # Remove common quantity patterns (e.g., 150g, 1 kg, 250ml, 2 x, 1/2 cup)
    s = _re.sub(
        r"\b\d+[\d\/.]*\s*(g|kg|ml|l|tbsp|tsp|cup|cups|slice|slices|pack|packs|packet|packets|x)\b",
        "",
        s,
        flags=_re.I,
    )
    # Remove plain numeric counts (e.g., 2, 1/2)
    s = _re.sub(r"\b\d+(?:[\/.]\d+)?\b", "", s)
    # Remove xN patterns (x2, x 2)
    s = _re.sub(r"\bx\s*\d+\b", "", s, flags=_re.I)
    # Remove ranges like 1–2, 8–10
    s = _re.sub(r"\b\d+\s*[–-]\s*\d+\b", "", s)
    # Remove descriptors that shouldn't affect product search
    descriptors = [
        'fresh', 'baby', 'large', 'small', 'medium', 'ripe', 'mixed', 'diced',
        'cubed', 'cubes', 'chopped', 'minced', 'sliced', 'grated', 'shredded',
        'cooked', 'raw', 'drained', 'rinse', 'rinsed', 'no added salt', 'low sugar',
        'crumbled', 'shelled', 'baked', 'marinated', 'seasonal', 'whole', 'thin', 'thick',
        'pieces', 'piece', 'clove', 'cloves', 'bunch', 'bunches', 'jar', 'can', 'cans'
    ]
    for d in descriptors:
        s = _re.sub(rf"\b{_re.escape(d)}\b", "", s, flags=_re.I)
    # Clean extra punctuation and multiple spaces
    s = _re.sub(r"[,.;:]", " ", s)
    s = _re.sub(r"\s+", " ", s).strip()
    # Phrase adjustments / synonyms
    low = s.lower()
    # Map toast -> bread (e.g., "sourdough toast" => "sourdough bread")
    low = low.replace(" toast", " bread")
    s = low.strip()
    # Reduce to 2-4 most relevant tokens to avoid over-specific searches
    tokens = [t for t in s.split() if t.lower() not in {
        'of', 'and', 'with', 'in', 'the'}]
    if not tokens:
        tokens = s.split()
    base = " ".join(tokens[:4])
    return base.strip()


def link_for(item_name: str) -> str:
    product_links = {
        'Firm Tofu 1kg': 'https://www.woolworths.com.au/shop/search/products?searchTerm=soyco%20firm%20tofu',
        'Tempeh 300g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=tempeh',
        'TVP (Textured Vegetable Protein) 300g': 'https://www.woolworths.com.au/shop/productdetails/173289/macro-textured-vegetable-protein',
        'High-Protein Soy Yogurt 4 x 160g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=soy%20protein%20yogurt',
        'Plant Protein Powder 500g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=plant%20protein%20powder',
        'Nutritional Yeast 125g (B12-fortified)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=nutritional%20yeast',
        'Unsweetened Soy Milk 3L (B12-fortified)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=unsweetened%20soy%20milk',
        'Jasmine Rice 1kg': 'https://www.woolworths.com.au/shop/search/products?searchTerm=jasmine%20rice%201kg',
        'Red Rice 500g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=red%20rice',
        'Black Rice 500g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=black%20rice',
        'Quinoa 1kg (or Buckwheat 1kg)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=quinoa%201kg',
        'Vetta SMART Protein Pasta 500g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=vetta%20protein%20pasta',
        'Cauliflower Pizza Base x2': 'https://www.woolworths.com.au/shop/search/products?searchTerm=cauliflower%20pizza%20base',
        'Taco Shells (Hard) x1 pack': 'https://www.woolworths.com.au/shop/search/products?searchTerm=hard%20taco%20shells',
        'Passata 700ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=passata',
        'Korma Simmer Sauce 375g (low sugar)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=korma%20simmer%20sauce',
        'Light Coconut Milk 400ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=light%20coconut%20milk',
        'Tahini 385g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=mayver%27s%20tahini',
        'Peanut Butter 375g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=peanut%20butter',
        'Ground Flaxseed 300g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=ground%20linseed%20flaxseed',
        'Chia Seeds 300g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=chia%20seeds',
        'Hemp Seeds 200g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=hemp%20seeds',
        'Mixed Nuts 300g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=mixed%20nuts%20300g',
        'Olive Oil 250ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=olive%20oil',
        'Soy Sauce 250ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=soy%20sauce',
        'Sesame Oil 100ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=sesame%20oil',
        'Marinara Sauce 500ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=marinara%20sauce',
        'Thai Red Curry Paste 200g': 'https://www.woolworths.com.au/shop/search/products?searchTerm=thai%20red%20curry%20paste',
        'Vanilla Extract 50ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=vanilla%20extract',
        'Lime Juice 250ml': 'https://www.woolworths.com.au/shop/search/products?searchTerm=lime%20juice',

        # Vlad's specific ingredients
        'Mixed Capsicum & Onion (diced)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=mixed%20capsicum%20onion',
        'Salsa (no added sugar)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=salsa%20no%20sugar',
        'Cooked Brown Rice': 'https://www.woolworths.com.au/shop/search/products?searchTerm=cooked%20brown%20rice',
        'Black Beans (canned, drained)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=black%20beans%20canned',
        'Roasted Corn & Capsicum Salsa': 'https://www.woolworths.com.au/shop/search/products?searchTerm=corn%20capsicum%20salsa',
        'Mixed Asian Greens (Bok Choy, Broccoli)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=asian%20greens',
        'Mushrooms': 'https://www.woolworths.com.au/shop/search/products?searchTerm=mushrooms',
        'Basmati Rice': 'https://www.woolworths.com.au/shop/search/products?searchTerm=basmati%20rice',
        'Cucumber': 'https://www.woolworths.com.au/shop/search/products?searchTerm=cucumber',
        'Tomato': 'https://www.woolworths.com.au/shop/search/products?searchTerm=tomato',
        'Red Onion': 'https://www.woolworths.com.au/shop/search/products?searchTerm=red%20onion',
        'Olives (diced)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=diced%20olives',
        'Vegan Feta Cheese (crumbled)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=vegan%20feta',
        'Lemon Dressing': 'https://www.woolworths.com.au/shop/search/products?searchTerm=lemon%20dressing',
        'Fresh Parsley': 'https://www.woolworths.com.au/shop/search/products?searchTerm=fresh%20parsley',
        'Fresh Mint': 'https://www.woolworths.com.au/shop/search/products?searchTerm=fresh%20mint',
        'Cooked Red Lentils': 'https://www.woolworths.com.au/shop/search/products?searchTerm=cooked%20red%20lentils',
        'Spicy Salsa': 'https://www.woolworths.com.au/shop/search/products?searchTerm=spicy%20salsa',
        'Indian Inspired Chickpea & Spinach Curry with Brown Rice': 'https://www.woolworths.com.au/shop/search/products?searchTerm=indian%20chickpea%20spinach%20curry',
        'Kimchi (fermented cabbage)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=kimchi',
        'Tahini-Miso Dressing': 'https://www.woolworths.com.au/shop/search/products?searchTerm=tahini%20miso%20dressing',
        'Rice Noodles': 'https://www.woolworths.com.au/shop/search/products?searchTerm=rice%20noodles',
        'Shredded Cabbage': 'https://www.woolworths.com.au/shop/search/products?searchTerm=shredded%20cabbage',
        'Crushed Peanuts': 'https://www.woolworths.com.au/shop/search/products?searchTerm=crushed%20peanuts',
        'Green Lentils': 'https://www.woolworths.com.au/shop/search/products?searchTerm=green%20lentils',
        'Vegetable Broth': 'https://www.woolworths.com.au/shop/search/products?searchTerm=vegetable%20broth',
        'Wholemeal Sourdough Bread': 'https://www.woolworths.com.au/shop/search/products?searchTerm=wholemeal%20sourdough%20bread',
        'Small Wholemeal Tortillas': 'https://www.woolworths.com.au/shop/search/products?searchTerm=small%20wholemeal%20tortillas',
        'Crispy Fried Shallots': 'https://www.woolworths.com.au/shop/search/products?searchTerm=crispy%20fried%20shallots',
        'Fresh Ginger (grated)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=fresh%20ginger%20grated',
        'Spring Onion': 'https://www.woolworths.com.au/shop/search/products?searchTerm=spring%20onion',
        'Edamame beans (shelled)': 'https://www.woolworths.com.au/shop/search/products?searchTerm=edamame%20shelled',
        'Apple Cider Vinegar': 'https://www.woolworths.com.au/shop/search/products?searchTerm=apple%20cider%20vinegar',
    }
    if item_name in product_links:
        return product_links[item_name]
    # Fallback: build a clean search query without quantities/descriptors
    query = _normalize_item_for_search(item_name)
    if not query:
        query = item_name
    return f"https://www.woolworths.com.au/shop/search/products?searchTerm={_urlquote(query)}"


def parse_meal_macros(content: str):
    """Extract calories, protein, carbs, fats from a meal content block.
    Returns (calories, protein_g, carbs_g, fats_g). Zeros if not found.
    """
    if not content:
        return 0, 0, 0, 0
    target = None
    for ln in content.split('\n'):
        if ln.strip().lower().startswith('macros:'):
            target = ln.lower()
            break
    if target is None:
        target = content.lower()

    def find_num(pattern: str) -> int:
        m = re.search(pattern, target)
        return int(m.group(1)) if m else 0
    calories = find_num(r"(\d+)\s*calories")
    protein_g = find_num(r"(\d+)\s*g\s*protein")
    carbs_g = find_num(r"(\d+)\s*g\s*carbs")
    fats_g = find_num(r"(\d+)\s*g\s*fats")
    return calories, protein_g, carbs_g, fats_g


def parse_meal_fields(content: str) -> dict:
    """Extract title, ingredients (list), and preparation text from a meal block string."""
    title = ""
    ingredients = []
    preparation = ""
    mode = None
    for raw in content.split('\n'):
        l = raw.strip()
        if not l:
            continue
        if l.lower().startswith('meal:'):
            title = l.split(':', 1)[1].strip()
            mode = None
            continue
        if l.lower().startswith('ingredients:'):
            mode = 'ingredients'
            continue
        if l.lower().startswith('preparation:'):
            preparation = l.split(':', 1)[1].strip()
            mode = None
            continue
        if mode == 'ingredients' and l.startswith('-'):
            ingredients.append(l.lstrip('-').strip())
    return {"title": title, "ingredients": ingredients, "preparation": preparation}


def _round_cups_label(cups_value: float) -> str:
    """Return a human-friendly cup fraction label rounded to common kitchen fractions."""
    if cups_value <= 0:
        return "a pinch"
    integer_part = int(cups_value)
    remainder = cups_value - integer_part
    candidates = [
        (0.0, ""),
        (1/8, "1/8"),
        (1/6, "1/6"),
        (1/4, "1/4"),
        (1/3, "1/3"),
        (1/2, "1/2"),
        (2/3, "2/3"),
        (3/4, "3/4"),
    ]
    best = min(candidates, key=lambda c: abs(remainder - c[0]))
    frac_label = best[1]
    approx = integer_part + best[0]
    if abs(approx - 1.0) < 1e-6 and integer_part == 0:
        return "1 cup"
    if integer_part == 0:
        return f"{frac_label} cup" if frac_label else "< 1/8 cup"
    if frac_label:
        return f"{integer_part} {frac_label} cups"
    return f"{integer_part} cup" if integer_part == 1 else f"{integer_part} cups"


def _convert_ml_to_cups_label(ml_value: float) -> str:
    cups = ml_value / 250.0  # AU metric cup
    return _round_cups_label(cups)


def _convert_grams_to_cups_label(grams_value: float, item_lower: str) -> str:
    """Approximate grams→cups for common cooked foods; returns a cups label or empty if unknown."""
    refs = [
        ("cooked quinoa", 185),
        ("cooked red lentils", 198),
        ("cooked lentils", 198),
        ("chickpeas", 165),
        ("black beans", 170),
        ("brown rice (cooked)", 195),
        ("cooked brown rice", 195),
        ("cooked rice", 160),
        ("buckwheat soba (cooked)", 114),
        ("soba (cooked)", 114),
        ("spinach", 30),
        ("mixed veg", 100),
        ("roasted veg", 100),
        ("vegetables", 100),
        ("veg ", 100),
        ("yogurt", 245),
        ("soy yogurt", 245),
        ("tofu (crumbled)", 150),
        ("tofu", 150),
    ]
    for key, g_per_cup in refs:
        if key in item_lower:
            cups = grams_value / float(g_per_cup)
            return _round_cups_label(cups)
    return ""


def _convert_small_grams_to_spoons(grams_value: float) -> str:
    """Convert small gram amounts to tsp/tbsp approximations."""
    if grams_value <= 0:
        return ""
    if grams_value <= 3:
        return "1/2 tsp"
    if grams_value <= 7:
        return "1 tsp"
    if grams_value <= 12:
        return "2 tsp"
    if grams_value <= 18:
        return "1 tbsp"
    if grams_value <= 25:
        return "1 1/2 tbsp"
    if grams_value <= 35:
        return "2 tbsp"
    return ""


def convert_ingredients_units_for_client(client_name: str, ingredients_block: str) -> str:
    """For specific clients (e.g., Dana), convert g/ml to cups/tbsp/tsp in ingredient lines."""
    if not ingredients_block:
        return ingredients_block
    if client_name not in ("Dana Aflamina",):
        return ingredients_block

    out_lines = []
    for raw in ingredients_block.split('\n'):
        line = raw
        stripped = raw.strip()
        if not stripped.startswith('-'):
            out_lines.append(line)
            continue
        if '+' in stripped:
            out_lines.append(line)
            continue
        m_g = _re.match(r"^\s*-\s*(\d+)\s*g\s+(.*)$", stripped, flags=_re.I)
        m_ml = _re.match(r"^\s*-\s*(\d+)\s*ml\s+(.*)$", stripped, flags=_re.I)
        if m_ml:
            ml = float(m_ml.group(1))
            item = m_ml.group(2)
            cups_label = _convert_ml_to_cups_label(ml)
            new_line = f"- {cups_label} {item}"
            out_lines.append(new_line)
            continue
        if m_g:
            grams = float(m_g.group(1))
            item = m_g.group(2)
            item_low = item.lower()
            cups_label = _convert_grams_to_cups_label(grams, item_low)
            if cups_label:
                out_lines.append(f"- {cups_label} {item}")
                continue
            spoon_label = _convert_small_grams_to_spoons(grams)
            if spoon_label:
                out_lines.append(f"- {spoon_label} {item}")
                continue
            out_lines.append(line)
            continue
        out_lines.append(line)
    return '\n'.join(out_lines)


def create_pdf(client_data: dict, week: int = 1):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    current_date = datetime.now().strftime("%Y%m%d")

    # Standardize output to a single friendly filename without dates or _PRO
    display_name = client_data["name"]
    filename = os.path.join(
        OUTPUT_DIR, f"{display_name} - Week {week}.pdf")

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontSize=24, alignment=1, spaceAfter=30, textColor=colors.HexColor('#0B3D91'))
    day_title_style = ParagraphStyle(
        'DayTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0B3D91'), spaceAfter=14)
    meal_title_style = ParagraphStyle('MealTitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor(
        '#0B3D91'), spaceBefore=10, spaceAfter=12)
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontSize=11, leading=18)
    info_style = ParagraphStyle(
        'Info', parent=styles['Normal'], alignment=1, fontSize=12, spaceAfter=6)
    shopping_title_style = ParagraphStyle(
        'ShoppingTitle', parent=styles['Heading1'], fontSize=18, alignment=1, textColor=colors.HexColor('#0B3D91'), spaceAfter=12)
    shopping_category_style = ParagraphStyle(
        'ShoppingCategory', parent=styles['Heading2'], fontSize=14, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor('#0B3D91'))
    shopping_item_style = ParagraphStyle('ShoppingItem', parent=styles['Normal'], fontSize=11, leftIndent=20, leading=14, textColor=colors.HexColor(
        '#0066CC'), underline=True, spaceBefore=3, spaceAfter=3)
    note_style = ParagraphStyle('Note', parent=body_style, fontSize=10,
                                alignment=1, textColor=colors.HexColor('#666666'), spaceAfter=15)

    # Roomier styles for the Theme Journey page
    journey_intro_style = ParagraphStyle(
        'JourneyIntro', parent=styles['Normal'], fontSize=12, leading=18, alignment=1, spaceAfter=12)
    journey_list_style = ParagraphStyle(
        'JourneyList', parent=styles['Normal'], fontSize=12, leading=18, alignment=0, spaceAfter=12)
    journey_features_style = ParagraphStyle(
        'JourneyFeatures', parent=styles['Normal'], fontSize=12, leading=18, alignment=0, spaceAfter=12)
    # Style for image placement, to ensure centering
    image_paragraph_style = ParagraphStyle(
        'ImageParagraph', parent=styles['Normal'], alignment=1, spaceAfter=0)

    story = []

    # Cover
    if os.path.exists(LOGO_PATH):
        story.append(Image(LOGO_PATH, width=2*inch, height=2*inch))
    story.append(Spacer(1, 30))
    story.append(Paragraph("MEAL PLAN", title_style))

    # Add theme info if available (for Sabrina's themed weeks)
    theme_info = ""
    if "weekly_theme" in client_data:
        theme_info = f"<b>Theme:</b> {client_data['weekly_theme']}<br/>"

    client_info = f"""
    <para alignment="center">
    <b>Client:</b> {client_data["name"]}<br/>
    <b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}<br/>
    <b>Week:</b> {week}<br/>
    {theme_info}<b>Goal:</b> {client_data["goal_description"]}
    </para>
    """
    story.append(Paragraph(client_info, info_style))

    # Targets
    age = calculate_age(client_data["dob"])
    cal, p, c, f = calculate_targets_by_sex(
        client_data["sex"], client_data["weight_kg"], client_data["height_cm"], age, client_data["activity_factor"], 500, client_data.get("target_calories"), client_data.get("target_protein_g"))

    targets = f"""
    <para alignment="center" bgcolor="#F5F5F5">
    <b>Daily Targets</b><br/>
    Calories: {cal}<br/>
    Protein: ~{p}g<br/>
    Carbs: ~{c}g<br/>
    Fats: ~{f}g
    </para>
    """
    story.append(Paragraph(targets, info_style))

    # 12-WEEK THEME JOURNEY - Dedicated Page (for Sabrina)
    if "theme_itinerary" in client_data:
        story.append(PageBreak())
        story.append(
            Paragraph("YOUR 12-WEEK THEME JOURNEY", shopping_title_style))

        itinerary = client_data["theme_itinerary"]
        journey_text = """
<para alignment="center">
<b>Welcome to your personalized 12-week culinary adventure!</b><br/>
Each week features a unique theme designed around your preferences.<br/>
No boring repetition - just exciting variety that keeps you motivated!<br/>
</para>
"""

        # Add this separately to avoid nested para tags
        story.append(Paragraph(journey_text, journey_intro_style))

        # Now add the week list
        weeks_text = "<b>YOUR THEMED WEEKS:</b><br/>"

        for week_num, theme in itinerary.items():
            if week_num == week:
                # Current week - make it stand out
                weeks_text += f"<b>• Week {week_num}: {theme} (YOU ARE HERE!)</b><br/>"
            elif week_num < week:
                # Completed weeks - muted
                weeks_text += f"• <font color='gray'>Week {week_num}: {theme} (completed)</font><br/>"
            else:
                # Future weeks - exciting preview
                weeks_text += f"• Week {week_num}: {theme}<br/>"

        story.append(Paragraph(weeks_text, journey_list_style))

        # Add special features section
        features_text = f"""
<b>What makes this special:</b><br/>
• <b>Built around your favorites:</b> Curries, rice bowls, noodles, pasta, creative salads<br/>
• <b>Stay satisfied at night:</b> Hearty, protein-forward meals to curb evening snacking<br/>
• <b>Batch-cooking friendly:</b> Same lunch Mon–Wed, new variety Thu–Sat<br/>
• <b>Clear weekly themes:</b> Structure and variety without decision fatigue<br/>
• <b>12 weeks of variety</b> – consistent progress without boredom<br/>
"""

        story.append(Paragraph(features_text, journey_features_style))

        # Add motivational closing
        closing_text = f"""
<para alignment="center">
<b>Ready to start your themed journey? Let's make Week {week} amazing!</b>
</para>
"""

        story.append(Paragraph(closing_text, info_style))

    # HOW TO USE YOUR MEAL PLAN - Explanation Page
    story.append(PageBreak())
    story.append(Paragraph("HOW TO USE YOUR MEAL PLAN", shopping_title_style))

    explanation_text = """
<b>MEAL ROTATION SYSTEM</b><br/>
Your lunch plan follows a smart batch-prep system:<br/>
• <b>Monday-Wednesday:</b> Same lunch for easy batch cooking<br/>
• <b>Thursday-Saturday:</b> New lunch variety (new batch)<br/>
• <b>Sunday:</b> Reset day with flexible options<br/>
<br/>
<b>Why this works:</b> Cook once, eat for 3 days! This saves time and reduces daily decision fatigue while ensuring you get variety throughout the week.<br/>
<br/>
<b>CALORIE TRACKING FOR FOOD FREEDOM</b><br/>
For maximum flexibility and food freedom, we recommend tracking your intake using:<br/>
• <b>Coco's Fitness app</b> (preferred) - excellent for plant-based foods<br/>
• <b>MyFitnessPal</b> - widely used alternative<br/>
<br/>
<b>Why track?</b> Learning portion sizes and macro values gives you the knowledge to make smart substitutions and enjoy more food freedom while staying on track with your goals.<br/>
<br/>
<b>SMART SUBSTITUTIONS</b><br/>
Feel free to make equivalent swaps:<br/>
• <b>Proteins:</b> Tofu ↔ Tempeh ↔ Beans ↔ Lentils (similar amounts)<br/>
• <b>Grains:</b> Jasmine Rice ↔ Basmati Rice ↔ Red Rice ↔ Black Rice ↔ Quinoa ↔ Pasta (similar portions)<br/>
• <b>Vegetables:</b> Any similar vegetables work great<br/>
• <b>Aim for similar calories</b> to maintain your targets<br/>
<br/>
<b>MEAL TIMING (APPROXIMATIONS)</b><br/>
The suggested meal times are <b>approximations</b> - adjust to fit your lifestyle:<br/>
• <b>Why timing helps:</b> Regular meal patterns support energy levels, hunger management, and metabolism<br/>
• <b>Not overly important:</b> Your total daily intake matters more than exact timing<br/>
• <b>Pre-workout:</b> Have your snack 30-60 mins before training for energy<br/>
• <b>Post-workout:</b> Include protein within 2 hours after training for recovery<br/>
• <b>Listen to your body:</b> Adjust timing based on your hunger, energy, and schedule<br/>
• <b>Sunday:</b> Flexible reset day - eat intuitively<br/>
<br/>
<b>SHOPPING & PREP TIPS</b><br/>
• Use the weekly shopping list provided<br/>
• <b>Batch prep:</b> Cook grains, chop vegetables, and prepare proteins ahead<br/>
• <b>Sunday prep:</b> 1-2 hours of prep sets you up for success<br/>
• <b>Storage:</b> Most meals keep 3-4 days in the fridge<br/>
<br/>
<b>SUCCESS TIPS</b><br/>
• <b>Be consistent</b> - aim for 80% adherence rather than 100% perfection<br/>
• <b>Plan ahead</b> - look at your week and prep accordingly<br/>
• <b>Listen to hunger</b> - adjust portions slightly based on your activity<br/>
• <b>Stay hydrated</b> - aim for 2-3L water daily<br/>
• <b>Ask questions</b> - your coach is here to support you!
"""

    story.append(Paragraph(explanation_text, body_style))

    # Content
    content = get_meal_plan_text(client_data=client_data, week=week)

    # Days 1–7
    for i in range(1, 8):
        day = f"DAY {i}"
        story.append(PageBreak())
        story.append(
            Paragraph(f"WEEK {week} - {day} MEAL PLAN", day_title_style))
        meals = extract_day_meals(content, day)
        # Keep order
        day_cals = day_pro = day_carbs = day_fats = 0
        for label in ("Breakfast", "Lunch", "Afternoon Snack", "Dinner"):
            if label in meals:
                # accumulate macros
                cal, pro, carbs, fats = parse_meal_macros(meals[label])
                day_cals += cal
                day_pro += pro
                day_carbs += carbs
                day_fats += fats
                # Create a list of flowables for the current meal block
                meal_flowables = [
                    Paragraph(label, meal_title_style),
                    # More space after title for better separation
                    Spacer(1, 0.3 * inch)
                ]

                # Optional image generation
                try:
                    # Handle tuple format (title, ingredients, preparation, macros) directly
                    meal_data = meals[label]
                    if isinstance(meal_data, tuple) and len(meal_data) >= 3:
                        meal_name = meal_data[0]
                        ing_text = meal_data[1]
                        prep_text = meal_data[2]
                        macros_for_image = meal_data[3] if len(
                            meal_data) > 3 else ""
                    else:
                        # Fallback to old parsing method for string format
                        fields = parse_meal_fields(meals[label])
                        meal_name = fields.get('title', '')
                        ing_text = "\n".join(fields.get('ingredients', []))
                        prep_text = fields.get('preparation', '')
                        # Extract macros for image generation
                        cal, p, c, f = parse_meal_macros(meals[label])
                        macros_for_image = f"Calories: {cal}, Protein: {p}g, Carbs: {c}g, Fats: {f}g"

                    img_path = maybe_generate_meal_image(meal_name, ing_text, prep_text, out_dir=os.path.join(
                        OUTPUT_DIR, 'images'), macros_text=macros_for_image)
                    if img_path and os.path.exists(img_path):
                        try:
                            # Preserve aspect ratio with a capped max height to avoid overflow
                            max_width = 3.5 * inch
                            max_height = 4.5 * inch
                            try:
                                iw, ih = ImageReader(img_path).getSize()
                                aspect = ih / float(iw) if iw else 0.75
                                img_width = max_width
                                img_height = img_width * aspect
                                if img_height > max_height:
                                    scale = max_height / img_height
                                    img_width = img_width * scale
                                    img_height = max_height
                                image_flowable = Image(
                                    img_path, width=img_width, height=img_height, hAlign='CENTER')
                            except Exception:
                                # Fallback to a safe size
                                image_flowable = Image(
                                    img_path, width=max_width, height=max_width * 0.75, hAlign='CENTER')
                            meal_flowables.append(image_flowable)
                            # More space below image
                            meal_flowables.append(Spacer(1, 0.25 * inch))
                        except Exception as e:
                            # Suppress error logging for now
                            pass
                except Exception:
                    pass

                # Add the meal content paragraph
                meal_flowables.append(
                    Paragraph(format_meal_content(meals[label]), body_style))
                # Space after meal content
                meal_flowables.append(Spacer(1, 0.2 * inch))

                # Keep each meal block together now that images are capped
                story.append(KeepTogether(meal_flowables))
        # Show recalculated totals for the day
        story.append(Spacer(1, 6))
        totals_str = f"<b>Daily Totals:</b> Calories: {day_cals}  •  Protein: {day_pro}g  •  Carbs: {day_carbs}g  •  Fats: {day_fats}g"
        story.append(Paragraph(totals_str, body_style))

    # Shopping List
    story.append(PageBreak())
    story.append(Paragraph("INGREDIENT SHOPPING LIST", shopping_title_style))
    story.append(Paragraph(
        "💡 <b>Tip:</b> Items below are clickable to help you shop online.", note_style))

    # Extract all ingredients from the generated meal plan text
    lines = content.split('\n')
    shopping = []
    in_list = False
    for ln in lines:
        t = ln.strip()
        # Look for ingredients lines after any meal type
        if t.startswith('Ingredients:'):
            in_list = True
            continue
        if in_list:
            # Stop when a new section starts or it's not an ingredient
            if t.startswith('Preparation:') or t.startswith('Macros:') or not t.startswith('-'):
                in_list = False
                continue
            if t.startswith('-'):
                # Add ingredient without the '- '
                shopping.append(t[2:].strip())

    # Consolidate duplicate items and handle specific replacements
    final_shopping_list_items = set()
    for item in shopping:
        # Assuming individual nuts from somewhere
        if item in ('Walnuts 100g', 'Almonds 100g', 'Cashews 100g', 'Peanuts 100g'):
            final_shopping_list_items.add('Mixed Nuts 300g')
        elif item == 'Dark Chocolate 70% 100g':  # Example from Amy's original
            final_shopping_list_items.add(
                'VitaWerx High Protein Chocolate (2 x 35g bars)')
        else:
            final_shopping_list_items.add(item)

    # Categories for shopping list (can be made dynamic based on item properties if a more complex system is built)
    categorized_shopping_list = {
        "Proteins & Alternatives:": [],
        "Pantry & Grains:": [],
        "Legumes & Canned:": [],
        "Produce & Fresh/Frozen:": [],
        "Supplements (optional):": [],
    }

    # Simple categorization based on keywords - this is a simplification
    for item in sorted(list(final_shopping_list_items)):  # Sort for consistent output
        lower_item = item.lower()
        if any(keyword in lower_item for keyword in ['tofu', 'tempeh', 'tvp', 'yogurt', 'protein powder', 'nutritional yeast', 'chickpea', 'lentil', 'beans']):
            categorized_shopping_list["Proteins & Alternatives:"].append(item)
        elif any(keyword in lower_item for keyword in ['rice', 'quinoa', 'buckwheat', 'oats', 'pasta', 'flour', 'seeds', 'nuts', 'oil', 'sauce', 'paste', 'extract', 'juice', 'honey', 'granola', 'bread', 'pizza base', 'taco shells', 'passata', 'coconut milk', 'tahini', 'peanut butter', 'tortillas', 'shallots']):
            categorized_shopping_list["Pantry & Grains:"].append(item)
        elif any(keyword in lower_item for keyword in ['chickpeas', 'beans', 'lentils']):
            # These are already caught by proteins, but if specific 'legumes & canned' needed, refine
            categorized_shopping_list["Legumes & Canned:"].append(item)
        elif any(keyword in lower_item for keyword in ['berries', 'apple', 'spinach', 'mushroom', 'capsicum', 'onion', 'tomato', 'broccoli', 'carrot', 'lettuce', 'lemon', 'lime', 'sauerkraut', 'avocado', 'corn', 'coriander', 'mint', 'basil', 'ginger', 'spring onion', 'edamame', 'sweet potato', 'parsnip', 'eggplant', 'cucumber', 'olives']):
            categorized_shopping_list["Produce & Fresh/Frozen:"].append(item)
        elif any(keyword in lower_item for keyword in ['supplement', 'algal oil', 'b12', 'vitaqerx']):
            categorized_shopping_list["Supplements (optional):"].append(item)
        else:
            # Fallback for items not categorized
            if "chocolate" in lower_item:  # Specific handling for dark chocolate
                categorized_shopping_list["Pantry & Grains:"].append(item)
            else:
                categorized_shopping_list["Pantry & Grains:"].append(
                    item)  # Default to pantry

    # Dynamically generate a categorized shopping list with clickable links
    category_order = [
        "Proteins & Alternatives:",
        "Pantry & Grains:",
        "Legumes & Canned:",
        "Produce & Fresh/Frozen:",
        "Supplements (optional):",
    ]
    parts = []
    for cat in category_order:
        items = sorted(set(categorized_shopping_list.get(cat, [])))
        if not items:
            continue
        parts.append(f"<b>{cat}</b><br/>")
        for item in items:
            href = link_for(item)
            parts.append(f"• <link href=\"{href}\"><u>{item}</u></link><br/>")
        parts.append("<br/>")

    shopping_list_formatted_text = "".join(parts)
    story.append(Paragraph(shopping_list_formatted_text, body_style))

    # Nutrition Guide (expanded – matches PRO quality)
    story.append(PageBreak())
    story.append(
        Paragraph("PLANT-BASED NUTRITION GUIDE", shopping_title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Understanding Plant-Based Protein & Macro Balancing", meal_title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Most plant proteins come bundled with either carbohydrates (legumes, grains) or fats (nuts, seeds). Hitting targets is 100% doable – it just needs smart choices:", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Protein Sources", meal_title_style))
    story.append(Paragraph("Focus on protein-dense options first: tofu, tempeh, seitan, TVP/soy mince, high-protein pasta, and fortified soy yogurt. Use a clean plant protein powder when convenient.", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Macro Control", meal_title_style))
    story.append(Paragraph("• Use protein isolates (powers) for grams without extra carbs/fats.<br/>• Choose high-protein product swaps (e.g., protein pasta vs standard).<br/>• Combine foods across the day to cover amino acids (grains + legumes).", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Iron (non-heme)", meal_title_style))
    story.append(Paragraph("Prioritise chickpeas, lentils, beans, tofu/tempeh, spinach and pumpkin seeds. Add vitamin C at meals (capsicum, lemon, berries) to boost absorption. Avoid tea/coffee 60 minutes around iron-rich meals.", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Vitamin B12", meal_title_style))
    story.append(Paragraph(
        "Use fortified foods (soy milk, nutritional yeast) and a reliable B12 supplement (weekly or daily) to maintain levels.", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Omega-3 Strategy", meal_title_style))
    story.append(Paragraph(
        "Daily ALA from flax, chia and hemp. For direct DHA/EPA, add an algal oil supplement (vegan). This supports brain, mood and endurance.", body_style))

    doc.build(story)
    print(f"✅ {client_data['name']} Week {week} PDF created: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--client", type=str, default="Linda",
                        help="Client name to generate meal plan for")  # Add client argument for testing
    args = parser.parse_args()

    # Use the client data from ALL_CLIENT_DATA based on the argument
    client_to_test = ALL_CLIENT_DATA.get(args.client)
    if client_to_test:
        create_pdf(client_data=client_to_test, week=args.week)
    else:
        print(f"Client '{args.client}' not found in ALL_CLIENT_DATA.")
