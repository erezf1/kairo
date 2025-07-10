# services/shared_resources.py
# This module is a centralized place to load shared resources like prompts and messages.
# It has no other project dependencies, which prevents circular imports.
import yaml
import os
from tools.logger import log_error, log_info

_PROMPTS = {}
_MESSAGES = {}

def load_resources():
    """Loads all YAML files into memory."""
    global _PROMPTS, _MESSAGES
    
    try:
        with open("config/prompts.yaml", 'r', encoding="utf-8") as f:
            _PROMPTS = yaml.safe_load(f) or {}
    except Exception as e:
        log_error("shared_resources", "load_resources", f"Failed to load prompts.yaml: {e}")
        _PROMPTS = {}

    try:
        with open("config/messages.yaml", 'r', encoding="utf-8") as f:
            _MESSAGES = yaml.safe_load(f) or {}
    except Exception as e:
        log_error("shared_resources", "load_resources", f"Failed to load messages.yaml: {e}")
        _MESSAGES = {}
        
    log_info("shared_resources", "load_resources", "Shared prompts and messages have been loaded.")

def get_prompt(key: str) -> str | None:
    """Gets a specific prompt by its key."""
    return _PROMPTS.get(key)

def get_message_templates(key: str) -> dict | None:
    """Gets a dictionary of message templates (for different languages) by its key."""
    return _MESSAGES.get(key)

# Load resources when the module is first imported.
load_resources()