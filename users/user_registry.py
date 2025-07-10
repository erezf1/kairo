# users/user_registry.py
import json
import os
from typing import Dict, Any

from tools.logger import log_info, log_error

USER_REGISTRY_PATH = os.path.join("data", "users", f"registry{os.getenv('DATA_SUFFIX', '')}.json")

_registry: Dict[str, Dict[str, Any]] = {}

DEFAULT_PREFERENCES = {
    "name": "friend",
    "timezone": None,
    "language": "en",
    "morning_muster_time": "08:00",
    "evening_reflection_time": "18:30",
    "status": "new",
    "projects": ["general", "work", "personal"],
    "work_days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "last_morning_trigger_date": "",
    "last_evening_trigger_date": "",
}

def _load_registry():
    global _registry
    try:
        os.makedirs(os.path.dirname(USER_REGISTRY_PATH), exist_ok=True)
        if os.path.exists(USER_REGISTRY_PATH):
            with open(USER_REGISTRY_PATH, "r", encoding="utf-8") as f:
                _registry = json.load(f) or {}
    except (IOError, json.JSONDecodeError) as e:
        log_error("user_registry", "_load_registry", f"Failed to load registry file {USER_REGISTRY_PATH}", e)
        _registry = {}

def _save_registry():
    try:
        with open(USER_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(_registry, f, indent=2, ensure_ascii=False)
    except IOError as e:
        log_error("user_registry", "_save_registry", f"Failed to write registry file {USER_REGISTRY_PATH}", e)

def get_all_preferences() -> Dict[str, Dict[str, Any]]:
    return _registry.copy()

def get_user_preferences(user_id: str) -> Dict[str, Any] | None:
    user_data = _registry.get(user_id, {})
    prefs = user_data.get("preferences", {})
    # Ensure all default keys exist for safety
    full_prefs = DEFAULT_PREFERENCES.copy()
    full_prefs.update(prefs)
    return full_prefs

def create_or_update_user_preferences(user_id: str, updates: Dict) -> bool:
    if user_id not in _registry:
        _registry[user_id] = {"preferences": DEFAULT_PREFERENCES.copy()}
    
    _registry[user_id]["preferences"].update(updates)
    _save_registry()
    return True

_load_registry()