from typing import Dict

def describe_food_image(image_url: str, *_, **__) -> str:
    return "Looks like a plated meal."

def classify_food_image(image_url: str, *_, **__) -> Dict:
    return {"item_type": "plated", "dish_name": "Meal", "confidence": 90}

def analyze_packaged_food(image_url: str, *_, **__) -> Dict:
    return {"energy_kcal": 200, "protein_g": 10, "carbs_g": 25, "fat_g": 6}

def format_packaged_summary(data: Dict) -> str:
    return (
        f"Per serving — Calories: {data.get('energy_kcal', 0)}, "
        f"P: {data.get('protein_g', 0)}g, C: {data.get('carbs_g', 0)}g, F: {data.get('fat_g', 0)}g"
    )

def get_calorie_analysis(*_, **__) -> str:
    # Return a predictable line that the parser can handle
    return "Meal: Example — Calories 450, Protein 30g, Carbs 50g, Fats 15g"
