import os
import hashlib
from io import BytesIO
from datetime import date, datetime
import base64
import random
import re as _re
# import logging # Remove logging import
from typing import List, Optional

# Configure basic logging (optional, keep commented for cleaner output normally)
# logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def calculate_age(dob_str: str) -> int:
    y, m, d = map(int, dob_str.split('-'))
    born = date(y, m, d)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def calculate_targets_by_sex(sex: str, weight_kg: float, height_cm: float, age: int, activity: float = 1.375, deficit_kcal: int = 500, target_calories: int = None, target_protein_g: int = None):
    if target_calories is not None and target_protein_g is not None:
        # Use explicit targets if provided
        protein_kcal = target_protein_g * 4
        fat_kcal = int(round(target_calories * 0.30))
        fat_g = int(round(fat_kcal / 9))
        carbs_kcal = target_calories - protein_kcal - fat_kcal
        carbs_g = max(0, int(round(carbs_kcal / 4)))
        return target_calories, target_protein_g, carbs_g, fat_g

    # Existing calculation logic if no explicit targets
    if sex.lower() == "female":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    elif sex.lower() == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        raise ValueError("Sex must be 'male' or 'female'")

    tdee = bmr * activity
    target_cal = max(1100, int(round(tdee - deficit_kcal)))

    protein_g = int(round(weight_kg * 1.7))
    protein_kcal = protein_g * 4

    fat_kcal = int(round(target_cal * 0.30))
    fat_g = int(round(fat_kcal / 9))

    carbs_kcal = target_cal - protein_kcal - fat_kcal
    carbs_g = max(0, int(round(carbs_kcal / 4)))
    return target_cal, protein_g, carbs_g, fat_g


def enrich_preparation_text(raw_prep: str, ingredients: List[str]) -> str:
    """
    Convert short, generic prep notes into clearer, step-by-step instructions.

    Heuristics only (no AI):
    - Split into actions, add sequencing and approximate times
    - If rice/noodles mentioned, add cues to cook/reheat properly
    - If tofu appears, suggest pressing/pan-searing for texture
    - Add leftover/reheat tip when sauces are used
    """
    text = raw_prep.strip()

    lower = text.lower()
    steps: List[str] = []

    # Aromatics/sauté baseline
    if any(k in lower for k in ["sauté", "saute", "stir-fry", "stir fry", "simmer", "bake", "blend"]):
        # Keep original but add timing when missing
        steps.append(text.rstrip('.'))
    else:
        steps.append(text.rstrip('.'))

    # Tofu handling
    if any("tofu" in i.lower() for i in ingredients):
        steps.append(
            "For best texture, pat tofu dry and pan-sear 3–4 mins per side before saucing.")

    # Rice/noodle handling
    if any(x in "\n".join(ingredients).lower() for x in ["rice", "noodle", "pasta", "quinoa"]):
        steps.append(
            "If using pre-cooked grains/noodles, reheat with a splash of water to loosen (1–2 mins).")

    # Sauce dishes tip
    if any(x in lower for x in ["sauce", "curry", "coconut milk", "broth"]):
        steps.append(
            "Simmer gently until the sauce thickens and flavours meld (5–8 mins).")
        steps.append(
            "Leftovers: Reheat next day with a splash of water to restore consistency.")

    # Join as one sentence for ReportLab paragraph
    return " ".join(step for step in steps if step)


def normalize_ingredients_for_cache(ingredients_text: str) -> str:
    """
    Normalize ingredients to ensure consistent cache keys regardless of order.
    This ensures the same meal with differently ordered ingredients gets the same photo.
    """
    if not ingredients_text:
        return ""

    # Split into lines and clean each one
    lines = ingredients_text.strip().split('\n')
    normalized_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove leading dashes, bullets, or numbers
        line = _re.sub(r'^[-•*\d+.\s]+', '', line)

        # Normalize measurement units
        line = _re.sub(r'\bgrams?\b', 'g', line, flags=_re.IGNORECASE)
        line = _re.sub(r'\bkilograms?\b', 'kg', line, flags=_re.IGNORECASE)
        line = _re.sub(r'\bmillilitres?\b', 'ml', line, flags=_re.IGNORECASE)
        line = _re.sub(r'\blitres?\b', 'l', line, flags=_re.IGNORECASE)
        line = _re.sub(r'\btablespoons?\b', 'tbsp', line, flags=_re.IGNORECASE)
        line = _re.sub(r'\bteaspoons?\b', 'tsp', line, flags=_re.IGNORECASE)

        # Remove "optional" markers from cache key (but keep in display)
        line_for_cache = _re.sub(
            r'\s*\(optional\)', '', line, flags=_re.IGNORECASE)

        # Normalize whitespace
        line_for_cache = ' '.join(line_for_cache.split())

        if line_for_cache:
            normalized_lines.append(line_for_cache.lower())

    # Sort lines alphabetically for consistent ordering
    normalized_lines.sort()

    return '\n'.join(normalized_lines)


