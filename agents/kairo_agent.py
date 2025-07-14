# agents/kairo_agent.py
import json
from typing import Dict, List, Any

# Core application imports
from services.llm_interface import get_instructor_client
from .tool_definitions import AVAILABLE_TOOLS, TOOL_PARAM_MODELS
from tools.logger import log_info, log_error
from services.shared_resources import get_prompt, get_message_templates
from users.user_manager import add_message_to_user_history
import tools.activity_db as db

ERROR_TEMPLATES = get_message_templates("generic_error_message") or {}
GENERIC_ERROR_MSG = ERROR_TEMPLATES.get("en", "Sorry, an error occurred.")

def handle_user_request(user_id: str, message: str, full_context: Dict) -> str:
    """Handles all incoming requests (user messages & system triggers) for Kairo."""
    fn_name = "handle_user_request"
    client = get_instructor_client()
    if not client: return GENERIC_ERROR_MSG

    # 1. Determine which prompt to use based on user status
    user_status = full_context.get("preferences", {}).get("status", "new")
    if user_status in ["new", "pending_onboarding", "onboarding"]:
        system_prompt_key = "kairo_onboarding_system_prompt"
    else: # 'active' or other statuses
        system_prompt_key = "kairo_agent_system_prompt"
    
    system_prompt = get_prompt(system_prompt_key)
    if not system_prompt:
        log_error("kairo_agent", fn_name, f"Critical: Prompt '{system_prompt_key}' not found.")
        return GENERIC_ERROR_MSG

    # 2. Prepare context and message history for the LLM
    try:
        context_for_llm = {
            "preferences": full_context.get("preferences", {}),
            "items": full_context.get("items", [])
        }
        context_json_str = json.dumps(context_for_llm, separators=(',', ':'), default=str)
        
        llm_history = full_context.get("conversation_history", [])
        system_message = f"{system_prompt}\n\n--- CURRENT USER CONTEXT ---\n{context_json_str}"
        
        messages_for_api = [{"role": "system", "content": system_message}] + llm_history
        if message:
            messages_for_api.append({"role": "user", "content": message})
            
    except Exception as e:
        log_error("kairo_agent", fn_name, f"Error preparing context for {user_id}", e)
        return GENERIC_ERROR_MSG

    # 3. Call LLM and process tools
    try:
        log_info("kairo_agent", fn_name, f"Calling LLM for user {user_id} with status '{user_status}'...")
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages_for_api,
            tools=[{"type": "function", "function": {"name": name, "description": model.__doc__, "parameters": model.model_json_schema()}} for name, model in TOOL_PARAM_MODELS.items()],
            tool_choice="auto", max_retries=1, temperature=0.2,
        )

        message_from_llm = response.choices[0].message
        add_message_to_user_history(user_id, "assistant", "agent_raw_response", content=message_from_llm.content)

        if message_from_llm.tool_calls:
            log_info("kairo_agent", fn_name, f"LLM requested {len(message_from_llm.tool_calls)} tool(s).")
            messages_for_api.append(message_from_llm)
            for tool_call in message_from_llm.tool_calls:
                tool_name = tool_call.function.name
                tool_function = AVAILABLE_TOOLS.get(tool_name)
                if not tool_function: continue
                try:
                    param_model = TOOL_PARAM_MODELS[tool_name]
                    tool_args = param_model.model_validate_json(tool_call.function.arguments)
                    tool_result = tool_function(user_id=user_id, params=tool_args)
                    db.log_llm_activity(user_id, tool_name, tool_args.model_dump(), tool_result)
                    messages_for_api.append({"tool_call_id": tool_call.id, "role": "tool", "name": tool_name, "content": json.dumps(tool_result, default=str)})
                except Exception as e:
                    log_error("kairo_agent", fn_name, f"Error executing tool '{tool_name}'", e)
                    messages_for_api.append({"tool_call_id": tool_call.id, "role": "tool", "name": tool_name, "content": json.dumps({"error": str(e)})})
            
            final_response = client.chat.completions.create(model="gpt-4-turbo", messages=messages_for_api, temperature=0.2)
            final_response_message = final_response.choices[0].message.content
        else:
            final_response_message = message_from_llm.content

        log_info("kairo_agent", fn_name, f"Generated final response for user {user_id}.")
        return final_response_message

    except Exception as e:
        log_error("kairo_agent", fn_name, f"LLM or tool processing error for user {user_id}", e)
        return GENERIC_ERROR_MSG