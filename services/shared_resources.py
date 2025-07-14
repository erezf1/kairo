# services/shared_resources.py
import yaml
import os
from tools.logger import log_error, log_info

_PROMPTS = {}
_MESSAGES = {}
_PROJECT_SETTINGS = {}

def load_resources():
    """Loads all YAML files into memory."""
    global _PROMPTS, _MESSAGES, _PROJECT_SETTINGS
    
    try:
        with open("config/prompts.yaml", 'r', encoding="utf-8") as f:
            _PROMPTS = yaml.safe_load(f) or {}
    except Exception as e:
        log_error("shared_resources", "load_resources", f"Failed to load prompts.yaml: {e}")

    try:
        with open("config/messages.yaml", 'r', encoding="utf-8") as f:
            _MESSAGES = yaml.safe_load(f) or {}
    except Exception as e:
        log_error("shared_resources", "load_resources", f"Failed to load messages.yaml: {e}")

    try:
        with open("config/settings.yaml", 'r', encoding="utf-8") as f:
            _PROJECT_SETTINGS = yaml.safe_load(f) or {}
    except Exception as e:
        log_error("shared_resources", "load_resources", f"Failed to load settings.yaml: {e}")
        
    log_info("shared_resources", "load_resources", "Shared prompts, messages, and settings have been loaded.")

def get_prompt(key: str) -> str | None:
    return _PROMPTS.get(key)

def get_message_templates(key: str) -> dict | None:
    return _MESSAGES.get(key)

# --- START OF REFACTORED LOGIC ---

def _get_current_project_config() -> dict:
    """Internal helper to get the full config block for the current project."""
    project_name = os.getenv("PROJECT_NAME", "kairo")
    log_info("shared_resources", "get_project_config", f"Loading config for project: {project_name}.")
    
    project_configs = _PROJECT_SETTINGS.get("projects", {})
    # Return the specific project config, or fall back to the default config block
    return project_configs.get(project_name, _PROJECT_SETTINGS.get("default_config", {}))

def get_default_preferences() -> dict:
    """Gets the default_preferences dictionary for the current project."""
    config = _get_current_project_config()
    preferences = config.get("default_preferences", {})
    if not preferences:
        log_error("shared_resources", "get_defaults", "CRITICAL: Could not find 'default_preferences' in config for current project.")
        # Return a hardcoded safe fallback
        return {"name": None, "timezone": None, "language": "en", "status": "new"}
    return preferences

def get_welcome_message_key() -> str:
    """Gets the welcome_message_key for the current project."""
    config = _get_current_project_config()
    # Fall back to the standard key if not found
    return config.get("welcome_message_key", "initial_welcome_message")

# --- END OF REFACTORED LOGIC ---

load_resources()