def normalize_meal_name_for_cache(meal_name: str) -> str:
    """
    Normalize meal name for consistent cache keys.
    """
    if not meal_name:
        return ""

    # Convert to lowercase
    name = meal_name.lower()

    # Remove extra whitespace
    name = ' '.join(name.split())

    # Standardize common variations
    name = _re.sub(r'\bbowl\b', 'bowl', name)
    name = _re.sub(r'\bsmoothie bowl\b', 'smoothie bowl', name)
    name = _re.sub(r'\bbuddha bowl\b', 'bowl', name)
    name = _re.sub(r'\bpower bowl\b', 'bowl', name)
    name = _re.sub(r'\bnourish bowl\b', 'bowl', name)

    return name


def _meal_image_key(meal_name: str, ingredients_text: str, macros_text: str = "", style_tag: str = "v8_photoreal_normalized") -> str:
    """
    Generate a consistent cache key with normalized inputs.
    Now handles ingredient order independence and meal name variations.
    """
    normalized_name = normalize_meal_name_for_cache(meal_name)
    normalized_ingredients = normalize_ingredients_for_cache(ingredients_text)

    # Keep macros as-is since they're usually consistent
    data = f"{normalized_name}|{normalized_ingredients}|{macros_text}|{style_tag}".encode(
        "utf-8")
    return hashlib.sha1(data).hexdigest()[:16]


