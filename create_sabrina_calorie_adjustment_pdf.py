#!/usr/bin/env python3
"""Create Sabrina's calorie adjustment PDF with explanation and game plan"""

import os
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from utils import calculate_age

# Sabrina's data
SABRINA_DATA = {
    "name": "Sabrina Woods",
    "dob": "1999-06-09",
    "sex": "Female",
    "weight_kg": 66.4,
    "height_cm": 168,
    "activity_factor": 1.375,  # Lightly active
    "goal_description": "Body Recomposition - feel strong and energised, fit comfortably into clothes",
    "dietary_type": "Vegan"
}

LOGO_PATH = r"C:\\Users\\Shannon\\OneDrive\\Documents\\cocos logo.png"
OUTPUT_DIR = "meal plans"


def calculate_new_macros(calories: int, protein_target: int = 100):
    """Calculate macros for new calorie target"""

    # Protein: 4 calories per gram
    protein_calories = protein_target * 4

    # Remaining calories for carbs and fats
    remaining_calories = calories - protein_calories

    # Split remaining: 55% carbs, 45% fats (approximate)
    carb_calories = remaining_calories * 0.55
    fat_calories = remaining_calories * 0.45

    # Convert to grams
    carbs = int(carb_calories / 4)  # 4 calories per gram
    fats = int(fat_calories / 9)   # 9 calories per gram

    return protein_target, carbs, fats


