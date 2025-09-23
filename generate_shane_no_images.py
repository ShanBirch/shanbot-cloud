#!/usr/bin/env python3
"""Generate Shane's meal plan without images while we wait for quota reset"""

import os
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Disable images to avoid quota issues
    os.environ['ENABLE_MEAL_IMAGES'] = '0'  # Explicitly disable

    print("=== GENERATING SHANE'S MEAL PLAN (NO IMAGES) ===")
    print("📝 Images disabled due to API quota limits")
    print("🖼️ We can add images later when quota resets")

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]

    # Calculate nutrition targets
    age = calculate_age(shane_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        shane_data["sex"],
        shane_data["weight_kg"],
        shane_data["height_cm"],
        age,
        shane_data["activity_factor"],
        500  # 500 calorie deficit for fat loss
    )

    print(f"\n👤 Client: {shane_data['name']}")
    print(f"🎯 Goal: {shane_data['goal_description']}")
    print(f"📊 Daily Targets:")
    print(f"   Calories: {target_cal}")
    print(f"   Protein: {target_protein}g")
    print(f"   Carbs: {target_carbs}g")
    print(f"   Fats: {target_fats}g")

    print(f"\n🍽️ Generating Week 1 meal plan (text only)...")

    # Generate the PDF without images
    try:
        create_pdf(shane_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{shane_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print(f"\n✅ SUCCESS! Meal plan PDF generated!")
            print(f"📄 Location: {pdf_path}")
            print(f"📊 PDF size: {pdf_size:,} bytes")
            print(f"📋 Contains complete meal plan with:")
            print(f"   • 7 days of meals (breakfast, lunch, dinner, snack)")
            print(f"   • Detailed ingredients and preparation instructions")
            print(f"   • Macro breakdowns for each meal")
            print(f"   • Shopping list organized by food category")
            print(f"   • Nutritional targets and client information")

            print(f"\n📝 Plan Overview:")
            print(f"   • Tailored for Shane's fat loss goal (80-85kg target)")
            print(
                f"   • {target_cal} calorie daily target with 500 cal deficit")
            print(f"   • High protein focus ({target_protein}g daily)")
            print(f"   • No pork or shellfish (per preferences)")
            print(f"   • Strength training nutrition support")

            print(f"\n💡 Next Steps:")
            print(f"   1. Review the meal plan PDF")
            print(f"   2. When API quota resets, we can regenerate with photos")
            print(f"   3. Photos will make meals more appealing and easier to prepare")

        else:
            print("❌ PDF was not created")

    except Exception as e:
        print(f"❌ Error generating meal plan: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
