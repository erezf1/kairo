# users/user_manager.py
import json
import os
import threading
from typing import Dict, Any, List
from datetime import datetime, timezone
from tools.logger import log_info, log_error
import tools.activity_db as db

# Configuration
USER_DATA_PATH = os.path.join("data", f"kairo_users{os.getenv('DATA_SUFFIX', '')}.json")
_user_prefs_store: Dict[str, Dict[str, Any]] = {}
_prefs_lock = threading.Lock()
DEFAULT_PREFERENCES = {
    "name": "friend", "timezone": None, "language": "en", "status": "new",
    "morning_muster_time": "08:00", "evening_reflection_time": "18:30",
    "projects": ["general", "work", "personal"],
    "work_days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "last_morning_trigger_date": "", "last_evening_trigger_date": "",
}

# Preference Management
def _load_user_preferences():
    """Loads ONLY user preferences from the JSON file into memory."""
    global _user_prefs_store
    try:
        os.makedirs(os.path.dirname(USER_DATA_PATH), exist_ok=True)
        if os.path.exists(USER_DATA_PATH):
            with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
                full_data = json.loads(f.read() or "{}")
                for user_id, data in full_data.items():
                    if "preferences" in data: _user_prefs_store[user_id] = data["preferences"]
        else: _user_prefs_store = {}
        log_info("user_manager", "load_prefs", f"Loaded preferences for {len(_user_prefs_store)} users.")
    except Exception as e:
        log_error("user_manager", "load_prefs", "Failed to load preferences file", e); _user_prefs_store = {}

def _save_user_preferences():
    """Saves ONLY the in-memory preferences store to the JSON file."""
    try:
        data_to_save = {uid: {"preferences": p} for uid, p in _user_prefs_store.items()}
        with open(USER_DATA_PATH + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        os.replace(USER_DATA_PATH + ".tmp", USER_DATA_PATH)
    except Exception as e:
        log_error("user_manager", "save_prefs", "Failed to write preferences to file", e)

# Public API
def init_all_agents():
    _load_user_preferences()

def get_agent(user_id: str) -> Dict[str, Any]:
    """
    Constructs the full agent state for a single turn, now including
    conversation history and the current date.
    """
    with _prefs_lock:
        if user_id not in _user_prefs_store:
            log_info("user_manager", "get_agent", f"Creating new user preferences for {user_id}")
            _user_prefs_store[user_id] = DEFAULT_PREFERENCES.copy()
            _save_user_preferences()
        preferences = _user_prefs_store.get(user_id, DEFAULT_PREFERENCES.copy())

    # Fetch dynamic data from the database for the current turn
    active_items = db.list_items_for_user(user_id, status_filter=["new", "in_progress"])
    conversation_history = db.get_recent_messages(user_id, limit=10)
    
    # Add the current date, which is needed by the Morning Muster prompt
    preferences['current_utc_date'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    return {
        "user_id": user_id,
        "preferences": preferences,
        "items": active_items,
        "conversation_history": conversation_history
    }

def get_all_user_data() -> Dict[str, Dict[str, Any]]:
    with _prefs_lock: return json.loads(json.dumps(_user_prefs_store))

def add_message_to_user_history(user_id: str, role: str, message_type: str, content: str | None = None, **kwargs):
    db.log_message(user_id=user_id, role=role, message_type=message_type, content=content)

def update_user_preferences(user_id: str, updates: Dict) -> bool:
    with _prefs_lock:
        if user_id not in _user_prefs_store: _user_prefs_store[user_id] = DEFAULT_PREFERENCES.copy()
        _user_prefs_store[user_id].update(updates); _save_user_preferences()
    return True