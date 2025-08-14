import logging, json
from typing import Dict, Optional

logger = logging.getLogger("dashboard_sqlite_utils_stub")

# very lightweight in-memory store for cloud runtime
__USER_TARGETS: Dict[str, Dict] = {}
__USER_METRICS: Dict[str, Dict] = {}

# Queue stubs

def add_response_to_review_queue(**kwargs):
    logger.info("[stub] add_response_to_review_queue: %s", list(kwargs.keys()))
    return 1

def add_message_to_history(**kwargs):
    logger.info("[stub] add_message_to_history")
    return None

# Nutrition targets/profile

def get_nutrition_targets(ig_username: str) -> Dict:
    return __USER_TARGETS.get(ig_username) or {}

def upsert_nutrition_targets(ig_username: str, targets: Dict) -> None:
    __USER_TARGETS[ig_username] = dict(targets or {})

# Calorie tracking summaries

def log_meal_and_update_calorie_tracking(**kwargs) -> None:
    logger.info("[stub] log_meal_and_update_calorie_tracking")


def get_calorie_summary_text(ig_username: str) -> str:
    t = get_nutrition_targets(ig_username) or {}
    cals = t.get("target_calories") or 2000
    return f"Daily target: {cals} cals"

# Metrics JSON helpers

def get_user_metrics_json(ig_username: str) -> Dict:
    return __USER_METRICS.get(ig_username, {}).copy()


def set_user_metrics_json_field(ig_username: str, key: str, value) -> None:
    m = __USER_METRICS.setdefault(ig_username, {})
    m[key] = value

# Flow flags/profile

def user_has_nutrition_profile(ig_username: str) -> bool:
    return bool(__USER_METRICS.get(ig_username, {}).get("nutrition_profile"))


def upsert_user_nutrition_profile(ig_username: str, **profile) -> None:
    m = __USER_METRICS.setdefault(ig_username, {})
    m["nutrition_profile"] = profile


def set_user_in_calorie_flow(ig_username: str, in_flow: bool) -> None:
    m = __USER_METRICS.setdefault(ig_username, {})
    m["in_calorie_flow"] = bool(in_flow)


def is_user_in_calorie_flow(ig_username: str) -> bool:
    return bool(__USER_METRICS.get(ig_username, {}).get("in_calorie_flow"))

# Misc stubs used defensively

def reset_daily_calorie_tracking_if_new_day(ig_username: str) -> None:
    return None


def rename_last_meal(ig_username: str, new_name: str) -> bool:
    return True

# DB connection stub used only for very specific SELECT/UPDATE of metrics_json; emulate minimally
class _Cursor:
    def __init__(self, user: str):
        self.user = user
        self._row = None
    def execute(self, sql: str, params: tuple = ()):  # noqa: ANN001
        sql_low = (sql or "").lower()
        if "select metrics_json from users" in sql_low:
            data = __USER_METRICS.get(self.user, {}).copy()
            self._row = (json.dumps(data),)
        elif "update users set metrics_json" in sql_low and params:
            try:
                metrics_json, user = params
                if isinstance(metrics_json, str):
                    __USER_METRICS[user] = json.loads(metrics_json)
            except Exception:  # pragma: no cover
                pass
        else:
            self._row = None
    def fetchone(self):
        return self._row

class _Conn:
    def __init__(self, user: str):
        self.user = user
        self._cur = _Cursor(user)
    def cursor(self):
        return self._cur
    def commit(self):
        return None
    def close(self):
        return None

# Factory returns a connection bound to the last user requested via SELECT/UPDATE; fallback to generic

def get_db_connection(ig_username: Optional[str] = None):
    return _Conn(ig_username or "default")
