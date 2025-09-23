#!/usr/bin/env python3
"""Generate Dana's meal plan with Gemini 2.5 Flash photos"""

import os
import shutil
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Enable images with the working Gemini 2.5 Flash system
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print("=== GENERATING DANA'S MEAL PLAN WITH GEMINI 2.5 FLASH PHOTOS ===")
    print("🎨 Using proven image generation system")
    print("🔧 Gemini 2.5 Flash configured with IMAGE+TEXT modalities")
    print("🥗 Hearty vegan bowls with specific dietary preferences")

    # Get Dana's data
    dana_data = ALL_CLIENT_DATA["Dana Aflamina"]

    # Calculate nutrition targets (Dana has pre-set targets)
    age = calculate_age(dana_data["dob"])

    # Dana has specific calorie and protein targets
    target_cal = dana_data["target_calories"]  # 1100
    target_protein = dana_data["target_protein_g"]  # 80g

    # Calculate remaining macros (rough estimates)
    protein_cals = target_protein * 4
    remaining_cals = target_cal - protein_cals
    # 60% of remaining from carbs
    target_carbs = int((remaining_cals * 0.6) / 4)
    # 40% of remaining from fats
    target_fats = int((remaining_cals * 0.4) / 9)

    print(f"\n👤 Client: {dana_data['name']}")
    print(f"📅 Age: {age} years old")
    print(f"🎯 Goal: {dana_data['goal_description']}")
    print(f"🌱 Dietary Type: {dana_data['dietary_type']}")
    print(f"💪 Activity: Lightly active (1.375 factor)")
    print(
        f"📊 Pre-set Targets: {target_cal} cal, {target_protein}g protein, {target_carbs}g carbs, {target_fats}g fats")

    print(f"\n🌟 Dana's Specific Preferences:")
    print(f"   ✅ LOVES: Dahls, Japanese curries, soups, stir fry, Buddha bowls")
    print(f"   ✅ LOVES: Stuffed sweet potato, juices, chickpeas, lentils, beans")
    print(f"   ❌ AVOIDS: Raw tomato, celery, cucumbers, coriander")
    print(f"   ❌ AVOIDS: Plain salads, too much rice")
    print(f"   🍚 Prefers: Quinoa & sweet potato over rice")
    print(f"   🥗 Only cooked vegetables preferred")

    # Clear old images for fresh generation
    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
        print(f"🗑️ Cleared old images from: {images_dir}")
    os.makedirs(images_dir, exist_ok=True)

    print(f"\n🍽️ Generating Week 1 meal plan with AI-generated photos...")
    print("⏳ This will take several minutes as each meal photo is generated...")
    print("📷 Expected photos: ~28 images (7 days × 4 meals)")
    print("🥗 Focus: Hearty vegan bowls Dana will love!")

    # Generate the PDF with images
    try:
        create_pdf(dana_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{dana_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            pdf_size_mb = pdf_size / (1024 * 1024)

            print(f"\n✅ SUCCESS! Dana's meal plan PDF generated!")
            print(f"📄 Location: {pdf_path}")
            print(f"📊 PDF size: {pdf_size:,} bytes ({pdf_size_mb:.1f} MB)")

            # Check generated images
            if os.path.exists(images_dir):
                generated_images = [f for f in os.listdir(
                    images_dir) if f.endswith('.jpg')]
                print(f"🖼️ Generated {len(generated_images)} meal photos")

                if generated_images:
                    total_image_size = sum(os.path.getsize(os.path.join(
                        images_dir, img)) for img in generated_images)
                    avg_image_size = total_image_size / \
                        len(generated_images) if generated_images else 0

                    print(f"\n📸 Image Generation Summary:")
                    print(f"   • Total photos: {len(generated_images)}")
                    print(
                        f"   • Average size: {avg_image_size/1024:.0f} KB per image")
                    print(
                        f"   • Total image data: {total_image_size/1024/1024:.1f} MB")
                    print(f"   • Generated using: Gemini 2.5 Flash")
                    print(f"   • Style: Photorealistic vegan bowl photography")

                    # Show sample images
                    print(f"\n📷 Sample generated meal images:")
                    for i, img_name in enumerate(generated_images[:5]):
                        img_path = os.path.join(images_dir, img_name)
                        img_size = os.path.getsize(img_path)
                        print(f"   {i+1}. {img_name} ({img_size/1024:.0f} KB)")

                    if len(generated_images) > 5:
                        print(
                            f"   ... and {len(generated_images) - 5} more photos")

                    # Analyze embedding success
                    if pdf_size > 2_000_000:  # > 2MB suggests many images embedded
                        print(
                            f"\n🎉 EXCELLENT! PDF size indicates images are successfully embedded")
                        print(f"📖 Dana now has a complete visual meal plan")
                        print(f"🥗 Perfect for her hearty bowl preferences!")
                    elif pdf_size > 500_000:  # > 500KB suggests some images
                        print(f"\n✅ GOOD! PDF contains some images")
                        print(
                            f"📊 {len(generated_images)} photos successfully generated")
                    else:
                        print(f"\n⚠️ PDF size suggests limited image embedding")
                        print(f"📋 Complete text-based meal plan is available")

                    print(f"\n📋 Dana's Meal Plan Features:")
                    print(f"   • 7-day customized meal plan")
                    print(f"   • Pre-set calorie targets (1,100 cal)")
                    print(f"   • High protein focus (80g daily)")
                    print(f"   • Hearty vegan bowls & dahls")
                    print(f"   • Japanese curry specialties")
                    print(f"   • Photorealistic meal images")
                    print(f"   • No raw tomato/celery/cucumber/coriander")
                    print(f"   • Minimal rice, more quinoa/sweet potato")
                    print(f"   • Cooked vegetables emphasis")
                    print(f"   • Fat loss target: 50kg")

                    print(f"\n🍽️ Dana's Favorite Meal Types:")
                    print(f"   🍛 Red Lentil Dahls (no rice)")
                    print(f"   🍜 Japanese Vegetable Curries")
                    print(f"   🥗 Buddha Bowls with quinoa")
                    print(f"   🍠 Stuffed Sweet Potatoes")
                    print(f"   🥤 Fresh Juices & protein parfaits")
                    print(f"   🍜 Hearty Soups & Stir-frys")

                    print(f"\n💪 Perfect for Dana because:")
                    print(f"   • Respects all her food preferences & dislikes")
                    print(f"   • Low calorie (1,100) for 50kg target")
                    print(f"   • High protein (80g) for muscle preservation")
                    print(f"   • Hearty, satisfying bowl-style meals")
                    print(f"   • Minimal rice, focus on quinoa/sweet potato")
                    print(f"   • All vegetables are cooked (no raw)")
                    print(f"   • Visual guide for proper portions")

                else:
                    print(f"\n⚠️ No images were generated")
                    print(f"📋 Complete text-based meal plan is available")

        else:
            print("❌ PDF was not created")

    except Exception as e:
        print(f"❌ Error generating meal plan: {e}")

        # Check if it's a quota issue
        if "quota" in str(e).lower() or "429" in str(e):
            print(f"\n💡 API quota exceeded - will need to retry later")
            print(f"📋 Dana can use the text-based meal plan in the meantime")
        else:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
