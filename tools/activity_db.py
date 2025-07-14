# tools/activity_db.py
import sqlite3
import os
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any

from tools.logger import log_info, log_error

# Configuration
DATA_SUFFIX = os.getenv("DATA_SUFFIX", "")
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, f"kairo_activity{DATA_SUFFIX}.db")
DB_LOCK = threading.Lock()

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    with DB_LOCK, sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users_tasks (
            item_id TEXT PRIMARY KEY NOT NULL, user_id TEXT NOT NULL, type TEXT NOT NULL,
            status TEXT NOT NULL, description TEXT NOT NULL, project TEXT, due_date TEXT,
            remind_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id_status ON users_tasks (user_id, status)")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, user_id TEXT NOT NULL,
            role TEXT NOT NULL, message_type TEXT NOT NULL, content TEXT
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id_ts ON messages (user_id, timestamp)")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, user_id TEXT NOT NULL,
            tool_name TEXT NOT NULL, tool_args_json TEXT NOT NULL, tool_result_json TEXT NOT NULL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, level TEXT NOT NULL,
            module TEXT NOT NULL, function TEXT NOT NULL, message TEXT NOT NULL, traceback TEXT
        )""")
        conn.commit()
    log_info("activity_db", "init_db", f"Database initialized at {DB_FILE}")

def _dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def add_or_update_item(item_data: Dict) -> bool:
    item_id = item_data.get("item_id")
    if not item_id: return False
    columns = list(item_data.keys()); placeholders = ', '.join('?'*len(columns))
    update_setters = ', '.join([f"{col}=excluded.{col}" for col in columns if col != 'item_id'])
    sql = f"INSERT INTO users_tasks ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT(item_id) DO UPDATE SET {update_setters}"
    try:
        with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
            conn.execute(sql, list(item_data.values())); conn.commit()
        return True
    except sqlite3.Error as e:
        log_error("activity_db", "add_or_update_item", f"DB error for item {item_id}", e); return False

def get_item(item_id: str) -> Dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = _dict_factory
            return conn.execute("SELECT * FROM users_tasks WHERE item_id = ?", (item_id,)).fetchone()
    except sqlite3.Error as e:
        log_error("activity_db", "get_item", f"DB error for item {item_id}", e); return None

def list_items_for_user(user_id: str, status_filter: List[str] | None = None) -> List[Dict]:
    sql = "SELECT * FROM users_tasks WHERE user_id = ?"; params: List[Any] = [user_id]
    if status_filter:
        placeholders = ','.join('?'*len(status_filter)); sql += f" AND status IN ({placeholders})"; params.extend(status_filter)
    sql += " ORDER BY created_at DESC"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = _dict_factory; return conn.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        log_error("activity_db", "list_items_for_user", f"DB error for {user_id}", e); return []

def get_recent_messages(user_id: str, limit: int = 10) -> List[Dict]:
    """Fetches the most recent messages for a user to provide conversation history."""
    sql = """
        SELECT role, content FROM messages
        WHERE user_id = ? AND message_type IN ('user_text', 'agent_text_response')
        ORDER BY timestamp DESC
        LIMIT ?
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = _dict_factory
            messages = conn.execute(sql, (user_id, limit)).fetchall()
            return list(reversed(messages))
    except sqlite3.Error as e:
        log_error("activity_db", "get_recent_messages", f"DB error for {user_id}", e)
        return []

def log_message(user_id: str, role: str, message_type: str, content: str):
    ts = datetime.now(timezone.utc).isoformat()
    sql = "INSERT INTO messages (timestamp, user_id, role, message_type, content) VALUES (?, ?, ?, ?, ?)"
    try:
        with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
            conn.execute(sql, (ts, user_id, role, message_type, content)); conn.commit()
    except sqlite3.Error as e:
        log_error("activity_db", "log_message", f"DB error for {user_id}", e)

def log_llm_activity(user_id: str, tool_name: str, tool_args: Dict, tool_result: Dict):
    ts = datetime.now(timezone.utc).isoformat()
    sql = "INSERT INTO llm_activity (timestamp, user_id, tool_name, tool_args_json, tool_result_json) VALUES (?, ?, ?, ?, ?)"
    try:
        with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
            conn.execute(sql, (ts, user_id, tool_name, json.dumps(tool_args), json.dumps(tool_result))); conn.commit()
    except sqlite3.Error as e:
        log_error("activity_db", "log_llm_activity", f"DB error for {user_id}", e)

def log_system_event(level: str, module: str, function: str, message: str, traceback_str: str | None = None, timestamp: str | None = None):
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    params = (ts, level.upper(), module, function, message, traceback_str)
    sql = "INSERT INTO system_logs (timestamp, level, module, function, message, traceback) VALUES (?, ?, ?, ?, ?, ?)"
    try:
        with DB_LOCK, sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
            conn.execute(sql, params); conn.commit()
    except sqlite3.Error as e:
        print(f"CRITICAL DB LOGGING FAILED: {ts} [{level.upper()}] {module}:{function} - {message}\n{e}")