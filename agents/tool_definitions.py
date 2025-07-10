# agents/tool_definitions.py
from pydantic import BaseModel, Field
from typing import Dict, Optional, List

# The tools now interact with our high-level service managers
import services.task_manager as kairo_core
import users.user_manager as user_manager

# ===================================================================
# == 1. Pydantic Models for Tool Parameters
# ===================================================================

class CreateTaskParams(BaseModel):
    """A tool to create a new task item in the user's logbook."""
    description: str = Field(..., description="The full description of the task.")
    project: Optional[str] = Field(None, description="Optional: A project tag, e.g., '#work'.")
    due_date: Optional[str] = Field(None, description="Optional: A due date in 'YYYY-MM-DD' format.")
    size: Optional[str] = Field(None, description="The estimated size of the task, e.g., 'small', 'medium', 'large'.")
    worktime: Optional[int] = Field(None, description="The estimated work time in minutes required for the task.")
    priority: Optional[int] = Field(None, description="The priority of the task, e.g., 1 (highest) to 5 (lowest).")
    urgency: Optional[int] = Field(None, description="The urgency of the task, e.g., 1 (highest) to 5 (lowest).")
    main_task_id: Optional[str] = Field(None, description="If this is a sub-task, the item_id of the main parent task.")

class CreateReminderParams(BaseModel):
    """A tool to create a new reminder item for a specific time."""
    description: str = Field(..., description="The full description of the reminder.")
    remind_at: str = Field(..., description="The specific time for the reminder in ISO 8601 UTC format.")
    duration: Optional[int] = Field(None, description="The duration of the event in minutes, for creating a calendar event.")

class UpdateItemParams(BaseModel):
    """A tool to update one or more properties of an existing task or reminder."""
    item_id: str = Field(..., description="The unique ID of the task or reminder to update.")
    updates: Dict = Field(..., description="A dictionary of fields to update, e.g., {'description': 'new text', 'status': 'completed'}.")

class UpdateUserPreferencesParams(BaseModel):
    """A tool to update the user's core preferences like name or timezone."""
    name: Optional[str] = Field(None, description="The user's preferred name.")
    timezone: Optional[str] = Field(None, description="The user's timezone, e.g., 'America/New_York'.")
    language: Optional[str] = Field(None, description="The user's language, 'en' or 'he'.")
    work_days: Optional[List[str]] = Field(None, description="A list of the user's working days, e.g., ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']")

class FinalizeOnboardingParams(BaseModel):
    """
    A tool to be called with no parameters when the user has confirmed their initial settings.
    This action completes the setup process.
    """
    pass

# ===================================================================
# == 2. Tool Function Definitions
# ===================================================================

def create_task(user_id: str, params: CreateTaskParams) -> Dict:
    """Creates a new task item and returns its data."""
    # Pass all optional params by excluding None values
    created_item = kairo_core.create_item(user_id, "task", params.model_dump(exclude_none=True))
    if created_item.get("success"):
        return {"success": True, "item_id": created_item.get("item_id")}
    return {"success": False, "error": "Failed to create task."}

def create_reminder(user_id: str, params: CreateReminderParams) -> Dict:
    """Creates a new reminder item and returns its data."""
    created_item = kairo_core.create_item(user_id, "reminder", params.model_dump(exclude_none=True))
    if created_item.get("success"):
        return {"success": True, "item_id": created_item.get("item_id")}
    return {"success": False, "error": "Failed to create reminder."}

def update_item(user_id: str, params: UpdateItemParams) -> Dict:
    """Updates properties of an existing item and reports success."""
    updated_item = kairo_core.update_item(user_id, params.item_id, params.updates)
    if updated_item.get("success"):
        return {"success": True, "item_id": updated_item.get("item_id")}
    return {"success": False, "error": "Failed to update item."}

def update_user_preferences(user_id: str, params: UpdateUserPreferencesParams) -> Dict:
    """Updates the user's preferences and reports success."""
    updates_to_apply = params.model_dump(exclude_unset=True, exclude_none=True)
    if not updates_to_apply:
        return {"success": False, "error": "No preferences were provided to update."}
    success = user_manager.update_user_preferences(user_id, updates_to_apply)
    return {"success": success}

def finalize_onboarding(user_id: str, params: FinalizeOnboardingParams) -> Dict:
    """Sets the user's status to 'active' and reports success."""
    success = user_manager.update_user_preferences(user_id, {"status": "active"})
    return {"success": success}

# ===================================================================
# == 3. Tool Dictionaries for the Agent
# ===================================================================

AVAILABLE_TOOLS = {
    "create_task": create_task,
    "create_reminder": create_reminder,
    "update_item": update_item,
    "update_user_preferences": update_user_preferences,
    "finalize_onboarding": finalize_onboarding,
}

TOOL_PARAM_MODELS = {
    "create_task": CreateTaskParams,
    "create_reminder": CreateReminderParams,
    "update_item": UpdateItemParams,
    "update_user_preferences": UpdateUserPreferencesParams,
    "finalize_onboarding": FinalizeOnboardingParams,
}