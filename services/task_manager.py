# services/task_manager.py
import uuid
from datetime import datetime, timezone
from typing import Dict

import tools.activity_db as db
from tools.logger import log_info

def create_item(user_id: str, item_type: str, item_params: Dict) -> Dict:
    """Creates a new task or reminder in the database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    new_item_data = {
        "item_id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": item_type,
        "status": "new",
        "created_at": now_iso,
        "updated_at": now_iso,
        **item_params
    }
    
    # Ensure a description exists, as it's a required field in the database
    if 'description' not in new_item_data:
        new_item_data['description'] = 'No description provided'
    
    success = db.add_or_update_item(new_item_data)
    if success:
        log_info("task_manager", "create_item", f"Created {item_type} '{new_item_data['item_id']}' for {user_id}.")
        return {"success": True, "item_id": new_item_data["item_id"]}
    else:
        return {"success": False, "error": f"Failed to create {item_type}."}

def update_item(user_id: str, item_id: str, updates: Dict) -> Dict:
    """
    Updates an existing item in the database by fetching the full record,
    merging the changes, and saving it back.
    """
    # 1. Fetch the complete existing item from the database.
    existing_item = db.get_item(item_id)
    if not existing_item or existing_item.get("user_id") != user_id:
        return {"success": False, "error": "Item not found."}
    
    # --- THIS IS THE FIX ---
    # 2. Merge the original item's data with the new updates.
    #    This ensures all required fields (like 'user_id', 'type') are preserved.
    final_payload = {
        **existing_item,
        **updates,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    # --- END OF THE FIX ---
    
    # 3. Save the complete, valid object back to the database.
    success = db.add_or_update_item(final_payload)
    if success:
        log_info("task_manager", "update_item", f"Updated item '{item_id}' for user {user_id}.")
        return {"success": True, "item_id": item_id}
    else:
        # The database layer will log the specific SQLite error.
        return {"success": False, "error": "Failed to update item."}