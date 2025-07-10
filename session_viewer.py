# session_viewer.py
import sqlite3
import json
import argparse
from datetime import datetime, timezone
import pytz
from typing import List, Dict

# --- Configuration ---
DB_DIR = "data"
# This allows the script to work with both _cli and non-suffixed DBs
DB_SUFFIX = "_cli" # Set to "" for production, or pass as an argument
DB_FILE_PATH = "" # Will be set by arguments

# --- Helper Functions ---
def _format_timestamp(ts_str: str, local_tz: pytz.BaseTzInfo) -> str:
    """Converts a UTC ISO string to a user-friendly local time string."""
    if not ts_str:
        return " " * 19
    try:
        utc_dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return ts_str[:19] # Fallback to show raw timestamp

def _pretty_print_json(json_str: str) -> str:
    """Formats a JSON string with indentation for readability."""
    try:
        obj = json.loads(json_str)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return json_str # Return as is if not valid JSON

# --- Main Logic ---
def get_user_session(db_path: str, user_id: str, local_tz: pytz.BaseTzInfo) -> None:
    """Queries all relevant tables for a user's session and prints a chronological log."""
    
    all_events = []
    
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Fetch messages
            cursor.execute("SELECT * FROM messages WHERE user_id = ?", (user_id,))
            for row in cursor.fetchall():
                all_events.append({
                    "timestamp": row["timestamp"],
                    "type": "MESSAGE",
                    "data": dict(row)
                })

            # 2. Fetch LLM tool activity
            cursor.execute("SELECT * FROM llm_activity WHERE user_id = ?", (user_id,))
            for row in cursor.fetchall():
                all_events.append({
                    "timestamp": row["timestamp"],
                    "type": "TOOL_CALL",
                    "data": dict(row)
                })

            # 3. Fetch system logs (errors/warnings)
            cursor.execute("SELECT * FROM system_logs") # Get all, then we'll filter
            for row in cursor.fetchall():
                 # For system logs, we can't always guarantee a user_id context, so we show all for now
                 # A more advanced version could try to correlate by timestamp
                 all_events.append({
                    "timestamp": row["timestamp"],
                    "type": f"SYS_{row['level']}",
                    "data": dict(row)
                })

    except sqlite3.Error as e:
        print(f"❌ Database Error: Could not connect to or query '{db_path}'.\n   Reason: {e}")
        return

    if not all_events:
        print(f"No activity found for user ID: {user_id}")
        return

    # Sort all collected events chronologically
    all_events.sorted_events = sorted(all_events, key=lambda x: x["timestamp"])

    # --- Print the formatted session log ---
    print("\n" + "="*80)
    print(f"Kairo Session Log for User: {user_id}")
    print(f"Timezone: {local_tz.zone}")
    print("="*80 + "\n")

    for event in all_events.sorted_events:
        ts = _format_timestamp(event["timestamp"], local_tz)
        event_type = event["type"]
        data = event["data"]

        if event_type == "MESSAGE":
            role = data['role'].upper()
            content = data['content']
            if role == 'USER':
                print(f"[{ts}] 👤 \033[92m{role}:\033[0m {content}") # Green
            else: # ASSISTANT
                print(f"[{ts}] 🤖 \033[94m{role}:\033[0m {content}") # Blue

        elif event_type == "TOOL_CALL":
            tool_name = data['tool_name']
            print(f"[{ts}] ⚙️  \033[93mTOOL CALL: {tool_name}\033[0m")
            print("   ▶️  Args:")
            print(_pretty_print_json(data['tool_args_json']))
            print("   ◀️  Result:")
            print(_pretty_print_json(data['tool_result_json']))
        
        elif event_type.startswith("SYS_"):
            level = data['level']
            color = '\033[91m' if level == 'ERROR' else '\033[93m' # Red for Error, Yellow for Warning
            print(f"[{ts}] ⚠️  {color}{level} in {data['module']}:{data['function']}\033[0m")
            print(f"   - {data['message']}")
            if data['traceback']:
                print(f"   - Traceback: {data['traceback']}")

    print("\n" + "="*80)
    print("End of session log.")
    print("="*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View a user's chronological session from the Kairo database.")
    parser.add_argument("user_id", type=str, help="The user ID to retrieve the session for.")
    parser.add_argument("--mode", type=str, choices=['cli', 'prod'], default='cli', help="The database mode ('cli' or 'prod'). Defaults to 'cli'.")
    parser.add_argument("--tz", type=str, default="Asia/Jerusalem", help="Your local timezone for displaying timestamps, e.g., 'America/New_York'. Defaults to 'Asia/Jerusalem'.")
    
    args = parser.parse_args()
    
    db_suffix = "_cli" if args.mode == 'cli' else ""
    db_path = os.path.join(DB_DIR, f"kairo_activity{db_suffix}.db")
    
    try:
        local_timezone = pytz.timezone(args.tz)
    except pytz.UnknownTimeZoneError:
        print(f"❌ Unknown timezone '{args.tz}'. Please use a valid TZ database name.")
        exit(1)

    get_user_session(db_path, args.user_id, local_timezone)