# services/cheats.py
import json
from typing import List, Dict, Any

import users.user_manager as user_manager
from tools.logger import log_info

def _handle_help() -> Dict:
    """Displays the available cheat commands."""
    return {"type": "message", "content": """Available Kairo Cheat Commands:
/help - Show this help message
/list [status] - List your items (status: active, new, in_progress, completed, deleted, all).
/memory - Show a summary of your current in-memory agent state.
/clear - !! DANGER !! Mark all non-deleted items as 'deleted'.
/morning - Manually trigger your Morning Muster.
/evening - Manually trigger your Evening Reflection."""}

def _handle_list(user_id: str, args: List[str]) -> Dict:
    """Lists items from the user's current agent state."""
    agent_state = user_manager.get_agent(user_id)
    if not agent_state or "items" not in agent_state:
        return {"type": "message", "content": "Error: Could not retrieve your items."}

    all_items = agent_state.get("items", [])
    status_filter = args[0].lower() if args else 'active'
    active_statuses = {"new", "in_progress"}
    
    if status_filter == 'all':
        filtered_items = all_items
    elif status_filter == 'active':
        filtered_items = [item for item in all_items if item.get('status') in active_statuses]
    else:
        filtered_items = [item for item in all_items if item.get('status') == status_filter]

    if not filtered_items:
        return {"type": "message", "content": f"No items found with status '{status_filter}'."}

    lines = [f"Items with status '{status_filter}':", "---"]
    for item in filtered_items:
        desc = item.get('description', '(No Description)')
        item_type = item.get('type', 'item')
        lines.append(f"({item_type}) {desc}")
    return {"type": "message", "content": "\n".join(lines)}

def _handle_memory(user_id: str) -> Dict:
    """Shows a summary of the agent's in-memory state."""
    agent_state = user_manager.get_agent(user_id)
    if not agent_state:
        return {"type": "message", "content": "Error: Agent state not found."}
        
    state_summary = {k: v for k, v in agent_state.items() if k != "conversation_history"}
    state_summary["history_count"] = len(agent_state.get("conversation_history", []))
    return {"type": "message", "content": f"Agent Memory Summary:\n```json\n{json.dumps(state_summary, indent=2, default=str)}\n```"}

def _handle_clear(user_id: str) -> Dict:
    """Marks all non-deleted items as 'deleted'."""
    from services.task_manager import update_item # Local import to avoid loops
    agent_state = user_manager.get_agent(user_id)
    if not agent_state: return {"type": "message", "content": "Error: Could not find user to clear items."}
        
    cleared_count = 0
    for item in agent_state.get("items", []):
        if item.get("status") != "deleted" and item.get("item_id"):
            update_item(user_id, item["item_id"], {"status": "deleted"})
            cleared_count += 1
    return {"type": "message", "content": f"Marked {cleared_count} item(s) as 'deleted'."}

def _handle_routines(routine_type: str) -> Dict:
    """Returns a special dictionary instructing the router to trigger a system event."""
    log_info("cheats", "_handle_routines", f"Cheat command is requesting a '{routine_type}' trigger.")
    return {"type": "system_event", "trigger_type": routine_type}

def handle_cheat_command(user_id: str, command: str, args: List[str]) -> Dict[str, Any]:
    """Main router for all cheat commands. Returns a dictionary specifying the action."""
    command_map = {
        "/help": _handle_help,
        "/list": lambda: _handle_list(user_id, args),
        "/memory": lambda: _handle_memory(user_id),
        "/clear": lambda: _handle_clear(user_id),
        "/morning": lambda: _handle_routines("morning_muster"),
        "/evening": lambda: _handle_routines("evening_reflection")
    }
    handler = command_map.get(command.lower())
    return handler() if handler else {"type": "message", "content": f"Unknown command: '{command}'. Try /help."}