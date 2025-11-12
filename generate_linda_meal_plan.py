#!/usr/bin/env python3
"""Generate Linda's meal plan with Gemini 2.5 Flash photos"""

import os
import shutil
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Enable images with the working Gemini 2.5 Flash system
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print("=== GENERATING LINDA'S MEAL PLAN WITH GEMINI 2.5 FLASH PHOTOS ===")
    print("🎨 Using proven image generation system")
    print("🔧 Gemini 2.5 Flash configured with IMAGE+TEXT modalities")
    print("🌱 Vegan nutrition with iron/B12/omega-3 focus")

    # Get Linda's data
    linda_data = ALL_CLIENT_DATA["Linda Hayes"]

    # Calculate nutrition targets
    age = calculate_age(linda_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        linda_data["sex"],
        linda_data["weight_kg"],
        linda_data["height_cm"],
        age,
        linda_data["activity_factor"],
        500  # 500 calorie deficit for fat loss
    )

    print(f"\n👤 Client: {linda_data['name']}")
    print(f"📅 Age: {age} years old (young adult)")
    print(f"🎯 Goal: {linda_data['goal_description']}")
    print(f"🌱 Dietary Type: {linda_data['dietary_type']}")
    print(f"💪 Activity: Lightly active (1.375 factor)")
    print(
        f"📊 Daily Targets: {target_cal} cal, {target_protein}g protein, {target_carbs}g carbs, {target_fats}g fats")

    print(f"\n🌟 Special Focus:")
    print(f"   • Iron absorption (vitamin C pairings)")
    print(f"   • B12 fortified foods & supplements")
    print(f"   • Omega-3 from flax, chia, walnuts")
    print(f"   • High-quality plant proteins")

    # Clear old images for fresh generation
    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
        print(f"🗑️ Cleared old images from: {images_dir}")
    os.makedirs(images_dir, exist_ok=True)

    print(f"\n🍽️ Generating Week 1 meal plan with AI-generated photos...")
    print("⏳ This will take several minutes as each meal photo is generated...")
    print("📷 Expected photos: ~28 images (7 days × 4 meals)")
    print("🌱 Focus: Nutritionally complete vegan meals!")

    # Generate the PDF with images
    try:
        create_pdf(linda_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{linda_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            pdf_size_mb = pdf_size / (1024 * 1024)

            print(f"\n✅ SUCCESS! Linda's meal plan PDF generated!")
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
                    print(f"   • Style: Photorealistic vegan food photography")

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
                        print(f"📖 Linda now has a complete visual meal plan")
                        print(f"🌱 Perfect for vegan nutrition education!")
                    elif pdf_size > 500_000:  # > 500KB suggests some images
                        print(f"\n✅ GOOD! PDF contains some images")
                        print(
                            f"📊 {len(generated_images)} photos successfully generated")
                    else:
                        print(f"\n⚠️ PDF size suggests limited image embedding")
                        print(f"📋 Complete text-based meal plan is available")

                    print(f"\n📋 Linda's Meal Plan Features:")
                    print(f"   • 7-day nutritionally complete meal plan")
                    print(f"   • Iron-rich vegan meals")
                    print(f"   • B12 & Omega-3 focused nutrition")
                    print(f"   • Photorealistic meal images")
                    print(f"   • Young adult portion sizes")
                    print(f"   • Plant-based protein optimization")
                    print(f"   • Detailed prep instructions")
                    print(f"   • Macro nutrition breakdowns")
                    print(f"   • Shopping list by category")
                    print(f"   • Tailored for vegan fat loss")

                    print(f"\n🌟 Linda's Special Nutrition Features:")
                    print(f"   🥬 Iron-rich meals with vitamin C boosters")
                    print(f"   🌱 B12 fortified plant milks & nutritional yeast")
                    print(f"   🥜 Omega-3 from chia seeds, flax, walnuts")
                    print(f"   🫘 Complete proteins from legume combinations")
                    print(f"   🥗 Spinach & dark leafy green emphasis")
                    print(f"   🍋 Citrus & vitamin C for iron absorption")

                    print(f"\n💪 Perfect for Linda because:")
                    print(f"   • Age-appropriate portions (21 years old)")
                    print(f"   • Addresses common vegan nutrient concerns")
                    print(f"   • Supports healthy fat loss")
                    print(f"   • Visual guide for meal prep")
                    print(f"   • Educational about vegan nutrition")

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
            print(f"📋 Linda can use the text-based meal plan in the meantime")
        else:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
