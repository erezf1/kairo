# users/user_manager.py
import json
import os
import threading
from typing import Dict, Any, List
from datetime import datetime, timezone
from tools.logger import log_info, log_error
import tools.activity_db as db
from services.shared_resources import get_default_preferences

# Configuration
USER_DATA_PATH = os.path.join("data", f"kairo_users{os.getenv('DATA_SUFFIX', '')}.json")
_user_prefs_store: Dict[str, Dict[str, Any]] = {}
_prefs_lock = threading.Lock()

def _load_user_preferences():
    global _user_prefs_store
    try:
        os.makedirs(os.path.dirname(USER_DATA_PATH), exist_ok=True)
        if os.path.exists(USER_DATA_PATH):
            with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
                full_data = json.loads(f.read() or "{}")
                for user_id, data in full_data.items():
                    if "preferences" in data: _user_prefs_store[user_id] = data["preferences"]
    except Exception as e:
        log_error("user_manager", "load_prefs", "Failed to load preferences file", e)

def _save_user_preferences():
    try:
        data_to_save = {uid: {"preferences": p} for uid, p in _user_prefs_store.items()}
        with open(USER_DATA_PATH + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        os.replace(USER_DATA_PATH + ".tmp", USER_DATA_PATH)
    except Exception as e:
        log_error("user_manager", "save_prefs", "Failed to write preferences", e)

def init_all_agents():
    _load_user_preferences()

def get_agent(user_id: str) -> Dict[str, Any]:
    with _prefs_lock:
        if user_id not in _user_prefs_store:
            log_info("user_manager", "get_agent", f"Creating new user preferences for {user_id}")
            _user_prefs_store[user_id] = get_default_preferences()
            _save_user_preferences()
        preferences = _user_prefs_store.get(user_id, get_default_preferences())

    # --- START OF FIX: Handle 'work_days' to 'ritual_days' migration ---
    if "ritual_days" not in preferences and "work_days" in preferences:
        preferences["ritual_days"] = preferences["work_days"]
    # --- END OF FIX ---

    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    all_active_items = db.list_items_for_user(user_id, status_filter=["new", "in_progress"])
    non_overdue_items = [item for item in all_active_items if not item.get("due_date") or item.get("due_date") >= today_str]
    conversation_history = db.get_recent_messages(user_id, limit=10)
    preferences['current_utc_date'] = today_str
    
    return {
        "user_id": user_id, "preferences": preferences,
        "items": non_overdue_items, "conversation_history": conversation_history
    }

def get_all_user_data() -> Dict[str, Dict[str, Any]]:
    with _prefs_lock: return json.loads(json.dumps(_user_prefs_store))

def add_message_to_user_history(user_id: str, role: str, message_type: str, content: str | None = None, **kwargs):
    db.log_message(user_id=user_id, role=role, message_type=message_type, content=content)

def update_user_preferences(user_id: str, updates: Dict) -> bool:
    with _prefs_lock:
        if user_id not in _user_prefs_store: _user_prefs_store[user_id] = get_default_preferences()
        
        # --- START OF FIX: Handle 'work_days' to 'ritual_days' migration during update ---
        if "work_days" in updates:
            updates["ritual_days"] = updates.pop("work_days")
        # --- END OF FIX ---
        
        _user_prefs_store[user_id].update(updates)
        _save_user_preferences()
    return True