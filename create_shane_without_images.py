#!/usr/bin/env python3
"""Generate Shane's meal plan without images but with a note about image availability"""

import os
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf


def main():
    # Disable images for now since your API key doesn't support Imagen
    os.environ["ENABLE_MEAL_IMAGES"] = "0"

    print("=== GENERATING SHANE'S MEAL PLAN (WITHOUT IMAGES) ===")
    print("Note: Your API key supports text generation but not image generation.")
    print("Image generation requires Imagen models which may need different permissions.")
    print()

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]
    print(f"Client: {shane_data['name']}")
    print(f"Goal: {shane_data['goal_description']}")
    print()

    # Generate Week 1 PDF without images
    print("Generating Week 1 meal plan PDF (text-only)...")
    try:
        create_pdf(shane_data, week=1)
        print("✅ Successfully generated Shane Week 1 meal plan PDF!")

        # Check results
        pdf_path = "meal plans/Shane Minahan - Week 1.pdf"
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"📄 PDF size: {size:,} bytes")
            print("📁 Location: meal plans/Shane Minahan - Week 1.pdf")

        print()
        print("📝 SOLUTION FOR IMAGES:")
        print("To enable image generation, you need:")
        print("1. Access to Imagen models (imagen-3.0-generate-001)")
        print("2. Enable the Vertex AI API in your Google Cloud project")
        print("3. Or use a different image generation service")
        print()
        print("For now, Shane has a complete meal plan with:")
        print("• Cover page with nutrition targets")
        print("• 7-day meal plan with detailed recipes")
        print("• Shopping list with Woolworths links")
        print("• Macro breakdowns for each meal")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
