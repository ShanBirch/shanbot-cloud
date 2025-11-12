LINDA_CLIENT_DATA = {
    "name": "Linda Hayes",
    "dob": "2003-09-21",
    "sex": "Female",
    "weight_kg": 66.3,
    "height_cm": 162,
    "activity_factor": 1.375,  # Lightly active label
    "goal_description": "Vegan Fat Loss (iron/B12/omega-3 focus)",
    "dietary_type": "Vegan",
    "preferred_meals": {},  # Will be populated with specific meal content
    "foods_to_avoid": [],
    "meal_notes": "Client requires meals with emphasis on protein, iron, B12, and Omega-3 for vegan fat loss."
}

# Meal rotations for Linda
LINDA_LUNCHES_MON_WED = {
    1: ("Chickpea & Tofu Spinach Curry (Mon–Wed batch) with Brown Rice",
        "- 120g Chickpeas (canned, drained)\n- 100g Firm Tofu (cubed)\n- 120g Baby Spinach\n- 120g Capsicum & Onion (sliced)\n- 120g Light Coconut Milk\n- 120g Korma Simmer Sauce (low sugar)\n- 150g Cooked Brown Rice\n- 5ml Lime Juice (vitamin C for iron absorption)",
        "Simmer tofu, chickpeas, veg with coconut milk and korma; stir in spinach. Serve over rice, finish with lime (15 minutes)",
        "Macros: 450 calories, 57g carbs, 24g protein, 14g fats"),
    2: ("Chickpea & Tempeh Tomato-Basil Bowl with Quinoa",
        "- 120g Chickpeas (canned, drained)\n- 80g Tempeh (cubed)\n- 150g Cherry Tomatoes & Spinach\n- 200ml Tomato Passata\n- 180g Cooked Quinoa\n- 8g Fresh Basil\n- 5ml Olive Oil",
        "Sauté tempeh in oil, add passata, chickpeas, veg; simmer 10 min. Serve over quinoa; top with basil (15 minutes)",
        "Macros: 450 calories, 55g carbs, 25g protein, 13g fats"),
    3: ("Smoky Black Bean & Tofu Bowl with Brown Rice",
        "- 100g Firm Tofu (cubed)\n- 120g Black Beans (drained)\n- 200g Capsicum, Corn, Onion mix\n- 150g Cooked Brown Rice\n- 30g Avocado\n- 40g Salsa\n- Lime wedge",
        "Pan-sear tofu; warm beans with veg and salsa; serve over rice with avocado and lime (15 minutes)",
        "Macros: 450 calories, 58g carbs, 24g protein, 13g fats"),
    4: ("Red Lentil & Veggie Dahl with Basmati",
        "- 180g Cooked Red Lentils\n- 200g Spinach, Tomato, Onion\n- 150g Cooked Basmati Rice\n- 120ml Light Coconut Milk\n- 10g Curry Paste\n- Coriander, lime",
        "Simmer lentils with coconut milk, curry paste and veg; serve over rice; garnish (15 minutes)",
        "Macros: 450 calories, 60g carbs, 23g protein, 12g fats"),
    5: ("Mediterranean Tofu Bowl with Buckwheat",
        "- 120g Baked Tofu\n- 200g Roasted Veg (zucchini, capsicum, onion)\n- 180g Cooked Buckwheat\n- 15g Tahini + Lemon\n- Parsley",
        "Roast veg ahead; assemble bowl with buckwheat, tofu, tahini-lemon dressing (12 minutes)",
        "Macros: 450 calories, 54g carbs, 25g protein, 14g fats"),
    6: ("TVP Bolognese Bowl with Protein Pasta",
        "- 40g TVP (rehydrated)\n- 200ml Tomato Passata\n- 150g Mushrooms, sliced\n- 75g Vetta SMART Protein Pasta (dry)\n- 10g Nutritional Yeast\n- 5ml Olive Oil",
        "Sauté mushrooms; add TVP and passata; simmer 10 min; toss with pasta; top with nutritional yeast (15 minutes)",
        "Macros: 450 calories, 50g carbs, 28g protein, 12g fats"),
}

LINDA_LUNCHES_THU_SAT = {
    1: ("Quinoa Veggie Bowl (Thu–Sat batch) with Tofu & Tahini",
        "- 180g Cooked Quinoa\n- 120g Firm Tofu (baked or pan-seared)\n- 250g Roasted Seasonal Veg (broccoli, carrot, capsicum)\n- 15g Tahini + Lemon + Water (dressing)\n- 30g Sauerkraut (optional)",
        "Roast veg in batch; assemble bowl with quinoa, tofu, veg, tahini-lemon dressing (15 minutes)",
        "Macros: 450 calories, 54g carbs, 25g protein, 14g fats"),
    2: ("Buckwheat Veggie Bowl with Tempeh & Miso-Tahini",
        "- 180g Cooked Buckwheat\n- 100g Tempeh\n- 250g Roasted Veg\n- 10g Miso + 10g Tahini + Water (dressing)",
        "Roast veg in batch; sear tempeh; whisk miso-tahini; assemble (15 minutes)",
        "Macros: 450 calories, 52g carbs, 26g protein, 14g fats"),
}

LINDA_DINNERS_ROT = {
    1: [
        ("High-Protein Lentil Bolognese with Protein Pasta",
         "- 80g Vetta SMART Protein Pasta (dry)\n- 160g Cooked Red Lentils\n- 150g Mushrooms, sliced\n- 200ml Tomato Passata\n- 10g Nutritional Yeast (B12-fortified)\n- 5ml Olive Oil",
         "Sauté mushrooms in oil, add lentils and passata; simmer 10 min. Toss with pasta, top with nutritional yeast (15 minutes)",
         "Macros: 440 calories, 52g carbs, 29g protein, 11g fats"),
        ("TVP Tacos (2 shells) with Black Beans & Avocado",
         "- 2 Hard Taco Shells\n- 50g TVP (dry), rehydrated with taco spice\n- 80g Black Beans (canned, drained)\n- 40g Avocado\n- 60g Shredded Lettuce\n- 40g Salsa (no added sugar)",
         "Season TVP; assemble tacos with beans, lettuce, salsa, avocado (12 minutes)",
         "Macros: 410 calories, 44g carbs, 30g protein, 12g fats"),
        ("Tempeh Peanut Stir-Fry with Veg & Buckwheat",
         "- 80g Tempeh, sliced\n- 250g Mixed Stir-Fry Veg (broccoli, capsicum, carrot)\n- 10g Peanut Butter + 10ml Soy Sauce + Water to thin (peanut sauce)\n- 120g Cooked Buckwheat",
         "Stir-fry tempeh and veg; whisk PB + soy + water; toss to coat; serve over buckwheat (15 minutes)",
         "Macros: 420 calories, 46g carbs, 26g protein, 15g fats")
    ],
    2: [
        ("Cauliflower-Base Vegan Pizza (Veg + Vegan Cheese)",
         "- 1 Cauliflower Pizza Base\n- 35g Vegan Pizza Cheese\n- 120g Mushrooms, sliced\n- 80g Capsicum, sliced\n- 2 tbsp Tomato Paste",
         "Assemble and bake at 200°C for 10–12 minutes (12 minutes)",
         "Macros: 420 calories, 48g carbs, 17g protein, 16g fats"),
        ("Chickpea & Spinach Coconut Curry",
         "- 140g Chickpeas\n- 200g Spinach & Broccoli\n- 120ml Light Coconut Milk\n- 10g Curry Paste\n- 150g Cooked Basmati",
         "Simmer sauce with chickpeas and veg; serve over rice (15 minutes)",
         "Macros: 430 calories, 58g carbs, 20g protein, 12g fats"),
        ("Tofu Satay Bowl",
         "- 120g Baked Tofu\n- 200g Steamed Veg\n- 20g Peanut Satay (PB+soy+lime)\n- 150g Cooked Brown Rice",
         "Assemble warm bowl; drizzle satay (12 minutes)",
         "Macros: 430 calories, 56g carbs, 24g protein, 12g fats"),
    ],
    3: [
        ("Lentil Shepherd's Skillet",
         "- 200g Mixed Veg\n- 180g Cooked Red Lentils\n- 200g Cauli-Potato Mash\n- Herbs",
         "Simmer lentils with veg; top with mash; grill 5 min (15 minutes)",
         "Macros: 430 calories, 55g carbs, 23g protein, 11g fats"),
        ("Protein Pasta Arrabbiata with Tofu",
         "- 80g Protein Pasta (dry)\n- 200ml Spicy Passata\n- 120g Baked Tofu\n- Basil",
         "Cook pasta; toss with passata and tofu; garnish (12 minutes)",
         "Macros: 440 calories, 52g carbs, 28g protein, 10g fats"),
        ("Black Bean Chili & Rice",
         "- 140g Black Beans\n- 200g Tomato, Onion, Capsicum\n- Chili spice\n- 150g Cooked Brown Rice",
         "Simmer chili 12 min; serve over rice (15 minutes)",
         "Macros: 420 calories, 58g carbs, 21g protein, 10g fats"),
    ],
    4: [
        ("Miso-Tahini Tofu Bowl",
         "- 120g Tofu\n- 200g Broccoli & Carrot\n- 10g Miso + 10g Tahini\n- 150g Cooked Quinoa",
         "Steam veg, sear tofu; whisk miso-tahini; assemble (12 minutes)",
         "Macros: 430 calories, 52g carbs, 26g protein, 12g fats"),
        ("TVP Tacos (2 shells) with Black Beans & Avocado",
         "- As earlier",
         "As earlier (12 minutes)",
         "Macros: 410 calories, 44g carbs, 30g protein, 12g fats"),
        ("High-Protein Lentil Bolognese with Protein Pasta",
         "- As earlier",
         "As earlier (15 minutes)",
         "Macros: 440 calories, 52g carbs, 29g protein, 11g fats"),
    ],
    5: [
        ("Ginger Tofu & Greens with Rice",
         "- 120g Tofu\n- 250g Greens (bok choy, broccoli)\n- 10ml Soy + Ginger + Garlic\n- 150g Cooked Rice",
         "Stir-fry; serve over rice (12 minutes)",
         "Macros: 430 calories, 56g carbs, 25g protein, 11g fats"),
        ("Protein Pasta Primavera",
         "- 80g Protein Pasta (dry)\n- 200g Mixed Veg\n- 10ml Olive Oil\n- Lemon & Herbs",
         "Cook pasta; toss with sautéed veg and oil; lemon (12 minutes)",
         "Macros: 440 calories, 50g carbs, 26g protein, 14g fats"),
        ("Tempeh Peanut Stir-Fry with Veg & Buckwheat",
         "- As earlier",
         "As earlier (15 minutes)",
         "Macros: 420 calories, 46g carbs, 26g protein, 15g fats"),
    ],
    6: [
        ("Cauliflower-Base Vegan Pizza (Veg + Vegan Cheese)",
         "- As earlier",
         "As earlier (12 minutes)",
         "Macros: 420 calories, 48g carbs, 17g protein, 16g fats"),
        ("Chickpea & Spinach Coconut Curry",
         "- As earlier",
         "As earlier (15 minutes)",
         "Macros: 430 calories, 58g carbs, 20g protein, 12g fats"),
        ("Protein Pasta Arrabbiata with Tofu",
         "- As earlier",
         "As earlier (12 minutes)",
         "Macros: 440 calories, 52g carbs, 28g protein, 10g fats"),
    ],
}

