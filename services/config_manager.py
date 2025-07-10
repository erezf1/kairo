# services/config_manager.py
# This service handles updating user preferences.
from typing import Dict

# It now imports from our new single data layer.
import data.data_manager as data_manager
from tools.logger import log_warning

def update_preferences(user_id: str, updates: Dict) -> bool:
    """
    Updates one or more preferences for a user and saves the changes.
    """
    fn_name = "update_preferences"
    if not isinstance(updates, dict) or not updates:
        log_warning("config_manager", fn_name, f"Invalid or empty updates dict provided for user {user_id}.")
        return False

    # 1. Get the user's full data record
    user_record = data_manager.get_user_record(user_id)
    if not user_record:
        # This case should ideally be handled by the user_manager creating a user first,
        # but we add a safeguard here.
        log_warning("config_manager", fn_name, f"User record for {user_id} not found. Cannot update preferences.")
        return False

    # 2. Update the preferences dictionary within the record
    if "preferences" not in user_record:
        user_record["preferences"] = {}
    
    user_record["preferences"].update(updates)

    # 3. Save the entire updated user record back to the data store
    return data_manager.write_user_record(user_id, user_record)