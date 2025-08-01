# bridge/request_router.py
import re
import os
import json
import threading
import time
from typing import Dict, Any

from tools.logger import log_info, log_error, log_warning
import users.user_manager as user_manager
from agents.kairo_agent import handle_user_request
from services.cheats import handle_cheat_command
from services.shared_resources import get_message_templates, get_welcome_message_key

# --- Setup ---
GENERIC_ERROR_MSG_ROUTER = (get_message_templates("generic_error_message") or {}).get("en", "Sorry, an error occurred.")
_bridge_instance: Any = None
_bridge_lock = threading.Lock()

# --- Idempotency Cache ---
_processed_messages_cache: Dict[str, float] = {}
_cache_lock = threading.Lock()
CACHE_EXPIRATION_SECONDS = 30 

def get_bridge() -> Any:
    global _bridge_instance
    if _bridge_instance is None:
        with _bridge_lock:
            if _bridge_instance is None:
                bridge_type = os.getenv("BRIDGE_TYPE", "cli")
                log_info("request_router", "get_bridge", f"First call. Initializing bridge of type '{bridge_type}'...")
                try:
                    if bridge_type == "cli":
                        from bridge.cli_interface import CLIBridge, outgoing_cli_messages, cli_queue_lock
                        _bridge_instance = CLIBridge(outgoing_cli_messages, cli_queue_lock)
                    elif bridge_type == "whatsapp":
                        from bridge.whatsapp_interface import WhatsAppBridge, outgoing_whatsapp_messages, whatsapp_queue_lock
                        _bridge_instance = WhatsAppBridge(outgoing_whatsapp_messages, whatsapp_queue_lock)
                    elif bridge_type == "twilio":
                        from bridge.twilio_interface import TwilioBridge
                        from twilio.rest import Client as TwilioSdkClient
                        sid, token, number = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"), os.getenv("TWILIO_WHATSAPP_NUMBER")
                        if not all([sid, token, number]): raise ValueError("Twilio credentials missing.")
                        _bridge_instance = TwilioBridge(TwilioSdkClient(sid, token), number)
                    else:
                        raise ValueError(f"Unsupported bridge type: {bridge_type}")
                    log_info("request_router", "get_bridge", f"Bridge '{type(_bridge_instance).__name__}' initialized.")
                except (ImportError, ValueError) as e:
                    log_error("request_router", "get_bridge", f"Failed to initialize bridge '{bridge_type}'", e)
    return _bridge_instance

def send_message(user_id: str, message_body: str):
    if not user_id or not message_body: return
    user_manager.add_message_to_user_history(user_id, "assistant", "agent_text_response", content=message_body)
    bridge = get_bridge()
    if bridge:
        bridge.send_message(user_id, message_body)
    else:
        log_error("request_router", "send_message", "Bridge not available.")

def normalize_user_id(user_id_from_bridge: str) -> str:
    if not user_id_from_bridge: return ""
    return re.sub(r'\D', '', str(user_id_from_bridge))

def handle_incoming_message(user_id_from_bridge: str, message_text: str, message_id: str | None = None):
    if message_id:
        with _cache_lock:
            current_time = time.time()
            expired_ids = [msg_id for msg_id, ts in _processed_messages_cache.items() if current_time - ts > CACHE_EXPIRATION_SECONDS]
            for msg_id in expired_ids:
                del _processed_messages_cache[msg_id]
            if message_id in _processed_messages_cache:
                log_warning("request_router", "handle_incoming", f"Duplicate message ID received: {message_id}. Ignoring.")
                return
            _processed_messages_cache[message_id] = current_time

    norm_user_id = normalize_user_id(user_id_from_bridge)
    if not norm_user_id: return

    agent_state = user_manager.get_agent(norm_user_id)
    if not agent_state:
        log_error("request_router", "handle_incoming", f"CRITICAL: Failed to get/create agent state for {norm_user_id}.")
        return

    user_manager.add_message_to_user_history(norm_user_id, "user", "user_text", content=message_text)

    if message_text.strip().startswith('/'):
        parts = message_text.strip().split(); command = parts[0].lower(); args = parts[1:]
        cheat_result = handle_cheat_command(norm_user_id, command, args)
        if cheat_result.get("type") == "message": send_message(norm_user_id, cheat_result.get("content", "OK."))
        elif cheat_result.get("type") == "system_event": handle_internal_system_event({"user_id": norm_user_id, "trigger_type": cheat_result.get("trigger_type")})
        return

    welcome_key = get_welcome_message_key()
    if agent_state.get("preferences", {}).get("status") == "new":
        welcome_templates = get_message_templates(welcome_key) or {}
        user_lang = agent_state.get("preferences", {}).get("language", "en")
        send_message(norm_user_id, welcome_templates.get(user_lang, "Hello!"))
        user_manager.update_user_preferences(norm_user_id, {"status": "onboarding"})
        return

    try:
        response = handle_user_request(user_id=norm_user_id, message=message_text, full_context=agent_state)
        if response: send_message(norm_user_id, response)
    except Exception as e:
        log_error("request_router", "handle_incoming", f"Error from KairoAgent for {norm_user_id}", e)
        send_message(norm_user_id, GENERIC_ERROR_MSG_ROUTER)

def handle_internal_system_event(event_data: Dict):
    user_id = event_data.get("user_id")
    trigger_type = event_data.get("trigger_type")
    if not user_id or not trigger_type: return

    agent_state = user_manager.get_agent(user_id)
    if not agent_state or agent_state.get("preferences", {}).get("status") != "active": return

    try:
        trigger_as_message = json.dumps({"trigger": trigger_type})
        response = handle_user_request(user_id=user_id, message=trigger_as_message, full_context=agent_state)
        if response: send_message(user_id, response)
    except Exception as e:
        log_error("request_router", "handle_internal", f"Error routing internal event '{trigger_type}' for {user_id}", e)