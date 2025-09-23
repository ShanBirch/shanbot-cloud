#!/usr/bin/env python3
"""Generate Shane's Week 1 meal plan PDF"""

from client_configs import ALL_CLIENT_DATA
from utils import calculate_targets_by_sex, calculate_age
from weekly_meal_plan_generator import create_pdf


def main():
    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]
    print("=== SHANE MINAHAN - NUTRITION TARGETS ===")
    print(f"Name: {shane_data['name']}")
    print(f"Age: {calculate_age(shane_data['dob'])} years old")
    print(f"Weight: {shane_data['weight_kg']} kg")
    print(f"Height: {shane_data['height_cm']} cm")
    print(f"Activity: {shane_data['activity_factor']} (Sedentary)")
    print(f"Goal: {shane_data['goal_description']}")
    print()

    # Calculate targets
    age = calculate_age(shane_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        shane_data["sex"],
        shane_data["weight_kg"],
        shane_data["height_cm"],
        age,
        shane_data["activity_factor"],
        500  # 500 cal deficit for fat loss
    )

    print(f"Daily Targets (500 cal deficit):")
    print(f"Calories: {target_cal}")
    print(f"Protein: {target_protein}g")
    print(f"Carbs: {target_carbs}g")
    print(f"Fats: {target_fats}g")
    print()

    # Generate Week 1 PDF
    print("Generating Week 1 meal plan PDF...")
    try:
        create_pdf(shane_data, week=1)
        print("✅ Successfully generated Shane Week 1 meal plan PDF!")
        print("📁 Check: meal plans/ directory")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
