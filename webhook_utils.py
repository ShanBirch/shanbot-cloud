from typing import Dict

def calculate_targets(onboarding: Dict) -> Dict:
    # Very rough calc: 30 * weight if present; else 2k
    try:
        w = int(onboarding.get('weight_kg') or 70)
        cals = max(1400, min(3500, w * 30))
    except Exception:
        cals = 2000
    return {"target_calories": cals}
