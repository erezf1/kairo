# users/user_manager.py
import json
import os
import threading
from typing import Dict, Any, List
from tools.logger import log_info, log_error
import tools.activity_db as db

# --- Configuration ---
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

# --- Preference Management Functions ---

def _load_user_preferences():
    """Loads ONLY user preferences from the JSON file into memory."""
    global _user_prefs_store
    try:
        os.makedirs(os.path.dirname(USER_DATA_PATH), exist_ok=True)
        if os.path.exists(USER_DATA_PATH):
            with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                full_data = json.loads(content) if content.strip() else {}
                for user_id, data in full_data.items():
                    if "preferences" in data:
                        _user_prefs_store[user_id] = data["preferences"]
        else:
            _user_prefs_store = {}
        log_info("user_manager", "load_prefs", f"Loaded preferences for {len(_user_prefs_store)} users.")
    except Exception as e:
        log_error("user_manager", "load_prefs", "Failed to load preferences file", e)
        _user_prefs_store = {}

def _save_user_preferences():
    """Saves ONLY the in-memory preferences store to the JSON file."""
    data_to_save = {user_id: {"preferences": prefs} for user_id, prefs in _user_prefs_store.items()}
    try:
        temp_path = USER_DATA_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, USER_DATA_PATH)
    except Exception as e:
        log_error("user_manager", "save_prefs", "Failed to write preferences to file", e)

# --- Public API for Application ---

def init_all_agents():
    """Initializes the user preference store from file at startup."""
    _load_user_preferences()

def get_agent(user_id: str) -> Dict[str, Any]:
    """
    Constructs the full agent state for a single turn.
    - Fetches preferences from the in-memory store.
    - Fetches items AND recent conversation history from the database.
    """
    with _prefs_lock:
        if user_id not in _user_prefs_store:
            log_info("user_manager", "get_agent", f"Creating new user preferences for {user_id}")
            _user_prefs_store[user_id] = DEFAULT_PREFERENCES.copy()
            _save_user_preferences()
        preferences = _user_prefs_store.get(user_id, DEFAULT_PREFERENCES.copy())

    # Fetch fresh item data from the database
    active_items = db.list_items_for_user(user_id, status_filter=["new", "in_progress"])
    
    # Fetch recent conversation history to provide context
    conversation_history = db.list_messages_for_user(user_id, limit=10)
    
    return {
        "user_id": user_id,
        "preferences": preferences,
        "items": active_items,
        "conversation_history": conversation_history 
    }

def get_all_user_data() -> Dict[str, Dict[str, Any]]:
    """Returns all user preference data for the scheduler."""
    with _prefs_lock:
        return json.loads(json.dumps(_user_prefs_store))

def add_message_to_user_history(user_id: str, role: str, message_type: str, content: str | None = None, **kwargs):
    """Logs a message directly to the database."""
    db.log_message(user_id=user_id, role=role, message_type=message_type, content=content)

def update_user_preferences(user_id: str, updates: Dict) -> bool:
    """Safely updates a user's preferences and saves to the JSON file."""
    with _prefs_lock:
        if user_id not in _user_prefs_store:
            _user_prefs_store[user_id] = DEFAULT_PREFERENCES.copy()
        _user_prefs_store[user_id].update(updates)
        _save_user_preferences()
    return True