def maybe_generate_meal_image(meal_name: str, ingredients_text: str, preparation_text: str, out_dir: str, macros_text: str = "") -> Optional[str]:
    """
    Best-effort image generation. Returns image path if available, else None.
    - Controlled by env var ENABLE_MEAL_IMAGES in {"1","true","yes"}
    - Requires GOOGLE_API_KEY and google-generativeai package installed
    - Caches images by meal+ingredients hash
    """
    enabled = str(os.getenv("ENABLE_MEAL_IMAGES", "")
                  ).lower() in {"1", "true", "yes"}
    if not enabled:
        return None

    # Skip image generation for vague or placeholder meal names
    if meal_name in ["—", "Flexible Choice within Guidelines", "Generic Breakfast", "Generic Lunch", "Generic Snack", "Generic Dinner"] or not meal_name.strip():
        return None

    os.makedirs(out_dir, exist_ok=True)
    # Choose vessel and camera angle styling based on meal type
    name_low = meal_name.lower()
    ing_low = (ingredients_text or "").lower()
    is_smoothie_bowl = ("smoothie bowl" in name_low) or (
        "bowl" in name_low and ("smoothie" in name_low or "acai" in name_low))
    # Drinks should be detected by name ONLY to avoid false positives from ingredients (e.g., "lime juice").
    drink_name_tokens = [
        "smoothie", "shake", "juice", "latte", "mocktail", "iced coffee", "iced tea", "ade", "lemonade", "milkshake", "tea", "coffee"
    ]
    not_food_tokens = [
        "bowl", "curry", "soup", "stir-fry", "stir fry", "pasta", "salad", "taco", "wrap", "rice", "noodle", "toast", "oat", "porridge", "pizza"
    ]
    is_glass_drink = (
        (not is_smoothie_bowl)
        and any(tok in name_low for tok in drink_name_tokens)
        and not any(ft in name_low for ft in not_food_tokens)
    )
    if is_glass_drink:
        style_tag = "v8_drink_glass_side"
    elif is_smoothie_bowl:
        style_tag = "v8_bowl_overhead"
    else:
        style_tag = "v8_food_overhead_plate"

    key = _meal_image_key(meal_name, ingredients_text,
                          macros_text=macros_text, style_tag=style_tag)
    dest_path = os.path.join(out_dir, f"{key}.jpg")
    rng = random.Random(int(key, 16))
    # Short-circuit on cache regardless; images do not include overlays now
    if os.path.exists(dest_path):
        return dest_path

    # Legacy cache fallback only when API key is NOT available (handled later)

    api_key = _get_genai_api_key()
    if not api_key:
        # Only when API is unavailable, allow reusing any legacy cached images
        legacy_keys = [
            _meal_image_key(meal_name, ingredients_text,
                            macros_text=macros_text, style_tag="v2_overhead_label"),
            _meal_image_key(meal_name, ingredients_text,
                            macros_text=macros_text, style_tag="v3_name_label_only"),
            _meal_image_key(meal_name, ingredients_text,
                            macros_text="", style_tag="v4_overhead_clean"),
        ]
        for legacy_key in legacy_keys:
            legacy_path = os.path.join(out_dir, f"{legacy_key}.jpg")
            if os.path.exists(legacy_path):
                return legacy_path
        return None

    try:
        # Photorealistic food photography prompt with exact ingredients/amounts (no labels)
        # Photorealistic food photography prompt with realism cues and randomized angles
        # Decide camera angle deterministically per meal
        angle_choice = "overhead"
        if is_glass_drink:
            angle_choice = "side"  # Always for glass drinks
        elif is_smoothie_bowl:
            angle_choice = "overhead" if rng.random() < 0.7 else rng.choice([
                "45-degree", "close-up"])
        else:
            angle_choice = rng.choice(["overhead", "45-degree", "close-up"])

        if angle_choice == "side":
            header_line = f"Photorealistic side-view food photo of {meal_name}."
            angle_line = "Camera angle: natural side view (3/4), not overhead; show full glass height and contents."
        elif angle_choice == "overhead":
            header_line = f"Photorealistic overhead (top-down 90°) food photo of {meal_name}."
            angle_line = "Camera angle: overhead (top-down 90°)."
        elif angle_choice == "45-degree":
            header_line = f"Photorealistic three-quarter (45°) food photo of {meal_name}."
            angle_line = "Camera angle: 45° three-quarter view."
        else:
            header_line = f"Photorealistic close-up food photo of {meal_name}."
            angle_line = "Camera angle: 30° close-up with shallow depth of field."

        vessel_line = (
            "Serve in a tall clear glass; transparent sides visible; set on a natural surface (wood or marble) with minimal props (linen napkin)."
            if is_glass_drink else
            ("Serve in a ceramic bowl (for smoothie bowls) on a natural surface with minimal tasteful props (linen napkin, spoon)."
             if is_smoothie_bowl else
             "Serve on a ceramic plate or shallow bowl on a natural surface with believable cutlery; avoid perfect symmetry.")
        )

        aspect_line = "Aspect: 3:2 or 4:3, natural composition; preserve aspect ratio."
        realism_lines = [
            "Natural daylight (window light), soft realistic shadows, true-to-life colors.",
            "Shallow depth of field where appropriate (background softly out of focus).",
            "Imperfect plating, a few realistic crumbs/smears; subtle steam/condensation when warm.",
            "Light table clutter: linen napkin, fork/spoon; no excessive props.",
            "No text, no labels, no borders, no watermarks, no hands, no logos."
        ]

        prompt_parts = [
            header_line,
            angle_line,
            aspect_line,
            "Ingredients and approximate amounts to depict:",
            ingredients_text,
            vessel_line,
            *realism_lines,
            "Food magazine quality, high dynamic range, crisp detail."
        ]
        prompt = "\n".join(prompt_parts)

        image_bytes = None
        candidate_images: List[bytes] = []
        num_variants = 3

        # Path A: new google-genai client
        try:
            # logging.info("Trying new google-genai client (Path A).") # Comment out logging
            from google import genai as new_genai  # type: ignore
            from google.genai import types as new_genai_types  # type: ignore
            client = new_genai.Client(api_key=api_key)  # type: ignore
            # Try likely image models
            for model_name in [
                "gemini-2.0-flash-preview-image-generation",  # Working Gemini 2.5 Flash
                "imagen-3.0-generate-001",  # Fallback: Imagen for photorealism
                "gemini-2.5-flash-image-preview",  # Fallback: other Gemini models
            ]:
                try:
                    # logging.info(f"Path A: Calling model '{model_name}' for '{meal_name}'") # Comment out logging
                    if model_name in ["gemini-2.5-flash-image-preview", "gemini-2.0-flash-preview-image-generation"]:
                        # Use candidate_count=1 for image generation models that don't support multiple candidates
                        candidates_to_request = 1 if model_name == "gemini-2.0-flash-preview-image-generation" else num_variants
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=[prompt],
                            config=new_genai_types.GenerateContentConfig(
                                response_modalities=[
                                    new_genai_types.Modality.IMAGE,
                                    new_genai_types.Modality.TEXT],
                                candidate_count=candidates_to_request,
                            )
                        )
                        if resp.candidates:
                            for cand in resp.candidates:
                                if cand.content and cand.content.parts:
                                    for part in cand.content.parts:
                                        if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                                            candidate_images.append(
                                                part.inline_data.data)
                        else:
                            # logging.warning(f"Path A: Model {model_name} generate_content did not return candidates/content/parts. Response: {resp}") # Comment out logging
                            pass
                    elif hasattr(client, "images") and hasattr(client.images, "generate"):
                        for _ in range(num_variants):
                            resp = client.images.generate(
                                model=model_name, prompt=prompt)  # type: ignore
                            if hasattr(resp, "images") and len(resp.images) > 0:
                                img = resp.images[0]
                                if hasattr(img, "image_bytes") and img.image_bytes:
                                    candidate_images.append(img.image_bytes)
                                elif hasattr(img, "data") and img.data:
                                    candidate_images.append(img.data)
                    else:
                        # logging.warning(f"Path A: client.images.generate not available for this client/model.") # Comment out logging
                        pass
                    if candidate_images:
                        break
                except Exception as e:
                    # logging.error(f"Path A - Error with model {model_name}: {e}") # Comment out logging
                    pass  # Suppress error logging for now
                    continue
        except Exception as e:
            # logging.error(f"Path A - Client initialization/import error: {e}") # Comment out logging
            pass

        # Select best candidate from collected images
        if candidate_images and not image_bytes:
            # For now, just select the first candidate
            # TODO: Implement more sophisticated selection criteria
            image_bytes = candidate_images[0]

        # Path B: legacy google-generativeai client
        if image_bytes is None:
            # logging.info("Trying legacy google-generativeai client (Path B).") # Comment out logging
            try:
                import google.generativeai as old_genai  # type: ignore
                old_genai.configure(api_key=api_key)
                for m in [
                    "imagen-3.0",
                    "gemini-2.5-flash-image-preview",
                    "gemini-2.0-flash-image",
                ]:
                    try:
                        # logging.info(f"Path B: Calling model '{m}' for '{meal_name}'") # Comment out logging
                        # Initialize model once per iteration
                        model = old_genai.GenerativeModel(m)
                        if m == "gemini-2.5-flash-image-preview":
                            resp = model.generate_content(contents=[prompt])
                            if resp.candidates and len(resp.candidates) > 0 and resp.candidates[0].content and resp.candidates[0].content.parts:
                                for part in resp.candidates[0].content.parts:
                                    if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                                        image_bytes = part.inline_data.data
                                        # logging.info(f"Path B: Successfully got data from {m} using generate_content") # Comment out logging
                                        break
                                if not image_bytes:
                                    # logging.warning(f"Path B: Model {m} generate_content returned content, but no inline_data.data found. Response parts: {[dir(p) for p in resp.candidates[0].content.parts]}") # Comment out logging
                                    pass
                            else:
                                # logging.warning(f"Path B: Model {m} generate_content did not return candidates/content/parts. Response: {resp}") # Comment out logging
                                pass
                        elif hasattr(model, "generate_image"):
                            r = model.generate_image(prompt=prompt)
                            if hasattr(r, "image") and len(r.image) > 0 and hasattr(r.image[0], "data"):
                                image_bytes = r.image[0].data
                                # logging.info(f"Path B: Successfully got data from {m}") # Comment out logging
                            else:
                                # logging.warning(f"Path B: Model {m} returned image, but no data found on image object. Image object attributes: {dir(r.image[0])}") # Comment out logging
                                pass
                        elif hasattr(model, "generate_images"):
                            r = model.generate_images(prompt=prompt)
                            if hasattr(r, "images") and len(r.images) > 0 and hasattr(r.images[0], "_image_bytes"):
                                image_bytes = r.images[0]._image_bytes
                                # logging.info(f"Path B: Successfully got _image_bytes from {m}") # Comment out logging
                            else:
                                # logging.warning(f"Path B: Model {m} returned images, but no _image_bytes found on image object. Image object attributes: {dir(r.images[0])}") # Comment out logging
                                pass
                        else:
                            # logging.warning(f"Path B: Model {m} does not have generate_image or generate_images method.") # Comment out logging
                            pass
                        if image_bytes:
                            break
                    except Exception as e:
                        # logging.error(f"Path B - Error with model {m}: {e}") # Comment out logging
                        pass  # Suppress error logging for now
                        continue
            except Exception as e:
                # logging.error(f"Path B - Client initialization/import error: {e}") # Comment out logging
                pass

        if not image_bytes:
            # logging.warning(f"Failed to retrieve image bytes for '{meal_name}'.") # Comment out logging
            return None

        # Recompress and resize image to reduce PDF size
        try:
            from PIL import Image as PILImage, ImageEnhance, ImageFilter, ImageChops  # type: ignore
            # Some Google APIs return base64-encoded strings; decode when needed
            if isinstance(image_bytes, str):
                try:
                    image_bytes = base64.b64decode(image_bytes)
                except Exception:
                    # leave as-is if decode fails
                    pass
            img = PILImage.open(BytesIO(image_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            max_px = 1400  # cap longest side
            img.thumbnail((max_px, max_px), PILImage.LANCZOS)
            # Subtle film grain
            try:
                w, h = img.size
                noise = PILImage.effect_noise((w, h), rms=3.5).convert("L")
                noise = noise.point(lambda p: int(p * 0.25))
                r, g, b = img.split()
                r = ImageChops.add(r, noise, scale=1.0, offset=0)
                g = ImageChops.add(g, noise, scale=1.0, offset=0)
                b = ImageChops.add(b, noise, scale=1.0, offset=0)
                img = PILImage.merge("RGB", (r, g, b))
            except Exception:
                pass

            # Mild vignette
            try:
                w, h = img.size
                vignette = PILImage.new('L', (w, h), 0)
                px = vignette.load()
                for y in range(h):
                    for x in range(w):
                        dx = (x - w / 2) / (w / 2)
                        dy = (y - h / 2) / (h / 2)
                        d = (dx*dx + dy*dy) ** 0.5
                        px[x, y] = int(max(0, min(255, 255 * (d - 0.6) / 0.8)))
                vignette = vignette.filter(ImageFilter.GaussianBlur(radius=20))
                darkened = img.point(lambda p: int(p * 0.98))
                img = PILImage.composite(darkened, img, vignette)
            except Exception:
                pass

            # Subtle chromatic aberration (1px channel offsets)
            try:
                r, g, b = img.split()
                r = ImageChops.offset(r, 1, 0)
                b = ImageChops.offset(b, -1, 0)
                img = PILImage.merge("RGB", (r, g, b))
            except Exception:
                pass

            # Slight white balance variance
            try:
                img = ImageEnhance.Color(img).enhance(1.02)
            except Exception:
                pass

            # Progressive JPEG with natural compression; try adding camera-like EXIF if available
            exif_bytes = None
            try:
                import piexif  # type: ignore
                zeroth_ifd = {
                    piexif.ImageIFD.Make: u"Canon",
                    piexif.ImageIFD.Model: u"EOS 5D Mark IV",
                    piexif.ImageIFD.Software: u"Adobe Lightroom",
                }
                exif_ifd = {
                    piexif.ExifIFD.DateTimeOriginal: datetime.utcnow().strftime("%Y:%m:%d %H:%M:%S"),
                    piexif.ExifIFD.LensModel: u"EF 50mm f/1.8 STM",
                    piexif.ExifIFD.FNumber: (28, 10),
                    piexif.ExifIFD.ExposureTime: (1, 125),
                    piexif.ExifIFD.ISOSpeedRatings: 200,
                }
                exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd}
                exif_bytes = piexif.dump(exif_dict)
            except Exception:
                exif_bytes = None

            save_kwargs = {"format": "JPEG", "quality": 78,
                           "optimize": True, "progressive": True}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(dest_path, **save_kwargs)
        except Exception:
            # Fallback to raw write if Pillow not available
            try:
                if isinstance(image_bytes, str):
                    image_bytes = base64.b64decode(image_bytes)
                with open(dest_path, "wb") as f:
                    f.write(image_bytes)
            except Exception:
                return None
        # logging.info(f"Successfully generated and saved image to {dest_path}") # Comment out logging
        return dest_path
    except Exception as outer_e:
        # logging.critical(f"Critical error in maybe_generate_meal_image: {outer_e}") # Comment out logging
        return None


def _get_genai_api_key() -> Optional[str]:
    for key_name in (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_GENAI_API_KEY",
        "GENAI_API_KEY",
    ):
        val = os.getenv(key_name)
        if val:
            return val
    return None