def create_sabrina_adjustment_pdf():
    """Create Sabrina's calorie adjustment explanation PDF"""

    print("=== CREATING SABRINA'S CALORIE ADJUSTMENT PDF ===")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Calculate age and new macros
    age = calculate_age(SABRINA_DATA["dob"])
    new_protein, new_carbs, new_fats = calculate_new_macros(1750, 100)
    old_protein, old_carbs, old_fats = calculate_new_macros(
        1900, 120)  # Assume previous protein was 120g

    print(f"👤 Client: {SABRINA_DATA['name']}")
    print(f"📅 Age: {age} years old")
    print(f"⚖️ Current weight: {SABRINA_DATA['weight_kg']} kg")
    print(f"📏 Height: {SABRINA_DATA['height_cm']} cm")
    print(f"🎯 Goal: {SABRINA_DATA['goal_description']}")

    print(f"\n📊 CALORIE ADJUSTMENT:")
    print(f"   Previous: 1900 calories")
    print(f"   New: 1750 calories")
    print(f"   Reduction: 150 calories")

    print(f"\n🍗 MACRO BREAKDOWN:")
    print(f"   Protein: {new_protein}g (maintains muscle)")
    print(f"   Carbs: {new_carbs}g (energy for workouts)")
    print(f"   Fats: {new_fats}g (hormone support)")

    # Create PDF
    pdf_path = os.path.join(
        OUTPUT_DIR, f"{SABRINA_DATA['name']} - Calorie Adjustment.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)

    # Get styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#2E7D32'),
        alignment=1  # Center
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#2E7D32'),
        spaceBefore=20
    )

    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.HexColor('#388E3C'),
        spaceBefore=15
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leftIndent=0,
        rightIndent=0
    )

    highlight_style = ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        backColor=colors.HexColor('#E8F5E8'),
        borderPadding=10,
        borderWidth=1,
        borderColor=colors.HexColor('#4CAF50')
    )

    # Build content
    content = []

    # Title and header
    content.append(Paragraph(f"Calorie Adjustment Plan", title_style))
    content.append(
        Paragraph(f"<b>{SABRINA_DATA['name']}</b>", styles['Heading1']))
    content.append(
        Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    content.append(Spacer(1, 0.5 * inch))

    # Key changes summary
    content.append(Paragraph("🎯 Key Changes Summary", heading_style))

    summary_text = f"""
    <b>Previous Calories:</b> 1,900 daily<br/>
    <b>New Calories:</b> 1,750 daily<br/>
    <b>Reduction:</b> 150 calories<br/>
    <b>New Protein Target:</b> {new_protein}g daily (maintained high for muscle preservation)<br/>
    <b>New Carbs:</b> {new_carbs}g daily<br/>
    <b>New Fats:</b> {new_fats}g daily
    """

    content.append(Paragraph(summary_text, highlight_style))
    content.append(Spacer(1, 0.3 * inch))

    # Why this adjustment
    content.append(Paragraph("🔬 Why This Adjustment?", heading_style))

    why_text = f"""
    Your body has adapted to your current calorie intake of 1,900 calories. This is completely normal and expected! 
    When we eat the same amount consistently, our metabolism adjusts to maintain our current weight.
    <br/><br/>
    <b>The Science:</b> Your body is incredibly smart and efficient. After several weeks at 1,900 calories, 
    your metabolism has likely adapted to this intake level. To continue progressing toward your body recomposition 
    goals, we need to create a new caloric deficit.
    <br/><br/>
    <b>Why 1,750 calories?</b> This 150-calorie reduction is modest and strategic. We want to restart fat loss 
    while preserving your muscle mass and energy levels for your pole dancing and gym sessions.
    """

    content.append(Paragraph(why_text, body_style))
    content.append(Spacer(1, 0.3 * inch))

    # The game plan
    content.append(Paragraph("🎯 The Game Plan: What to Expect", heading_style))

    content.append(
        Paragraph("Phase 1: Initial Adaptation (Weeks 1-2)", subheading_style))

    phase1_text = """
    <b>What will happen:</b> Your body will begin using stored fat for energy again. You should see the scale 
    start moving downward and feel clothes fitting more comfortably.
    <br/><br/>
    <b>What you might experience:</b>
    • Slightly increased hunger (normal and temporary)
    • Mild fatigue as your body adjusts
    • Possible mood fluctuations
    • Scale weight may drop 0.5-1kg in the first week (includes water weight)
    """

    content.append(Paragraph(phase1_text, body_style))

    content.append(
        Paragraph("Phase 2: Steady Progress (Weeks 3-6)", subheading_style))

    phase2_text = """
    <b>What will happen:</b> Your body adapts to the new calorie level. Fat loss continues at a steady, 
    healthy rate of 0.3-0.5kg per week.
    <br/><br/>
    <b>What you might experience:</b>
    • Hunger levels normalize
    • Energy levels stabilize
    • Consistent progress in measurements and photos
    • Improved body composition (less fat, maintained muscle)
    """

    content.append(Paragraph(phase2_text, body_style))

    content.append(
        Paragraph("Phase 3: Next Adaptation (Weeks 6-8)", subheading_style))

    phase3_text = """
    <b>What will happen:</b> Your metabolism will begin adapting to 1,750 calories. Weight loss may slow down 
    or plateau.
    <br/><br/>
    <b>Our response:</b> We'll assess progress and make another strategic adjustment if needed. This might involve:
    • Further reducing calories by 100-150
    • Adding a cardio session
    • Implementing carb cycling
    • Taking a planned diet break to reset metabolism
    """

    content.append(Paragraph(phase3_text, body_style))
    content.append(Spacer(1, 0.3 * inch))

    # What to expect section
    content.append(Paragraph("⚡ What You Might Experience", heading_style))

    expect_text = """
    <b>Week 1-2: Initial Adjustment</b>
    • Increased appetite (your body sensing the deficit)
    • Slightly lower energy, especially in the first few days
    • Possible mood changes or irritability
    • Better sleep quality (less food before bed)
    • Scale weight dropping (includes water weight)
    <br/><br/>
    <b>Week 3-4: Finding Your Rhythm</b>
    • Hunger levels stabilizing
    • Energy returning to normal
    • Seeing visual changes in the mirror
    • Clothes fitting better
    • Strength maintained in the gym
    <br/><br/>
    <b>Week 5-6: Steady Progress</b>
    • Consistent energy levels
    • Regular progress on the scale
    • Improved body composition
    • Better definition and muscle tone
    • Reduced evening snacking urges
    """

    content.append(Paragraph(expect_text, body_style))
    content.append(Spacer(1, 0.3 * inch))

    # Success strategies
    content.append(Paragraph("🌟 Success Strategies", heading_style))

    strategies_text = """
    <b>1. Prioritize Protein</b>
    • Aim for {protein}g daily to preserve muscle mass
    • Include protein at every meal and snack
    • This helps with satiety and maintains metabolism
    <br/><br/>
    <b>2. Stay Hydrated</b>
    • Drink 2-3 liters of water daily
    • Often thirst masquerades as hunger
    • Helps with energy and workout performance
    <br/><br/>
    <b>3. Manage Evening Snacking</b>
    • Plan satisfying dinners to reduce cravings
    • Keep healthy snacks available if needed
    • Practice mindful eating techniques
    <br/><br/>
    <b>4. Monitor Energy for Workouts</b>
    • Time your carbs around pole and gym sessions
    • Don't sacrifice workout intensity for the scale
    • Rest if genuinely fatigued (adaptation is normal)
    <br/><br/>
    <b>5. Track Non-Scale Victories</b>
    • Take weekly progress photos
    • Measure waist, hips, arms
    • Notice energy levels and mood
    • Celebrate fitting into clothes better
    """.format(protein=new_protein)

    content.append(Paragraph(strategies_text, body_style))
    content.append(Spacer(1, 0.3 * inch))

    # When to adjust again
    content.append(Paragraph("🔄 When We'll Adjust Again", heading_style))

    adjust_text = """
    <b>Plateau Indicators (typically 6-8 weeks):</b>
    • No scale movement for 10-14 days
    • No visual changes in photos
    • No improvement in measurements
    • Feeling very comfortable at current intake
    <br/><br/>
    <b>Next Steps Could Include:</b>
    • Small calorie reduction (100-150 calories)
    • Adding 1-2 cardio sessions per week
    • Implementing a structured refeed day
    • Taking a planned diet break to reset metabolism
    <br/><br/>
    <b>Remember:</b> Plateaus are NORMAL and expected. They don't mean you're doing anything wrong – 
    they mean your body is adapting (which is what bodies do!). We'll always have a plan B, C, and D.
    """

    content.append(Paragraph(adjust_text, body_style))
    content.append(Spacer(1, 0.3 * inch))

    # Support section
    content.append(Paragraph("💪 You've Got This!", heading_style))

    support_text = """
    This adjustment is a completely normal part of your body recomposition journey. Your previous 
    progress at 1,900 calories was excellent, and this slight reduction will help you continue moving 
    toward your goals.
    <br/><br/>
    <b>Remember:</b>
    • Your body is incredibly adaptive (that's why we need adjustments)
    • Temporary discomfort during adaptation is normal
    • We're preserving muscle while losing fat
    • Your pole dancing and gym performance remain the priority
    • This is a temporary phase, not forever
    <br/><br/>
    <b>Stay in touch about:</b>
    • Energy levels during workouts
    • Hunger and satiety
    • Sleep quality
    • Mood and stress levels
    • Any concerns or questions
    <br/><br/>
    <i>You're doing amazing, and this adjustment will help you continue progressing toward feeling 
    strong, energized, and confident in your body!</i>
    """

    content.append(Paragraph(support_text, highlight_style))

    # Build PDF
    doc.build(content)

    # Check file size
    pdf_size = os.path.getsize(pdf_path)
    pdf_size_kb = pdf_size / 1024

    print(f"\n✅ SUCCESS! Sabrina's adjustment PDF created!")
    print(f"📄 Location: {pdf_path}")
    print(f"📊 PDF size: {pdf_size:,} bytes ({pdf_size_kb:.1f} KB)")

    print(f"\n📋 PDF Contents:")
    print(f"   • Calorie adjustment explanation (1900 → 1750)")
    print(f"   • Scientific rationale for the change")
    print(f"   • 3-phase timeline and expectations")
    print(f"   • What to experience during adaptation")
    print(f"   • Success strategies for the transition")
    print(f"   • Future adjustment planning")
    print(f"   • Motivational support and encouragement")

    print(f"\n🎯 Key Messages:")
    print(f"   • 150-calorie reduction is strategic and manageable")
    print(f"   • Protein maintained at 100g for muscle preservation")
    print(f"   • Adaptation periods are normal and expected")
    print(f"   • Future adjustments are planned and strategic")
    print(f"   • Focus on non-scale victories and overall progress")

    return pdf_path


if __name__ == "__main__":
    create_sabrina_adjustment_pdf()

    print(f"\n🌟 CALORIE ADJUSTMENT SUMMARY:")
    print(f"   📊 Previous: 1900 calories → New: 1750 calories")
    print(f"   🍗 Protein: 100g (muscle preservation priority)")
    print(f"   ⏱️ Expected adaptation: 1-2 weeks")
    print(f"   🔄 Next review: 6-8 weeks")
    print(f"   💪 Goal: Continue body recomposition progress")

    print(f"\n✅ Ready to support Sabrina through this transition phase!")
