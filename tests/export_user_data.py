# export_user_data.py
import sqlite3
import os
import re
import json
import argparse
from typing import List, Dict, Any
from datetime import datetime
import pytz

# --- Configuration ---
DB_DIR = "data"
LOCAL_TIMEZONE = "Asia/Jerusalem" # For display purposes

def normalize_phone(phone_number: str) -> str:
    """Removes all non-digit characters from a phone number string."""
    return re.sub(r'\D', '', phone_number)

def format_timestamp(ts_str: str, local_tz: pytz.BaseTzInfo) -> str:
    """Converts a UTC ISO string to a user-friendly local time string."""
    try:
        utc_dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
    except (ValueError, TypeError):
        return ts_str # Fallback for invalid formats

def pretty_print_json(json_str: str) -> str:
    """Formats a JSON string with indentation."""
    try:
        obj = json.loads(json_str)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return json_str

def export_user_report(user_phone: str, mode: str):
    """
    Connects to data sources, fetches all data for a user,
    and exports it to a chronological, human-readable text file.
    """
    normalized_user_id = normalize_phone(user_phone)
    suffix = f"_{mode}"
    output_filename = f"user_session_{normalized_user_id}.txt"

    db_path = os.path.join(DB_DIR, f"kairo_activity{suffix}.db")
    prefs_path = os.path.join(DB_DIR, f"kairo_users{suffix}.json")

    all_events: List[Dict[str, Any]] = []
    
    # 1. Get User Preferences
    if os.path.exists(prefs_path):
        with open(prefs_path, 'r', encoding='utf-8') as f:
            user_prefs_data = json.load(f).get(normalized_user_id, {}).get("preferences")
            if user_prefs_data:
                all_events.append({"timestamp": "0000-01-01T00:00:00Z", "type": "USER_PREFERENCES", "data": user_prefs_data})

    # 2. Get all dynamic data from the Database
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found at '{db_path}'"); return

    print(f"Connecting to database: {db_path}...")
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE user_id = ?", (normalized_user_id,))
            for r in cursor.fetchall(): all_events.append({"timestamp": r["timestamp"], "type": "MESSAGE", "data": dict(r)})
            cursor.execute("SELECT * FROM llm_activity WHERE user_id = ?", (normalized_user_id,))
            for r in cursor.fetchall(): all_events.append({"timestamp": r["timestamp"], "type": "TOOL_CALL", "data": dict(r)})
            cursor.execute("SELECT * FROM system_logs")
            for r in cursor.fetchall(): all_events.append({"timestamp": r["timestamp"], "type": "SYSTEM_LOG", "data": dict(r)})
            cursor.execute("SELECT * FROM users_tasks WHERE user_id = ?", (normalized_user_id,))
            tasks = [dict(r) for r in cursor.fetchall()]
            if tasks: all_events.append({"timestamp": "9999-12-31T23:59:59Z", "type": "TASK_SNAPSHOT", "data": tasks})
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}"); return

    if not all_events:
        print(f"No data found for user ID: {normalized_user_id}"); return

    # 3. Sort and Generate the Report
    all_events.sort(key=lambda x: x.get('timestamp', ''))
    local_tz = pytz.timezone(LOCAL_TIMEZONE)
    report_lines = [f"Kairo User Session Report for: {normalized_user_id}\n", "="*50, "\n"]

    # --- START OF FIX: Restructured loop to handle special cases ---
    for event in all_events:
        event_type = event['type']
        data = event['data']
        
        if event_type == "USER_PREFERENCES":
            report_lines.append(f"--- USER PREFERENCES (Initial State) ---\n")
            report_lines.append(pretty_print_json(json.dumps(data)) + "\n\n")
        
        elif event_type == "TASK_SNAPSHOT":
            report_lines.append(f"--- FINAL TASK SNAPSHOT ---\n")
            for i, task in enumerate(data):
                report_lines.append(f"  {i+1}. [{task.get('status', '?')}] {task.get('description', 'N/A')} (ID: {task.get('item_id')})\n")
            report_lines.append("\n")

        else: # Handle all regular, timestamped events
            ts = format_timestamp(event['timestamp'], local_tz)
            if event_type == "MESSAGE":
                report_lines.append(f"--- MESSAGE ---\n")
                report_lines.append(f"Timestamp: {ts}\n")
                report_lines.append(f"Role:      {data.get('role', 'N/A').upper()}\n")
                report_lines.append(f"Content:   {data.get('content', '')}\n\n")
            elif event_type == "TOOL_CALL":
                report_lines.append(f"--- TOOL CALL ---\n")
                report_lines.append(f"Timestamp: {ts}\n")
                report_lines.append(f"Tool Name: {data.get('tool_name', 'N/A')}\n")
                report_lines.append(f"Arguments:\n{pretty_print_json(data.get('tool_args_json', '{}'))}\n")
                report_lines.append(f"Result:\n{pretty_print_json(data.get('tool_result_json', '{}'))}\n\n")
            elif event_type == "SYSTEM_LOG":
                report_lines.append(f"--- SYSTEM LOG ---\n")
                report_lines.append(f"Timestamp: {ts}\n")
                report_lines.append(f"Level:     {data.get('level', 'N/A')}\n")
                report_lines.append(f"Module:    {data.get('module', 'N/A')}:{data.get('function', 'N/A')}\n")
                report_lines.append(f"Message:   {data.get('message', '')}\n")
                if data.get('traceback'):
                    report_lines.append(f"Traceback: {data.get('traceback')}\n")
                report_lines.append("\n")
    # --- END OF FIX ---
            
    # 4. Write to file
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.writelines(report_lines)
        print(f"✅ Success! Report generated: '{os.path.abspath(output_filename)}'")
    except IOError as e:
        print(f"❌ File Error: Could not write report. Reason: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export a user's full session data from Kairo to a readable .txt file.")
    parser.add_argument("phone_number", help="The user's phone number to export data for.")
    parser.add_argument("--mode", choices=['cli', 'wa'], default='wa', help="The database mode ('wa' for WhatsApp, 'cli' for testing). Defaults to 'wa'.")
    
    args = parser.parse_args()
    
    export_user_report(args.phone_number, args.mode)