# Placeholder for Romy's data and meal rotations
ROMY_CLIENT_DATA = {
    "name": "Romy",
    "dob": "1989-10-24",
    "sex": "Female",
    "weight_kg": 58.0,
    "height_cm": 167,
    "activity_factor": 1.55,  # Moderately active - moderate exercise 6-7 days per week
    "goal_description": "Body Recomposition - pbf 20%, build strength and endurance",
    "dietary_type": "High Protein Vegan",
    "preferred_meals": {
        "breakfasts": ["Cereal/oats", "Smoothies", "Banana"],
        "lunches": ["Sandwich/toastie/jaffle", "Wraps", "Salads with sweet potato, roasted tofu, greens, seeds, nuts"],
        "dinners": ["Chips", "Pasta", "Pizza", "Fried rice with veges and tofu", "Stir fry", "Rice and curry", "Burrito", "Noodle stir fry"],
        "snacks": ["Choc brownie/cake (rarely)", "All veges and nuts and seeds"]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork", "Shellfish", "Dairy"],
    "meal_notes": "Likes measurements in cups. Daily HIIT cycling 30 mins, Zumba 45mins Tuesdays. Loves variety - pasta, rice dishes, stir frys, salads.",
    "target_calories": 1200,  # Reduced from ~1496 for more aggressive fat loss
    "target_protein_g": 99,   # Maintain high protein for body recomposition
    "workout_time": "Daily",
    "training_days": "Daily HIIT cycling, Tuesdays Zumba",
    "workout_type": "HIIT cycling (5min warmup, 25min intervals, cooldown), Zumba, bodyweight exercises",
    "meal_times": {
        "breakfast": "7:00 AM",
        "lunch": "1:00 PM",
        "snack": "4:00 PM",
        "dinner": "7:00 PM"
    }
}

ROMY_LUNCHES_MON_WED = {
    1: ("Mediterranean Pasta Salad (Mon–Wed batch)",
        "- 3/4 cup Cooked Pasta\n- 1/3 cup Cherry Tomatoes\n- 1/4 cup Vegan Feta\n- 2 tbsp Olives\n- 3/4 cup Baby Spinach\n- 1 tbsp Olive Oil Dressing",
        "Cook pasta, combine with all ingredients. Toss with dressing. (10 mins)",
        "Macros: 320 calories, 42g carbs, 16g protein, 14g fats"),
    2: ("Italian Wrap (Mon–Wed batch)",
        "- 1 Large Wholemeal Tortilla\n- 1/3 cup Marinated Tofu\n- 1/3 cup Roasted Vegetables\n- 3 tbsp Hummus\n- 3/4 cup Mixed Greens",
        "Marinate tofu: Mix 1 tbsp soy sauce + 1/2 tsp garlic + 1/2 tsp ginger, marinate cubed tofu 15+ mins. Spread hummus on wrap, add marinated tofu, roasted veg, greens. Roll tightly. (5 mins)",
        "Macros: 300 calories, 32g carbs, 18g protein, 14g fats"),
}

ROMY_LUNCHES_THU_SAT = {
    1: ("Veggie Fried Rice with Tofu (Thu–Sat batch)",
        "- 3/4 cup Cooked Rice\n- 1/3 cup Firm Tofu (cubed)\n- 3/4 cup Mixed Vegetables\n- 1/2 tbsp Soy Sauce\n- 1/2 tsp Sesame Oil\n- Spring Onions",
        "Stir fry tofu and vegetables, add rice and seasonings. (15 mins)",
        "Macros: 320 calories, 48g carbs, 18g protein, 10g fats"),
    2: ("Power Salad with Sweet Potato & Seeds (Thu–Sat batch)",
        "- 1 1/2 cups Mixed Greens\n- 1/3 cup Roasted Sweet Potato\n- 1/3 cup Roasted Tofu\n- 2 tbsp Mixed Seeds & Nuts\n- 1 tbsp Tahini Dressing",
        "Assemble greens, sweet potato, tofu, seeds and nuts. Drizzle with tahini dressing. (8 mins)",
        "Macros: 300 calories, 28g carbs, 16g protein, 18g fats"),
}

ROMY_DINNERS_ROT = {
    1: [
        ("Ultimate Veggie Pizza with Tofu",
         "- 1 Small Pizza Base\n- 1/3 cup Tomato Sauce\n- 1/4 cup Vegan Cheese\n- 1/4 cup Cubed Tofu\n- 3/4 cup Mixed Vegetables\n- Fresh Basil",
         "Top pizza base with sauce, cheese, tofu, vegetables. Bake until crispy. (20 mins)",
         "Macros: 350 calories, 38g carbs, 22g protein, 16g fats"),
        ("Loaded Burrito Bowl",
         "- 2/3 cup Brown Rice\n- 1/3 cup Black Beans\n- 1/3 cup Roasted Vegetables\n- 2 tbsp Avocado\n- 1 tbsp Salsa",
         "Layer rice, beans, vegetables, avocado and salsa in bowl. (10 mins)",
         "Macros: 320 calories, 52g carbs, 14g protein, 8g fats"),
        ("Asian Noodle Stir Fry",
         "- 3/4 cup Cooked Noodles\n- 1/3 cup Firm Tofu\n- 3/4 cup Asian Vegetables\n- 1/2 tbsp Soy Sauce\n- 1/2 tsp Sesame Oil",
         "Stir fry tofu and vegetables, toss with noodles and seasonings. (15 mins)",
         "Macros: 340 calories, 48g carbs, 18g protein, 12g fats"),
    ],
}

ROMY_BREAKFASTS_ROT = {
    1: ("Berry Smoothie Bowl",
        "- 3/4 cup Frozen Mixed Berries\n- 1/3 cup Soy Milk\n- 1/2 Banana (sliced)\n- 3 tbsp Granola\n- 1 tbsp Chia Seeds\n- 1/2 tbsp Almond Butter",
        "Blend berries and soy milk, pour into bowl. Top with banana, granola, chia seeds and almond butter. (5 mins)",
        "Macros: 290 calories, 48g carbs, 12g protein, 8g fats"),
    2: ("Protein Oat Bowl with Banana",
        "- 1/2 cup Rolled Oats\n- 3/4 cup Soy Milk\n- 1/2 Banana (sliced)\n- 1 tbsp Peanut Butter\n- 1/2 tbsp Maple Syrup\n- Pinch of Cinnamon\n- 1 tbsp Plant Protein Powder",
        "Cook oats with soy milk, stir in protein powder when cool. Top with banana, peanut butter, maple syrup and cinnamon. (8 mins)",
        "Macros: 320 calories, 48g carbs, 18g protein, 10g fats"),
}

ROMY_SNACKS_ROT = {
    1: ("Green Power Smoothie",
        "- 3/4 cup Spinach\n- 1/2 Banana\n- 1/3 cup Mango\n- 3/4 cup Coconut Water\n- 1/2 tbsp Chia Seeds",
        "Blend all ingredients until smooth. (3 mins)",
        "Macros: 140 calories, 32g carbs, 4g protein, 2g fats"),
    2: ("Mixed Nuts & Seeds Trail Mix",
        "- 2 tbsp Mixed Nuts\n- 1/2 tbsp Pumpkin Seeds\n- 1/2 tbsp Sunflower Seeds\n- 1 tbsp Dried Fruit (no sugar)",
        "Mix all ingredients. (1 min)",
        "Macros: 140 calories, 12g carbs, 6g protein, 10g fats"),
}

# Placeholder for Hannah's data and meal rotations
HANNAH_CLIENT_DATA = {
    "name": "Hannah",
    "dob": "1998-09-29",
    "sex": "Female",
    "weight_kg": 76.5,
    "height_cm": 164.5,
    "activity_factor": 1.375,  # Lightly active - light exercise 6-7 days per week
    "goal_description": "Fat Loss - goal weight 68kg for body confidence and improved health",
    "dietary_type": "Balanced Vegan",
    "preferred_meals": {
        "breakfasts": ["Pancakes", "Smoothies", "Juice"],
        "lunches": ["Salad", "Wraps", "Spring rolls"],
        "dinners": ["Thai curries", "Shepherds pie", "Pasta", "Burgers"],
        "snacks": ["Smoothies", "Fruit"]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork", "Shellfish", "Dairy"],
    "meal_notes": "Rock climbing 2-3x per week, daily walking. Enjoys Thai curries, pasta, burgers. Prefers cardio that isn't running.",
    "workout_time": "Mondays, Wednesdays (rock climbing)",
    "training_days": "Daily walking, rock climbing 2-3x per week (Mon/Wed)",
    "workout_type": "Rock climbing, strength training, squats, basketball, swimming, walking, non-running cardio",
    "meal_times": {
        "breakfast": "8:00 AM",
        "lunch": "12:00 PM",
        "snack": "3:00 PM",
        "dinner": "6:00 PM"
    }
}

HANNAH_LUNCHES_MON_WED = {
    1: ("Fresh Rainbow Salad Bowl (Mon–Wed batch)",
        "- 150g Mixed Greens\n- 100g Cherry Tomatoes\n- 80g Cucumber\n- 60g Carrots\n- 100g Chickpeas\n- 30ml Lemon Vinaigrette",
        "Combine all ingredients in bowl, toss with dressing. (8 mins)",
        "Macros: 480 calories, 52g carbs, 20g protein, 18g fats"),
    2: ("Veggie Wrap with Hummus (Mon–Wed batch)",
        "- 1 Large Wholemeal Tortilla\n- 80g Hummus\n- 100g Roasted Vegetables\n- 60g Mixed Greens\n- 50g Sprouts",
        "Spread hummus on wrap, add vegetables and greens. Roll tightly. (5 mins)",
        "Macros: 460 calories, 48g carbs, 18g protein, 20g fats"),
}

HANNAH_LUNCHES_THU_SAT = {
    1: ("Asian Spring Rolls with Peanut Sauce (Thu–Sat batch)",
        "- 4 Rice Paper Wraps\n- 100g Fresh Vegetables (carrot, cucumber, herbs)\n- 80g Marinated Tofu\n- 40g Peanut Dipping Sauce",
        "Soften rice paper, fill with vegetables and tofu. Serve with peanut sauce. (15 mins)",
        "Macros: 420 calories, 45g carbs, 16g protein, 18g fats"),
    2: ("Thai-Style Salad Bowl (Thu–Sat batch)",
        "- 150g Mixed Asian Greens\n- 100g Edamame\n- 80g Red Cabbage\n- 60g Carrots\n- 30ml Thai Dressing",
        "Combine all ingredients, toss with Thai dressing. (8 mins)",
        "Macros: 440 calories, 38g carbs, 20g protein, 22g fats"),
}

HANNAH_DINNERS_ROT = {
    1: [
        ("Hannah's Favorite Thai Green Curry",
         "- 200g Mixed Vegetables (eggplant, bamboo shoots, capsicum)\n- 150ml Coconut Milk\n- 60ml Thai Green Curry Paste\n- 150g Jasmine Rice\n- Fresh Thai Basil\n- Lime wedge",
         "Simmer vegetables with coconut milk and curry paste. Serve over rice with basil and lime. Hannah's absolute favorite! (20 mins)",
         "Macros: 580 calories, 72g carbs, 18g protein, 24g fats"),
        ("Classic Vegan Shepherd's Pie",
         "- 200g Lentils & Mixed Vegetables (carrot, peas, onion)\n- 150g Mashed Potato (with plant milk)\n- 100ml Rich Vegetable Gravy\n- Fresh Thyme",
         "Layer seasoned lentil mixture, top with creamy mashed potato, bake until golden. Hannah's comfort food! (35 mins)",
         "Macros: 520 calories, 68g carbs, 22g protein, 16g fats"),
        ("Creamy Pasta with Roasted Vegetables",
         "- 120g Pasta (Hannah's choice)\n- 150g Roasted Mediterranean Vegetables\n- 80g Vegan Cream Cheese\n- 30ml Olive Oil\n- Fresh Basil & Parsley",
         "Cook pasta, toss with roasted vegetables, vegan cream cheese and herbs. Hannah loves pasta! (18 mins)",
         "Macros: 560 calories, 65g carbs, 20g protein, 24g fats"),
    ],
}

HANNAH_BREAKFASTS_ROT = {
    1: ("High-Protein Vegan Pancakes (Mon-Wed batch)",
        "- 120g Self-Raising Flour\n- 250ml Unsweetened Almond Milk\n- 30g Plant Protein Powder\n- 20g Maple Syrup\n- 100g Fresh Berries\n- 15g Vegan Butter\n- Vanilla Extract",
        "Mix flour, almond milk, protein powder, maple syrup and vanilla. Cook pancakes, serve with berries and vegan butter. (15 mins)",
        "Macros: 520 calories, 68g carbs, 28g protein, 16g fats"),
    2: ("Power Green Smoothie Bowl (Thu-Sat batch)",
        "- 200ml Fresh Orange Juice\n- 100g Spinach\n- 1 Banana\n- 100g Mango\n- 30g Plant Protein Powder\n- 20g Granola\n- Ice",
        "Blend juice, spinach, banana, mango, protein powder and ice. Pour into bowl, top with granola. (5 mins)",
        "Macros: 480 calories, 78g carbs, 32g protein, 8g fats"),
}

HANNAH_SNACKS_ROT = {
    1: ("Fresh Fruit Smoothie",
        "- 200ml Coconut Water\n- 100g Mixed Berries\n- 1/2 Banana\n- 100g Mango\n- 15g Chia Seeds",
        "Blend all ingredients until smooth. Hannah's refreshing snack! (3 mins)",
        "Macros: 250 calories, 52g carbs, 6g protein, 6g fats"),
    2: ("Energy Fruit Bowl",
        "- 100g Mixed Fresh Fruit (apple, berries, grapes)\n- 30g Granola\n- 20g Nuts & Seeds\n- 15g Coconut Yogurt",
        "Combine all ingredients in a bowl. Hannah's natural energy boost! (3 mins)",
        "Macros: 320 calories, 48g carbs, 8g protein, 12g fats"),
}

# Placeholder for Amy's data and meal rotations
AMY_CLIENT_DATA = {
    "name": "Amy",
    "dob": "1984-07-11",
    "sex": "Female",
    "weight_kg": 45.2,
    "height_cm": 157.5,
    "activity_factor": 1.375,  # Lightly active - light exercise 6-7 days per week
    "goal_description": "Body Recomposition - Lose fat, build muscle, get in a good rhythm with healthy eating habits",
    "dietary_type": "High Protein Vegetarian",
    "preferred_meals": {
        "breakfasts": ["Porridge", "French toast", "Breakfast cook up (beans, sourdough, spinach, avo, tomato, hash browns, eggs)"],
        "lunches": ["Veggie burger", "Cheese and tomato toasties", "Soups with crusty bread"],
        "dinners": ["Fried rice", "Nachos/tacos/mexican", "Salt and pepper tofu", "Curries", "Veg lasagne"],
        "snacks": ["Chocolate and variations"]
    },
    "foods_to_avoid": ["Pork", "Shellfish", "Fish"],
    "meal_notes": "Loves Mexican food, fried rice, curries, chocolate. Bodyfit twice per week + daily dog walks. Prefers variety and comfort foods.",
    "workout_time": "Wed, Thurs, Fri, Sat, Sun",
    "training_days": "Bodyfit twice per week, daily dog walks, cycling when fit",
    "workout_type": "Weights at bodyfit, walking, cycling, wants to get back to running",
    "meal_times": {
        "breakfast": "7:30 AM",
        "lunch": "12:30 PM",
        "snack": "3:30 PM",
        "dinner": "6:30 PM"
    }
}

AMY_LUNCHES_MON_WED = {
    1: ("High-Protein Cheese & Tomato Toastie (Mon–Wed batch)",
        "- 2 Slices Helga's High Protein Bread\n- 60g Bega 50% Less Fat Cheese\n- 100g Tomato (sliced)\n- 10g Butter\n- Side of 60g mixed greens",
        "Butter high protein bread, layer Bega cheese and tomato, grill until golden and cheese melts. Serve with fresh greens. (8 mins)",
        "Macros: 480 calories, 38g carbs, 32g protein, 22g fats"),
    2: ("Vegetable Soup with High-Protein Bread (Mon–Wed batch)",
        "- 300ml Vegetable Soup (homemade or quality store-bought)\n- 2 Slices Helga's High Protein Bread\n- 20g Butter\n- 20g Bega 50% Less Fat Cheese (grated)",
        "Heat soup, toast high protein bread with butter, sprinkle Bega cheese on top. (10 mins)",
        "Macros: 450 calories, 45g carbs, 28g protein, 20g fats"),
}

AMY_LUNCHES_THU_SAT = {
    1: ("Mexican Nachos Bowl with Bega Cheese (Thu–Sat batch)",
        "- 60g Corn Tortilla Chips\n- 120g Refried Beans\n- 60g Bega 50% Less Fat Cheese (melted)\n- 50g Avocado\n- 40g Salsa\n- 30g Sour Cream\n- Jalapeños",
        "Layer corn tortilla chips, beans, melted Bega cheese. Top with avocado, salsa, sour cream and jalapeños. (8 mins)",
        "Macros: 520 calories, 48g carbs, 26g protein, 28g fats"),
    2: ("High-Protein Veggie Burger (Thu–Sat batch)",
        "- 1 Vegetarian Burger Patty\n- 1 High-Protein Burger Bun\n- 40g Bega 50% Less Fat Cheese\n- 50g Lettuce & Tomato\n- Side of 60g Sweet Potato Fries",
        "Cook burger patty, assemble with Bega cheese, lettuce, tomato. Serve with sweet potato fries. (12 mins)",
        "Macros: 480 calories, 48g carbs, 32g protein, 18g fats"),
}

AMY_DINNERS_ROT = {
    1: [
        ("High-Protein Vegetarian Fried Rice",
         "- 120g Cooked Jasmine Rice\n- 100g Mixed Vegetables (carrot, peas, corn)\n- 2 Eggs (scrambled)\n- 120g Soyco High Protein Tofu (cubed)\n- 15ml Soy Sauce\n- 10ml Sesame Oil\n- Spring Onions",
         "Scramble eggs, set aside. Stir fry vegetables and Soyco tofu. Add rice, soy sauce, sesame oil. Combine with eggs. (15 mins)",
         "Macros: 620 calories, 58g carbs, 38g protein, 26g fats"),
        ("Sweet Chilli Tofu with Asian Greens",
         "- 150g Sweet Chilli Tofu\n- 200g Asian Greens (bok choy, broccoli)\n- 120g Cooked Rice\n- Sugar-free Sweet Chilli Sauce\n- 15ml Soy Sauce\n- 10ml Sesame Oil",
         "Pan fry sweet chilli tofu until crispy. Stir fry greens. Serve over rice with soy sauce and extra sweet chilli. (18 mins)",
         "Macros: 580 calories, 55g carbs, 32g protein, 24g fats"),
        ("High-Protein Vegetable Pizza",
         "- 100g Protein Pizza Base\n- 80g Mixed Vegetables (capsicum, zucchini, mushroom)\n- 40g Bega 50% Less Fat Cheese\n- 2 Eggs (cracked on top)\n- Tomato Paste\n- Fresh Basil",
         "Top protein pizza base with tomato paste, vegetables, Bega cheese and cracked eggs. Bake until eggs are cooked and cheese melted. (20 mins)",
         "Macros: 560 calories, 48g carbs, 42g protein, 24g fats"),
    ],
}

AMY_BREAKFASTS_ROT = {
    1: ("High-Protein Berry Porridge",
        "- 60g Rolled Oats\n- 250ml Unsweetened Almond Milk\n- 1 Scoop Protein Powder\n- 100g Mixed Berries\n- 20g Honey or Maple Syrup\n- 20g Chopped Nuts",
        "Cook oats with almond milk, stir in protein powder when cool. Top with berries, honey and nuts. (8 mins)",
        "Macros: 520 calories, 58g carbs, 32g protein, 16g fats"),
    2: ("Protein French Toast",
        "- 2 Slices Helga's High Protein Bread\n- 2 Eggs\n- 50ml Milk\n- 100g Fresh Berries\n- 20g Maple Syrup\n- 10g Butter",
        "Whisk eggs and milk, dip high protein bread, cook until golden. Serve with berries and syrup. (12 mins)",
        "Macros: 580 calories, 52g carbs, 38g protein, 24g fats"),
}

AMY_SNACKS_ROT = {
    1: ("MuscleNation Chocolate Protein Smoothie",
        "- 250ml Unsweetened Almond Milk\n- 30g MuscleNation Chocolate Protein Powder\n- 1/2 Banana\n- Ice",
        "Blend all ingredients until smooth. (3 mins)",
        "Macros: 280 calories, 24g carbs, 32g protein, 8g fats"),
    2: ("Macro Mike Brownie & Yogurt",
        "- 50g Macro Mike Brownie\n- 75g Vitasoy Yogurt\n- 10g Mixed Nuts",
        "Crumble brownie, mix with yogurt and nuts. (2 mins)",
        "Macros: 320 calories, 28g carbs, 18g protein, 16g fats"),
}

VLAD_CLIENT_DATA = {
    "name": "Vlad",
    "dob": "1985-01-20",
    "sex": "Male",
    "weight_kg": 136.0,
    "height_cm": 183,
    "activity_factor": 1.2,  # Sedentary
    "goal_description": "Body Recomposition - Look good naked and save time",
    "dietary_type": "Vegan",
    "preferred_meals": {
        "breakfasts": ["Soft tacos (tofu/veg)", "8-treasure congee"],
        "lunches": ["Mixed veg pasta", "mixed veg stir-fry"],
        "dinners": ["Burrito bowls", "nourish bowls"],
        "snacks": ["Dark chocolate (80-95%)"]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork"],
    "meal_notes": "Loves spice, variety of plants, fermented foods, strong flavours. Hates baking. Not into sweet. High Protein. Explicit calorie target provided.",
    "target_calories": 3000,  # Middle of 2700-3299 range
    "target_protein_g": 150,
    "workout_time": "Early Morning",
    "training_days": "Monday (high volume), walk to gym when weather permits (just under 1hour), shower, work, walk home. Will invest in walking pad under 120kg.",
    "workout_type": "Pure vanity sarcoplasmic training, V-taper. Squats, deadlifts, crunches.",
    "fasted_morning_routine": "Leave house around 5am after black coffee, fasted walk (maybe ginger powder in water and ACV)",
    "meal_times": {
        "breakfast": "6:30 AM",
        "lunch": "1:00 PM",
        "snack": "4:00 PM",
        "dinner": "7:30 PM"
    }
}

LIBBY_CLIENT_DATA = {
    "name": "Libby",
    "dob": "1986-01-18",
    "sex": "Female",
    "weight_kg": 91.0,
    "height_cm": 172,
    "activity_factor": 1.375,  # Lightly active - light exercise 6-7 days per week
    "goal_description": "Fat Loss - lose another 10-15kg to be more comfortable and confident",
    "dietary_type": "High Protein Vegan",
    "preferred_meals": {
        "breakfasts": ["Easy prep options", "Quick meals"],
        "lunches": ["Salads", "Wraps", "Easy prep"],
        "dinners": ["Stir fry", "Pasta", "Curries"],
        "snacks": ["Simple options"]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork"],
    "meal_notes": "Not fussy at all, loves pretty much everything. Loves meals that are easy to prep - salads, stir frys, pasta, curries, sandwiches, wraps, literally everything.",
    "workout_time": "Monday, Wednesday, Friday or Saturday",
    "training_days": "Monday, Wednesday, Friday or Saturday - following structured program from weight class",
    "workout_type": "Walking, weights (strength training) - Full body, Upper body, Legs rotation program",
    "meal_times": {
        "breakfast": "7:00 AM",
        "lunch": "12:30 PM",
        "snack": "3:00 PM",
        "dinner": "6:30 PM"
    }
}

# Libby's meal rotations - easy prep focus with variety she loves
LIBBY_LUNCHES_MON_WED = {
    1: ("Quick Power Salad Bowl with Protein (Mon–Wed batch)",
        "- 150g Mixed Greens (pre-washed)\n- 120g Chickpeas (canned, drained)\n- 100g Cherry Tomatoes (halved)\n- 80g Cucumber (diced)\n- 60g Avocado (sliced)\n- 30g Sunflower Seeds\n- 40ml Tahini Lemon Dressing",
        "Combine all ingredients in a bowl. Drizzle with dressing. (5 mins prep)",
        "Macros: 520 calories, 45g carbs, 22g protein, 28g fats"),
    2: ("Mediterranean Wrap (Mon–Wed batch)",
        "- 1 Large Wholemeal Tortilla\n- 100g Hummus (high-protein)\n- 120g Roasted Vegetables (capsicum, zucchini, eggplant)\n- 60g Baby Spinach\n- 80g Vegan Feta\n- 30g Sun-dried Tomatoes\n- Fresh Basil",
        "Spread hummus on tortilla, add roasted veg (can prep ahead), spinach, feta, tomatoes, basil. Wrap tightly. (3 mins assembly)",
        "Macros: 540 calories, 52g carbs, 24g protein, 26g fats"),
}

LIBBY_LUNCHES_THU_SAT = {
    1: ("Asian Inspired Noodle Salad (Thu–Sat batch)",
        "- 150g Rice Noodles (cooked, cooled)\n- 120g Edamame (shelled)\n- 100g Shredded Red Cabbage\n- 80g Carrots (julienned)\n- 60g Cucumber (strips)\n- 30g Peanut Butter Dressing\n- 20g Crushed Peanuts\n- Fresh Mint & Coriander",
        "Cook noodles, cool. Combine with prepared veg. Toss with peanut dressing. Garnish with peanuts and herbs. (10 mins active, can prep veg ahead)",
        "Macros: 560 calories, 68g carbs, 26g protein, 22g fats"),
    2: ("Quick Quinoa & Bean Salad (Thu–Sat batch)",
        "- 150g Cooked Quinoa (can use pre-cooked)\n- 120g Black Beans (canned, drained)\n- 100g Corn Kernels\n- 80g Diced Capsicum (red/yellow)\n- 60g Red Onion (finely diced)\n- 30ml Lime Juice & Olive Oil Dressing\n- Fresh Coriander",
        "Mix all ingredients in a bowl. Let marinate 10 mins for flavors to develop. (5 mins prep)",
        "Macros: 530 calories, 78g carbs, 24g protein, 16g fats"),
}

LIBBY_DINNERS_ROT = {
    1: [
        ("Easy Thai-Style Tofu Stir Fry with Rice",
         "- 150g Firm Tofu (cubed)\n- 200g Mixed Stir Fry Vegetables (fresh or frozen)\n- 150g Cooked Brown Rice\n- 60ml Thai Red Curry Paste\n- 100ml Light Coconut Milk\n- 15ml Soy Sauce\n- Fresh Basil & Lime",
         "Pan-fry tofu until golden. Add vegetables, curry paste, coconut milk. Simmer 8 mins. Serve over rice with basil and lime. (15 mins)",
         "Macros: 580 calories, 65g carbs, 28g protein, 24g fats"),
        ("Simple Pasta with Lentil Bolognese",
         "- 120g Wholemeal Pasta (dry)\n- 150g Cooked Red Lentils\n- 200ml Tomato Passata\n- 100g Mushrooms (sliced)\n- 80g Onion (diced)\n- 15g Nutritional Yeast\n- 10ml Olive Oil\n- Fresh Basil",
         "Sauté onion and mushrooms. Add lentils and passata, simmer 10 mins. Cook pasta. Combine and top with nutritional yeast and basil. (20 mins)",
         "Macros: 590 calories, 85g carbs, 30g protein, 18g fats"),
        ("Quick Chickpea Curry with Naan",
         "- 180g Chickpeas (canned, drained)\n- 150ml Light Coconut Milk\n- 100g Baby Spinach\n- 80g Onion (diced)\n- 60ml Korma Curry Sauce\n- 1 Mini Naan Bread\n- Fresh Coriander",
         "Sauté onion, add chickpeas, curry sauce, coconut milk. Simmer 10 mins. Stir in spinach. Serve with warmed naan and coriander. (15 mins)",
         "Macros: 570 calories, 72g carbs, 26g protein, 22g fats"),
    ],
    2: [
        ("Mediterranean Vegetable Pasta",
         "- 120g Wholemeal Pasta (dry)\n- 150g Mediterranean Vegetables (zucchini, capsicum, cherry tomatoes)\n- 80g Vegan Feta (crumbled)\n- 60g Kalamata Olives\n- 30ml Olive Oil\n- Fresh Herbs (basil, oregano)\n- Lemon Zest",
         "Cook pasta. Pan-fry vegetables with olive oil. Combine pasta, veg, feta, olives. Finish with herbs and lemon zest. (18 mins)",
         "Macros: 610 calories, 78g carbs, 24g protein, 28g fats"),
        ("Asian Style Tofu & Vegetable Curry",
         "- 150g Firm Tofu (cubed)\n- 200g Asian Vegetables (bok choy, snow peas, mushrooms)\n- 150g Cooked Jasmine Rice\n- 100ml Light Coconut Milk\n- 30ml Thai Green Curry Paste\n- 15ml Soy Sauce\n- Fresh Thai Basil",
         "Pan-fry tofu. Add vegetables, curry paste, coconut milk, soy sauce. Simmer 12 mins. Serve over rice with Thai basil. (20 mins)",
         "Macros: 595 calories, 62g carbs, 32g protein, 26g fats"),
        ("Quick Bean & Vegetable Chili with Bread",
         "- 150g Mixed Beans (kidney, black, cannellini)\n- 200g Diced Tomatoes (canned)\n- 100g Capsicum & Onion (diced)\n- 80g Corn Kernels\n- 30ml Chili Sauce/Paste\n- 2 Slices Wholegrain Bread\n- Fresh Coriander",
         "Sauté veg, add beans, tomatoes, corn, chili sauce. Simmer 15 mins. Serve with toasted bread and coriander. (20 mins)",
         "Macros: 565 calories, 88g carbs, 28g protein, 12g fats"),
    ],
}

LIBBY_BREAKFASTS_ROT = {
    1: ("Quick Protein Smoothie Bowl (Mon-Wed batch)",
        "- 30g Plant Protein Powder (vanilla)\n- 200ml Unsweetened Soy Milk\n- 100g Frozen Mixed Berries\n- 1/2 Banana (60g)\n- 30g Granola\n- 20g Chia Seeds",
        "Blend protein powder, soy milk, berries, banana until smooth. Pour into bowl, top with granola and chia seeds. (3 mins)",
        "Macros: 480 calories, 52g carbs, 32g protein, 18g fats"),
    2: ("Easy High-Protein Avocado Toast (Thu-Sat batch)",
        "- 2 Slices Helga's High Protein Bread\n- 80g Avocado (mashed)\n- 100g Chickpeas (mashed, seasoned)\n- 30g Cherry Tomatoes (halved)\n- 20g Hemp Seeds\n- Lemon juice, salt, pepper",
        "Toast high protein bread. Mash avocado and seasoned chickpeas. Spread on toast, top with tomatoes and hemp seeds. (5 mins)",
        "Macros: 540 calories, 52g carbs, 34g protein, 26g fats"),
}

LIBBY_SNACKS_ROT = {
    1: ("Apple with Almond Butter",
        "- 1 Large Apple (180g)\n- 25g Almond Butter",
        "Slice apple, serve with almond butter for dipping. (2 mins)",
        "Macros: 280 calories, 35g carbs, 8g protein, 16g fats"),
    2: ("Hummus & Veggie Sticks",
        "- 60g High-Protein Hummus\n- 150g Mixed Vegetable Sticks (carrot, cucumber, capsicum)",
        "Cut vegetables into sticks, serve with hummus. (3 mins prep)",
        "Macros: 220 calories, 25g carbs, 12g protein, 10g fats"),
}

# Vlad's lunch rotations - same lunch for Mon-Wed, then changes Thu-Sat
VLAD_LUNCHES_MON_WED = {
    1: ("High-Protein Chickpea & Tofu Curry (Mon–Wed batch) with Brown Rice",
        "- 120g Chickpeas (canned, drained)\n- 100g Firm Tofu (cubed)\n- 120g Baby Spinach\n- 120g Capsicum & Onion (sliced)\n- 120g Light Coconut Milk\n- 120g Thai Red Curry Paste (spicy)\n- 150g Cooked Brown Rice\n- 5ml Lime Juice\n- Fresh Coriander",
        "Simmer tofu, chickpeas, veg, coconut milk and curry paste for 15 min; stir in spinach. Serve over rice, finish with coriander and lime. (25 minutes)",
        "Macros: 780 calories, 85g carbs, 40g protein, 28g fats"),
    2: ("Spicy Mexican Bean & Quinoa Bowl (Mon–Wed batch)",
        "- 150g Cooked Quinoa\n- 120g Black Beans (canned, drained)\n- 100g Firm Tofu (crumbled, spiced with cumin/paprika)\n- 120g Roasted Corn & Capsicum Salsa\n- 50g Avocado\n- 40g Spicy Salsa\n- Fresh Coriander, Lime Wedge\n- 10ml Olive Oil",
        "Pan-fry spiced tofu until golden. Combine quinoa, beans, corn salsa. Top with tofu, avocado, salsa, coriander and lime. Drizzle with olive oil. (20 minutes)",
        "Macros: 820 calories, 95g carbs, 38g protein, 32g fats"),
}

VLAD_LUNCHES_THU_SAT = {
    1: ("Asian Peanut Tempeh Stir-fry (Thu–Sat batch) with Rice Noodles",
        "- 150g Rice Noodles (cooked)\n- 120g Tempeh (sliced, marinated)\n- 200g Mixed Asian Greens (Bok Choy, Broccoli, Snow Peas)\n- 100g Mushrooms\n- 20g Peanut Butter\n- 15ml Soy Sauce\n- 5ml Sesame Oil\n- Chili flakes, Fresh Ginger\n- Crushed Peanuts for garnish",
        "Marinate and pan-fry tempeh. Stir-fry vegetables. Cook noodles. Whisk peanut butter, soy sauce, sesame oil, chili. Combine all, garnish with peanuts. (25 minutes)",
        "Macros: 760 calories, 78g carbs, 42g protein, 30g fats"),
    2: ("Mediterranean Lentil & Veg Power Bowl (Thu–Sat batch)",
        "- 150g Cooked Green Lentils\n- 120g Roasted Mixed Vegetables (zucchini, capsicum, eggplant)\n- 100g Hummus (high-protein)\n- 80g Vegan Feta Cheese (crumbled)\n- 60g Mixed Greens\n- 20ml Olive Oil & Lemon Dressing\n- Fresh Parsley, Mint\n- 2 Wholemeal Pita Triangles",
        "Roast vegetables. Assemble bowl with lentils, roasted veg, hummus, feta, greens. Dress with olive oil and lemon. Serve with pita. (30 minutes prep, 20 mins if veg pre-roasted)",
        "Macros: 800 calories, 82g carbs, 45g protein, 35g fats"),
}

VLAD_DINNERS_ROT = {
    1: [
        ("High-Protein Lentil Bolognese with Protein Pasta",
         "- 100g Vetta SMART Protein Pasta (dry)\n- 180g Cooked Red Lentils\n- 150g Mushrooms, sliced\n- 250ml Tomato Passata\n- 15g Nutritional Yeast (B12-fortified)\n- 10ml Olive Oil\n- Fresh Basil",
         "Sauté mushrooms in oil, add lentils and passata; simmer 15 min. Toss with pasta, top with nutritional yeast and basil. (20 minutes)",
         "Macros: 700 calories, 80g carbs, 40g protein, 25g fats"),
        ("Spicy Tofu & Black Bean Tacos (3 shells)",
         "- 3 Hard Taco Shells\n- 150g Firm Tofu (crumbled, spiced with taco seasoning)\n- 120g Black Beans (canned, drained)\n- 100g Shredded Lettuce, Diced Tomato, Onion\n- 50g Avocado\n- 40g Spicy Salsa",
         "Season and pan-fry crumbled tofu. Warm beans. Assemble tacos with all ingredients. (18 minutes)",
         "Macros: 720 calories, 85g carbs, 38g protein, 28g fats"),
        ("Indian Inspired Chickpea & Spinach Curry with Brown Rice",
         "- 150g Chickpeas (canned, drained)\n- 200g Baby Spinach\n- 150g Mixed Capsicum & Onion (sliced)\n- 150ml Light Coconut Milk\n- 20g Red Curry Paste (or Vindaloo paste for extra spice)\n- 200g Cooked Brown Rice\n- Fresh Coriander, Lime Wedge",
         "Simmer chickpeas, veg, coconut milk and curry paste for 15 min; stir in spinach. Serve over rice, finish with coriander and lime. (25 minutes)",
         "Macros: 750 calories, 90g carbs, 35g protein, 30g fats"),
    ],
    2: [
        ("Vegan Nourish Bowl with Tempeh & Kimchi",
         "- 180g Cooked Quinoa\n- 150g Tempeh (baked or pan-fried)\n- 200g Mixed Roasted Root Vegetables (sweet potato, carrot, parsnip)\n- 80g Kimchi (fermented cabbage)\n- 20g Tahini-Miso Dressing\n- Fresh Parsley",
         "Roast vegetables. Bake/pan-fry tempeh. Assemble bowl with quinoa, tempeh, roasted veg, kimchi and dressing. (25 minutes, if veg roasted ahead) ",
         "Macros: 700 calories, 80g carbs, 40g protein, 25g fats"),
        ("Spicy Asian Noodle Salad with Tofu & Peanut Dressing",
         "- 150g Rice Noodles (cooked)\n- 150g Firm Tofu (marinated, grilled/fried)\n- 200g Shredded Cabbage, Carrot, Cucumber\n- 30g Peanut Butter + Soy Sauce + Lime Juice + Chili Flakes (dressing)\n- Fresh Mint, Crushed Peanuts",
         "Cook noodles. Grill/fry tofu. Toss noodles, tofu, and veg with dressing. Top with mint and peanuts. (20 minutes)",
         "Macros: 720 calories, 85g carbs, 38g protein, 28g fats"),
        ("Mediterranean Lentil & Vegetable Stew with Wholemeal Bread",
         "- 200g Cooked Green Lentils\n- 250g Mixed Mediterranean Vegetables (zucchini, capsicum, eggplant, tomato)\n- 300ml Vegetable Broth\n- Herbs (oregano, thyme)\n- 2 Slices Wholemeal Sourdough Bread\n- 10ml Olive Oil",
         "Simmer lentils, veg, broth, and herbs until tender. Serve with crusty bread drizzled with olive oil. (30 minutes)",
         "Macros: 750 calories, 90g carbs, 35g protein, 30g fats"),
    ],
}

LINDA_BREAKFASTS_ROT = {
    1: ("High-Protein Vegan Smoothie Bowl (Mon-Wed batch)",
        "- 30g Plant Protein Powder (vanilla)\n- 250ml Fortified Soy Milk (B12)\n- 100g Frozen Mixed Berries\n- 1/2 Banana (60g)\n- 30g Granola\n- 15g Chia Seeds (omega-3)\n- 5g Spirulina (iron)",
        "Blend protein powder, soy milk, berries, banana until smooth. Pour into bowl, top with granola, chia seeds and spirulina. (5 mins)",
        "Macros: 480 calories, 52g carbs, 32g protein, 18g fats"),
    2: ("High-Protein Avocado Toast with Tempeh (Thu-Sat batch)",
        "- 2 Slices Helga's High Protein Bread\n- 80g Avocado (mashed)\n- 80g Tempeh (sliced, pan-fried)\n- 30g Cherry Tomatoes (halved)\n- 15g Hemp Seeds (omega-3)\n- 10g Nutritional Yeast (B12)\n- Lemon juice, salt, pepper",
        "Toast bread. Pan-fry tempeh slices. Mash avocado, spread on toast. Top with tempeh, tomatoes, hemp seeds, nutritional yeast. (8 mins)",
        "Macros: 520 calories, 45g carbs, 34g protein, 26g fats"),
}

LINDA_SNACKS_ROT = {
    1: ("Iron-Rich Trail Mix & Dark Chocolate",
        "- 30g Mixed Nuts & Seeds (pumpkin seeds for iron)\n- 20g Dark Chocolate (70% cocoa)\n- 15g Dried Fruit (no added sugar)",
        "Combine nuts, seeds, chocolate and dried fruit. (1 min)",
        "Macros: 280 calories, 20g carbs, 8g protein, 20g fats"),
    2: ("B12-Fortified Smoothie with Berries",
        "- 200ml Fortified Soy Milk (B12)\n- 100g Mixed Berries\n- 15g Peanut Butter\n- 10g Chia Seeds (omega-3)\n- 5g Nutritional Yeast (B12)",
        "Blend all ingredients until smooth. (3 mins)",
        "Macros: 260 calories, 22g carbs, 12g protein, 16g fats"),
}

VLAD_BREAKFASTS_ROT = {
    1: ("High-Protein Soft Tacos with Spiced Tofu Scramble and Avocado",
        "- 3 Large Wholemeal Tortillas\n- 150g Firm Tofu (crumbled, spiced)\n- 100g Mixed Capsicum & Onion (diced)\n- 50g Avocado (sliced)\n- 40g Salsa (no added sugar)\n- 30g Vegan Cheese (shredded)\n- Fresh Coriander",
        "Sauté veg, scramble tofu with spices. Warm tortillas. Assemble tacos with all toppings. (18 mins)",
        "Macros: 720 calories, 68g carbs, 38g protein, 32g fats"),
    2: ("8-Treasure High-Protein Congee (Savory Rice Porridge)",
        "- 120g Cooked Brown Rice (or leftover)\n- 200ml Vegetable Broth\n- 80g Mixed Mushrooms (sliced)\n- 50g Edamame beans (shelled)\n- 30g Crispy Fried Shallots\n- 15ml Soy Sauce\n- 30g Plant Protein Powder (mixed in)\n- Fresh Ginger (grated), Spring Onion",
        "Simmer rice with broth, mushrooms, edamame until thick. Stir in protein powder. Top with fried shallots, soy sauce, ginger, spring onion. (15 mins)",
        "Macros: 680 calories, 72g carbs, 42g protein, 22g fats"),
}

VLAD_SNACKS_ROT = {
    1: ("Dark Chocolate (80-95%) & Trail Mix Power Snack",
        "- 40g Dark Chocolate (80-95% cocoa)\n- 50g Mixed Nuts & Seeds (almonds, cashews, walnuts, pumpkin seeds)\n- 20g Dried Fruit (no added sugar)",
        "Combine and enjoy mindfully. (2 mins)",
        "Macros: 420 calories, 28g carbs, 12g protein, 32g fats"),
    2: ("High-Protein Vegan Shake with Banana & Nut Butter",
        "- 40g Vegan Protein Powder (unflavoured/neutral)\n- 300ml Unsweetened Soy Milk\n- 1/2 Medium Banana (60g)\n- 20g Almond Butter\n- 10ml Apple Cider Vinegar\n- 1/4 tsp Ginger Powder",
        "Blend all ingredients until smooth and creamy. (3 mins)",
        "Macros: 380 calories, 25g carbs, 35g protein, 18g fats"),
}

SHANE_CLIENT_DATA = {
    "name": "Shane Minahan",
    "dob": "1990-09-12",
    "sex": "Male",
    "weight_kg": 96.0,
    "height_cm": 172,
    "activity_factor": 1.2,  # Sedentary - desk job
    "goal_description": "Fat Loss – target 80–85 kg; happier, healthier; role model for kids",
    "dietary_type": "Balanced (no pork/shellfish)",
    "preferred_meals": {},
    "foods_to_avoid": ["Pork", "Shellfish"],
    "meal_notes": "Full gym access. Prefers strength training. Knees/calves sensitive – avoid heavy squats/lower-leg focus. Flexible training days.",
    "email": "shaneminahan12@hotmail.com",
    "phone": "+61 430 201 191",
}

SHANE_BREAKFASTS_ROT = {
    1: (
        "High-Protein Greek Yogurt Bowl",
        "- 200g Greek Yogurt (low-fat)\n- 30g Whey Protein (vanilla)\n- 80g Mixed Berries\n- 20g Almonds\n- 10g Honey",
        "Whisk protein into yogurt. Top with berries, almonds, and a drizzle of honey.",
        "Macros: 480 calories, 40g carbs, 45g protein, 16g fats",
    ),
    2: (
        "Veggie Omelette on Wholegrain",
        "- 3 Eggs\n- 60g Spinach & Capsicum (chopped)\n- 30g Reduced-Fat Cheese\n- 1 Slice Wholegrain Bread\n- 5ml Olive Oil",
        "Sauté veg in oil, add beaten eggs, cook until set; top with cheese. Serve with toast.",
        "Macros: 520 calories, 34g carbs, 38g protein, 24g fats",
    ),
}

SHANE_LUNCHES_MON_WED = {
    1: (
        "Chicken, Rice & Greens Bowl (Mon–Wed batch)",
        "- 150g Chicken Breast (cooked, sliced)\n- 150g Cooked Jasmine Rice\n- 150g Broccoli (steamed)\n- 15ml Teriyaki or Soy Sauce\n- 5ml Olive Oil",
        "Assemble warm bowl with rice, chicken, broccoli; finish with sauce and oil.",
        "Macros: 610 calories, 64g carbs, 45g protein, 18g fats",
    ),
}

SHANE_LUNCHES_THU_SAT = {
    1: (
        "Beef & Quinoa Power Salad (Thu–Sat batch)",
        "- 140g Lean Beef Strips (grilled)\n- 150g Cooked Quinoa\n- 120g Mixed Salad Veg (tomato, cucumber, capsicum)\n- 30g Feta (optional)\n- 15ml Olive Oil + Lemon",
        "Combine quinoa, veg, sliced beef; dress with olive oil and lemon; add feta if desired.",
        "Macros: 640 calories, 52g carbs, 44g protein, 26g fats",
    ),
}

SHANE_DINNERS_ROT = {
    1: [
        (
            "Lean Beef Stir-Fry with Rice",
            "- 150g Lean Beef Strips\n- 250g Stir-Fry Veg (capsicum, onion, snow peas)\n- 150g Cooked Rice\n- 15ml Stir-Fry Sauce (low sugar)\n- 5ml Sesame Oil",
            "Stir-fry beef and veg on high heat; toss with sauce; serve over rice.",
            "Macros: 700 calories, 78g carbs, 45g protein, 22g fats",
        ),
        (
            "High-Protein Pasta with Tomato & Turkey",
            "- 90g High-Protein Pasta (dry)\n- 150g Lean Turkey Mince\n- 250ml Tomato Passata\n- 100g Mushrooms & Onion\n- 10g Parmesan",
            "Brown turkey with onion/mushrooms; simmer with passata; toss with pasta; top with parmesan.",
            "Macros: 690 calories, 76g carbs, 48g protein, 18g fats",
        ),
        (
            "Grilled Chicken, Sweet Potato & Greens",
            "- 180g Chicken Thigh (trimmed)\n- 250g Sweet Potato (roasted)\n- 150g Green Beans (steamed)\n- 10ml Olive Oil\n- Lemon, Herbs",
            "Grill chicken; roast sweet potato; steam beans; finish with lemon and herbs.",
            "Macros: 720 calories, 62g carbs, 48g protein, 24g fats",
        ),
    ],
}

SHANE_SNACKS_ROT = {
    1: (
        "Protein Shake & Banana",
        "- 300ml Milk (or soy milk)\n- 30g Whey Protein (vanilla/choc)\n- 1 Medium Banana",
        "Blend protein with milk; have banana on the side.",
        "Macros: 340 calories, 46g carbs, 28g protein, 6g fats",
    ),
    2: (
        "Cottage Cheese & Crackers",
        "- 200g Low-Fat Cottage Cheese\n- 4–6 Wholegrain Crackers\n- 1 tsp Chives",
        "Serve cottage cheese with crackers; sprinkle chives.",
        "Macros: 320 calories, 28g carbs, 30g protein, 8g fats",
    ),
}

SABRINA_CLIENT_DATA = {
    "name": "Sabrina Woods",
    "dob": "1999-06-09",
    "sex": "Female",
    "weight_kg": 66.4,
    "height_cm": 168,
    "activity_factor": 1.375,  # Lightly active - light exercise 6-7 days per week
    "goal_description": "Body Recomposition - feel strong and energised, fit comfortably into clothes",
    "dietary_type": "Vegan",
    "target_calories": 1750,  # Adjusted from 1900 calories
    "target_protein_g": 100,  # Maintained for muscle preservation
    "target_carbs_g": 185,    # Energy for pole dancing and gym sessions
    "target_fats_g": 67,      # Hormone support and satiety
    "preferred_meals": {
        "curries": ["African peanut stew", "Indian palak paneer (with tofu)", "Sri Lankan eggplant curry", "Japanese katsu curry"],
        "rice_bowls": ["jasmine rice bowls", "basmati rice bowls", "red rice bowls", "black rice bowls"],
        "salads": ["roasted veggie quinoa salad", "tofu hemp seed salad with fruits"],
        "noodles": ["rice noodle broth", "rice noodle stir fry"],
        "pasta": ["impossible beef bolognese", "cashew cream pasta", "baked tofu pasta"],
        "potatoes": ["roasted potato bowls with veggies and protein"]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork", "brown rice", "cucumber", "raw tomatoes", "raw onion", "lettuce"],
    "meal_notes": "Loves curries, rice bowls (no brown rice), creative salads with roasted veg, rice noodles, pasta dishes, roasted potatoes. Struggles with evening snacking/binging. Prefers nutritionally dense foods like spinach over lettuce. Makes sauces from scratch.",
    "workout_schedule": {
        "monday": "Pole choreography class (evening) + gym",
        "tuesday": "Pole beginners class (evening) + gym",
        "wednesday": "Advanced pole class (evening) - NO gym",
        "thursday": "Pole intermediate class (evening) - busy, no gym",
        "friday": "Gym session",
        "weekend": "Social schedule + morning pole session + 1 gym session"
    },
    "training_details": "1-2 pole sessions + wants 3-4 gym sessions (push/pull/lower split). Prefers slow controlled movements over HIIT.",
    "problem_areas": "Evening binge eating after dinner - needs satisfying meals and controlled snacking strategy"
}

# Master dictionary to map client names to their data and meal rotations
ALL_CLIENT_DATA = {
    "Linda Hayes": LINDA_CLIENT_DATA,
    "Romy": ROMY_CLIENT_DATA,
    "Hannah": HANNAH_CLIENT_DATA,
    "Amy": AMY_CLIENT_DATA,
    "Vlad": VLAD_CLIENT_DATA,
    "Libby": LIBBY_CLIENT_DATA,
    "Shane Minahan": SHANE_CLIENT_DATA,
    # "Sabrina Woods": SABRINA_CLIENT_DATA,  # deactivated per request
}

ALL_CLIENT_MEAL_ROTATIONS = {
    "Linda Hayes": {
        "breakfasts": LINDA_BREAKFASTS_ROT,
        "lunches_mon_wed": LINDA_LUNCHES_MON_WED,
        "lunches_thu_sat": LINDA_LUNCHES_THU_SAT,
        "dinners": LINDA_DINNERS_ROT,
        "snacks": LINDA_SNACKS_ROT,
    },
    "Romy": {
        "breakfasts": ROMY_BREAKFASTS_ROT,
        "lunches_mon_wed": ROMY_LUNCHES_MON_WED,
        "lunches_thu_sat": ROMY_LUNCHES_THU_SAT,
        "dinners": ROMY_DINNERS_ROT,
        "snacks": ROMY_SNACKS_ROT,
    },
    "Hannah": {
        "breakfasts": HANNAH_BREAKFASTS_ROT,
        "lunches_mon_wed": HANNAH_LUNCHES_MON_WED,
        "lunches_thu_sat": HANNAH_LUNCHES_THU_SAT,
        "dinners": HANNAH_DINNERS_ROT,
        "snacks": HANNAH_SNACKS_ROT,
    },
    "Amy": {
        "breakfasts": AMY_BREAKFASTS_ROT,
        "lunches_mon_wed": AMY_LUNCHES_MON_WED,
        "lunches_thu_sat": AMY_LUNCHES_THU_SAT,
        "dinners": AMY_DINNERS_ROT,
        "snacks": AMY_SNACKS_ROT,
    },
    "Vlad": {
        "breakfasts": VLAD_BREAKFASTS_ROT,
        "lunches_mon_wed": VLAD_LUNCHES_MON_WED,
        "lunches_thu_sat": VLAD_LUNCHES_THU_SAT,
        "dinners": VLAD_DINNERS_ROT,
        "snacks": VLAD_SNACKS_ROT,
    },
    "Libby": {
        "breakfasts": LIBBY_BREAKFASTS_ROT,
        "lunches_mon_wed": LIBBY_LUNCHES_MON_WED,
        "lunches_thu_sat": LIBBY_LUNCHES_THU_SAT,
        "dinners": LIBBY_DINNERS_ROT,
        "snacks": LIBBY_SNACKS_ROT,
    },
    "Shane Minahan": {
        "breakfasts": SHANE_BREAKFASTS_ROT,
        "lunches_mon_wed": SHANE_LUNCHES_MON_WED,
        "lunches_thu_sat": SHANE_LUNCHES_THU_SAT,
        "dinners": SHANE_DINNERS_ROT,
        "snacks": SHANE_SNACKS_ROT,
    },
    # "Sabrina Woods": { ... }, # deactivated per request
}

STACI_CLIENT_DATA = {
    "name": "Staci Smythe",
    "dob": "1988-07-11",
    "sex": "Female",
    "weight_kg": 70.0,
    "height_cm": 152.4,
    "activity_factor": 1.55,  # Moderately active
    "goal_description": "Fat Loss to 55 kg – fast, easy vegan meals (minimal cooking)",
    "dietary_type": "Vegan",
    "preferred_meals": {
        "notes": [
            "Loves sweet (chocolate), savoury, spices, coconut cream",
            "Addicted to potatoes (fried/air-fried)",
            "Wants lazy/fast recipes – little to no cooking"
        ]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork", "Shellfish", "Dairy"],
    "meal_notes": "Design for minimal effort: microwave rice, canned beans, air fryer potatoes/tofu, pre-washed greens, jar sauces.",
    "email": "staci.smythe@gmail.com",
    "phone": "+61 413 107 663",
}

STACI_LUNCHES_MON_WED = {
    1: (
        "Loaded Baked Potato Bowl (Mon–Wed batch)",
        "- 300g Microwave-Ready Potato Chunks (or 1 large potato)\n- 120g Black Beans (canned, drained)\n- 60g Corn Kernels (canned)\n- 40g Salsa\n- 30g Avocado\n- 10g Vegan Mayo (optional)\n- Spring Onion, Chili Flakes",
        "Microwave potatoes until tender (5–7 mins). Warm beans and corn (1 min). Bowl up potatoes, top with beans, corn, salsa, avocado, mayo. Finish with spring onion & chili.",
        "Macros: ~520 calories, 78g carbs, 18g protein, 16g fats",
    ),
}

STACI_LUNCHES_THU_SAT = {
    1: (
        "No-Cook Hummus Veg Wrap (Thu–Sat batch)",
        "- 1 Large Wholemeal Tortilla\n- 80g High-Protein Hummus\n- 60g Pre-washed Mixed Greens\n- 80g Roasted Veg (jarred)\n- 30g Pickled Veg/Onion (optional)\n- 10ml Lemon Juice",
        "Spread hummus, layer roasted veg and greens, splash lemon, roll tight. Ready in 2–3 mins.",
        "Macros: ~480 calories, 50g carbs, 18g protein, 20g fats",
    ),
}

STACI_DINNERS_ROT = {
    1: [
        (
            "Air-Fryer Crispy Potato & Tofu Bowl",
            "- 250g Frozen Diced Potato (air-fryer ready)\n- 150g Firm Tofu (cubed)\n- 10ml Olive Oil\n- Garlic Powder, Paprika, Salt\n- 60g Baby Spinach\n- 20g Vegan Garlic Mayo or Tahini",
            "Air-fry potatoes (200°C, 12–15 mins) and tofu (8–10 mins) until crisp. Toss with spinach to wilt. Drizzle mayo/tahini.",
            "Macros: ~560 calories, 60g carbs, 28g protein, 22g fats",
        ),
        (
            "10-Min Peanut Noodles with Tofu",
            "- 120g Rice Noodles (quick-cook)\n- 150g Firm Tofu (pre-cooked or pan-seared)\n- 25g Peanut Butter\n- 15ml Soy Sauce\n- 5ml Lime Juice\n- 5ml Sesame Oil\n- 150g Pre-cut Stir-Fry Veg (bag)",
            "Soak/cook noodles per pack. Warm tofu. Toss noodles, veg and tofu with PB+soy+lime+sesame. Add chili if desired.",
            "Macros: ~590 calories, 72g carbs, 26g protein, 20g fats",
        ),
        (
            "Chickpea Coconut Curry (12 minutes)",
            "- 240g Chickpeas (canned, drained)\n- 150ml Light Coconut Milk\n- 60g Korma/Red Curry Paste (low sugar)\n- 100g Baby Spinach\n- 250g Microwave Jasmine Rice",
            "Simmer chickpeas with coconut milk and curry paste 6–8 mins; stir in spinach to wilt. Serve over microwave rice.",
            "Macros: ~610 calories, 82g carbs, 22g protein, 20g fats",
        ),
    ],
}

STACI_BREAKFASTS_ROT = {
    1: (
        "5-Min Choc Banana Protein Smoothie (Mon–Wed batch)",
        "- 30g Vegan Protein Powder (chocolate)\n- 250ml Soy Milk\n- 1 Banana (frozen ok)\n- 10g Cocoa Powder\n- 15g Peanut Butter\n- Ice",
        "Blend everything until smooth and thick (30–45s).",
        "Macros: ~450 calories, 48g carbs, 32g protein, 14g fats",
    ),
    2: (
        "Coconut Chia Parfait (Thu–Sat batch)",
        "- 250ml Light Coconut Milk\n- 30g Chia Seeds\n- 10g Maple Syrup\n- 100g Frozen Mixed Berries\n- 20g Granola",
        "Stir chia with coconut milk & maple; chill 10+ mins (or overnight). Top with berries and granola.",
        "Macros: ~420 calories, 44g carbs, 14g protein, 18g fats",
    ),
}

STACI_SNACKS_ROT = {
    1: (
        "Dark Chocolate & Nut Mix",
        "- 25g Dark Chocolate (80–95%)\n- 25g Mixed Nuts",
        "Combine and enjoy mindfully.",
        "Macros: ~280 calories, 16g carbs, 6g protein, 20g fats",
    ),
    2: (
        "2-Min Protein Yogurt Cup",
        "- 150g Soy Yogurt (unsweetened)\n- 20g Plant Protein Powder (vanilla/choc)\n- 10g Maple Syrup\n- 10g Granola",
        "Whisk protein into yogurt, sweeten, top with granola.",
        "Macros: ~240 calories, 22g carbs, 22g protein, 6g fats",
    ),
}

ALL_CLIENT_DATA.update({
    "Staci Smythe": STACI_CLIENT_DATA,
})

ALL_CLIENT_MEAL_ROTATIONS.update({
    "Staci Smythe": {
        "breakfasts": STACI_BREAKFASTS_ROT,
        "lunches_mon_wed": STACI_LUNCHES_MON_WED,
        "lunches_thu_sat": STACI_LUNCHES_THU_SAT,
        "dinners": STACI_DINNERS_ROT,
        "snacks": STACI_SNACKS_ROT,
    }
})

DANA_CLIENT_DATA = {
    "name": "Dana Aflamina",
    "dob": "1969-05-08",
    "sex": "Female",
    "weight_kg": 58.0,
    "height_cm": 158.0,
    "activity_factor": 1.375,  # Lightly active
    "goal_description": "Fat Loss to 50 kg – hearty vegan bowls (low rice preference)",
    "dietary_type": "Vegan",
    "preferred_meals": {
        "likes": [
            "Dahls", "Japanese curries", "Soups", "Stir fry", "Buddha bowls",
            "Stuffed sweet potato", "Juices", "Chickpeas", "Lentils", "Beans"
        ],
        "dislikes": [
            "Uncooked tomato", "Celery", "Cucumbers", "Coriander", "Plain salads"
        ],
        "notes": [
            "Prefers cooked veg; salads only when loaded with cooked veg",
            "Doesn't like eating a lot of rice – brown rice when used"
        ]
    },
    "foods_to_avoid": ["Fish", "Eggs", "Pork", "Shellfish", "Dairy"],
    "meal_notes": "Use quinoa, sweet potato, lentils/beans; minimal rice; avoid raw tomato/celery/cucumber/coriander.",
    "email": "dana.aflamina@outlook.com.au",
    "phone": "+61 417 554 595",
    "target_calories": 1100,
    "target_protein_g": 80,
}

DANA_LUNCHES_MON_WED = {
    1: (
        "Roasted Veg & Lentil Quinoa Bowl (Mon–Wed batch)",
        "- 100g Cooked Quinoa\n- 120g Cooked Brown/Green Lentils\n- 200g Roasted Veg (pumpkin, zucchini, capsicum, onion)\n- 10g Tahini-Lemon Dressing\n- Parsley (optional)",
        "Roast veg in batch (200°C, ~20 mins). Warm quinoa and lentils. Toss with a light tahini-lemon dressing.",
        "Macros: ~350 calories, 45g carbs, 18g protein, 9g fats",
    ),
}

DANA_LUNCHES_THU_SAT = {
    1: (
        "Stuffed Sweet Potato with Chickpeas & Greens (Thu–Sat batch)",
        "- 1 Small-Medium Sweet Potato (200g)\n- 120g Chickpeas (canned, drained)\n- 80g Baby Spinach (wilted)\n- 10g Tahini + Lemon + Water (drizzle)\n- Smoked Paprika",
        "Microwave or bake sweet potato until soft. Warm chickpeas. Wilt spinach in the heat. Split potato, stuff with chickpeas & spinach, drizzle tahini-lemon.",
        "Macros: ~360 calories, 55g carbs, 14g protein, 8g fats",
    ),
}

DANA_DINNERS_ROT = {
    1: [
        (
            "Red Lentil Dahl with Greens (no rice)",
            "- 150g Cooked Red Lentils (dahl)\n- 200g Cooked Veg (spinach, carrot, onion)\n- 80ml Light Coconut Milk\n- Curry spices",
            "Simmer lentils with spices and light coconut milk 10–12 mins. Stir in veg. Serve with extra greens (no rice).",
            "Macros: ~350 calories, 45g carbs, 18g protein, 9g fats",
        ),
        (
            "Japanese Vegetable Curry (no rice)",
            "- 250g Mixed Cooked Veg (carrot, potato, eggplant, onion)\n- 120ml Japanese Curry Sauce (block or paste)\n- 5ml Soy Sauce",
            "Simmer veg in curry sauce until tender (10–12 mins). Serve on its own or with extra veg (no rice).",
            "Macros: ~300 calories, 42g carbs, 8g protein, 9g fats",
        ),
        (
            "Ginger-Garlic Veg Stir-Fry with Soba",
            "- 80g Buckwheat Soba (cooked)\n- 150g Mixed Stir-Fry Veg (broccoli, beans, capsicum)\n- 100g Tofu or Edamame\n- 10ml Soy Sauce\n- 5ml Sesame Oil\n- Fresh Ginger & Garlic",
            "Stir-fry veg with ginger/garlic, add tofu/edamame. Toss with soba, soy and sesame oil.",
            "Macros: ~320 calories, 35g carbs, 20g protein, 9g fats",
        ),
    ],
}

DANA_BREAKFASTS_ROT = {
    1: (
        "Protein Chia Parfait with Berries (Mon–Wed batch)",
        "- 250ml Soy Milk\n- 30g Chia Seeds\n- 15g Plant Protein Powder (vanilla)\n- 100g Mixed Berries\n- 10g Maple Syrup\n- 10g Granola (optional)",
        "Stir chia and protein into soy milk; chill 10+ mins (or overnight). Top with berries and a little maple; sprinkle granola if desired.",
        "Macros: ~260 calories, 28g carbs, 16g protein, 9g fats",
    ),
    2: (
        "Savory Miso Tofu on Wholegrain (Thu–Sat batch)",
        "- 1 Slice Wholegrain Bread\n- 100g Firm Tofu (crumbled)\n- 10g Miso + 5ml Soy Sauce + Garlic Powder\n- 5g Avocado (optional)",
        "Scramble tofu with miso/soy/garlic. Toast bread; top with tofu scramble (add a tiny smear of avocado if desired).",
        "Macros: ~260 calories, 24g carbs, 21g protein, 6g fats",
    ),
}

DANA_SNACKS_ROT = {
    1: (
        "Small Juice & Nuts",
        "- 150ml Fresh Juice (carrot-apple-ginger)\n- 10g Mixed Nuts",
        "Have juice with a small portion of nuts for balance.",
        "Macros: ~120 calories, 16g carbs, 3g protein, 6g fats",
    ),
    2: (
        "Light Protein Yogurt Cup",
        "- 120g Soy Yogurt (unsweetened)\n- 10g Plant Protein Powder\n- 2g Maple Syrup",
        "Stir protein into yogurt; lightly sweeten.",
        "Macros: ~120 calories, 8g carbs, 12g protein, 3g fats",
    ),
}

# Register Dana
ALL_CLIENT_DATA.update({
    "Dana Aflamina": DANA_CLIENT_DATA,
})

ALL_CLIENT_MEAL_ROTATIONS.update({
    "Dana Aflamina": {
        "breakfasts": DANA_BREAKFASTS_ROT,
        "lunches_mon_wed": DANA_LUNCHES_MON_WED,
        "lunches_thu_sat": DANA_LUNCHES_THU_SAT,
        "dinners": DANA_DINNERS_ROT,
        "snacks": DANA_SNACKS_ROT,
    }
})
