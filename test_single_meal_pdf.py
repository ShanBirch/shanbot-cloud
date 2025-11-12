#!/usr/bin/env python3
"""Test generating a PDF with a single meal and image to isolate the issue"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from utils import maybe_generate_meal_image


def create_test_pdf():
    print("=== CREATING TEST PDF WITH SINGLE MEAL + IMAGE ===")

    # Set environment for images
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    # Test meal data
    meal_name = "High-Protein Greek Yogurt Bowl"
    ingredients = "- 200g Greek Yogurt (low-fat)\n- 30g Whey Protein (vanilla)\n- 80g Mixed Berries\n- 20g Almonds\n- 10g Honey"
    preparation = "Whisk protein into yogurt. Top with berries, almonds, and a drizzle of honey."
    macros = "Macros: 480 calories, 40g carbs, 45g protein, 16g fats"

    # Generate image
    print(f"🖼️ Generating image for: {meal_name}")
    img_path = maybe_generate_meal_image(
        meal_name,
        ingredients,
        preparation,
        out_dir=os.path.join("meal plans", "images"),
        macros_text=macros
    )

    if img_path and os.path.exists(img_path):
        img_size = os.path.getsize(img_path)
        print(f"✅ Image generated: {img_path} ({img_size:,} bytes)")
    else:
        print(f"❌ No image generated")
        return False

    # Create PDF
    print(f"\n📄 Creating test PDF...")
    pdf_path = os.path.join("meal plans", "test_single_meal.pdf")

    # Create document
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontSize=16, spaceAfter=12)
    normal_style = styles['Normal']

    # Add title
    story.append(Paragraph("TEST MEAL WITH IMAGE", title_style))
    story.append(Spacer(1, 0.3*inch))

    # Meal content
    meal_flowables = []

    # Meal name
    meal_flowables.append(Paragraph(f"<b>{meal_name}</b>", title_style))
    meal_flowables.append(Spacer(1, 0.1*inch))

    # Ingredients
    meal_flowables.append(Paragraph("<b>Ingredients:</b>", normal_style))
    for ingredient in ingredients.split('\n'):
        if ingredient.strip():
            meal_flowables.append(Paragraph(ingredient.strip(), normal_style))
    meal_flowables.append(Spacer(1, 0.1*inch))

    # Preparation
    meal_flowables.append(
        Paragraph(f"<b>Preparation:</b> {preparation}", normal_style))
    meal_flowables.append(Spacer(1, 0.1*inch))

    # Macros
    meal_flowables.append(Paragraph(f"<b>{macros}</b>", normal_style))
    meal_flowables.append(Spacer(1, 0.2*inch))

    # Add image
    if img_path and os.path.exists(img_path):
        try:
            print(f"🖼️ Adding image to PDF: {img_path}")

            # Get image dimensions
            reader = ImageReader(img_path)
            iw, ih = reader.getSize()
            print(f"Image dimensions: {iw}x{ih}")

            # Calculate size preserving aspect ratio
            max_width = 4 * inch
            max_height = 5 * inch

            aspect = ih / float(iw) if iw else 0.75
            img_width = max_width
            img_height = img_width * aspect

            if img_height > max_height:
                scale = max_height / img_height
                img_width = img_width * scale
                img_height = max_height

            print(f"PDF image size: {img_width:.1f} x {img_height:.1f}")

            # Create image flowable
            image_flowable = Image(
                img_path, width=img_width, height=img_height, hAlign='CENTER')
            meal_flowables.append(image_flowable)
            meal_flowables.append(Spacer(1, 0.25*inch))

            print("✅ Image flowable added")

        except Exception as e:
            print(f"❌ Error adding image: {e}")
            import traceback
            traceback.print_exc()

    # Keep meal together
    story.append(KeepTogether(meal_flowables))

    # Build PDF
    try:
        print(f"📄 Building PDF...")
        doc.build(story)
        print(f"✅ PDF created: {pdf_path}")

        # Check result
        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print(f"📊 PDF size: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")

            if pdf_size > 100000:  # > 100KB suggests image is embedded
                print("🎉 SUCCESS! PDF size suggests image is embedded!")
                return True
            else:
                print("⚠️ PDF size seems small - image might not be embedded")
                return False
        else:
            print("❌ PDF file not created")
            return False

    except Exception as e:
        print(f"❌ Error building PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_test_pdf()

    if success:
        print("\n🎉 Test successful! Image embedding is working.")
        print("💡 The issue might be in the main meal plan generation logic.")
    else:
        print("\n❌ Test failed! Need to investigate image embedding.")
