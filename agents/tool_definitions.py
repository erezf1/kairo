# agents/tool_definitions.py
from pydantic import BaseModel, Field
from typing import Dict, Optional

# The tools now interact with our high-level service managers
import services.task_manager as kairo_core
import users.user_manager as user_manager
from services.shared_resources import get_message_templates

# ===================================================================
# == 1. Pydantic Models for Tool Parameters
# == Defines the expected inputs for each tool the agent can use.
# ===================================================================

class CreateTaskParams(BaseModel):
    """A tool to create a new task item in the user's logbook."""
    description: str = Field(..., description="The full description of the task.")
    project: str = Field("", description="Optional: A project tag, e.g., '#work'.")
    due_date: str = Field("", description="Optional: A due date in 'YYYY-MM-DD' format.")

class CreateReminderParams(BaseModel):
    """A tool to create a new reminder item for a specific time."""
    description: str = Field(..., description="The full description of the reminder.")
    remind_at: str = Field(..., description="The specific time for the reminder in ISO 8601 UTC format.")

class UpdateItemParams(BaseModel):
    """A tool to update one or more properties of an existing task or reminder."""
    item_id: str = Field(..., description="The unique ID of the task or reminder to update.")
    # --- THIS IS THE FIX ---
    updates: Dict = Field(..., description="A dictionary of fields to update, e.g., {'description': 'new text', 'status': 'completed', 'status': 'deleted'}.")
    # --- END OF FIX ---

class UpdateUserPreferencesParams(BaseModel):
    """A tool to update the user's core preferences like name or timezone."""
    name: Optional[str] = Field(None, description="The user's preferred name.")
    timezone: Optional[str] = Field(None, description="The user's timezone, e.g., 'America/New_York'.")
    language: Optional[str] = Field(None, description="The user's language, 'en' or 'he'.")
    work_days: Optional[list[str]] = Field(None, description="A list of the user's working days, e.g., ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']")

class FinalizeOnboardingParams(BaseModel):
    """
    A tool to be called with no parameters when the user has confirmed their initial settings.
    This action completes the setup process.
    """
    pass

# ===================================================================
# == 2. Tool Function Definitions
# == The actual Python functions that get executed by the agent.
# == Note: They return data for the agent, NOT user-facing messages.
# ===================================================================

def create_task(user_id: str, params: CreateTaskParams) -> Dict:
    """Creates a new task item and returns its data."""
    created_item = kairo_core.create_item(user_id, "task", params.model_dump())
    if created_item:
        return {"success": True, "item_id": created_item.get("item_id")}
    return {"success": False, "error": "Failed to create task."}

def create_reminder(user_id: str, params: CreateReminderParams) -> Dict:
    """Creates a new reminder item and returns its data."""
    created_item = kairo_core.create_item(user_id, "reminder", params.model_dump())
    if created_item:
        return {"success": True, "item_id": created_item.get("item_id")}
    return {"success": False, "error": "Failed to create reminder."}

def update_item(user_id: str, params: UpdateItemParams) -> Dict:
    """Updates properties of an existing item and reports success."""
    updated_item = kairo_core.update_item(user_id, params.item_id, params.updates)
    if updated_item:
        return {"success": True, "item_id": updated_item.get("item_id")}
    return {"success": False, "error": "Failed to update item."}

def update_user_preferences(user_id: str, params: UpdateUserPreferencesParams) -> Dict:
    """Updates the user's preferences and reports success."""
    updates_to_apply = params.model_dump(exclude_unset=True)
    if not updates_to_apply:
        return {"success": False, "error": "No preferences were provided to update."}
    
    success = user_manager.update_user_preferences(user_id, updates_to_apply)
    return {"success": success}

def finalize_onboarding(user_id: str, params: FinalizeOnboardingParams) -> Dict:
    """Sets the user's status to 'active' and reports success."""
    success = user_manager.update_user_preferences(user_id, {"status": "active"})
    # The agent will formulate the final welcome message based on this success result.
    return {"success": success}

# ===================================================================
# == 3. Tool Dictionaries for the Agent
# == These dictionaries map the tool names to their functions and models.
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