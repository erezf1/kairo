# tools/logger.py
import os
import pytz
from datetime import datetime, timezone
import traceback

# This module will now attempt to import the DB logging function when first used.
_activity_db_log_func = None
ACTIVITY_DB_IMPORTED = False

# --- Configuration ---
DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() in ('true', '1', 't')
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "kairo_app.log")
LOG_TIMEZONE_STR = "Asia/Jerusalem"

try:
    LOG_TIMEZONE_PYTZ = pytz.timezone(LOG_TIMEZONE_STR)
except pytz.UnknownTimeZoneError:
    print(f"[ERROR] [logger:init] Unknown Timezone '{LOG_TIMEZONE_STR}'. Defaulting to UTC.")
    LOG_TIMEZONE_PYTZ = pytz.utc

try:
    os.makedirs(LOG_DIR, exist_ok=True)
except OSError as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] [ERROR] [logger:init] Failed to create log directory '{LOG_DIR}': {e}")

# --- Helper Functions ---
def _timestamp_utc_iso():
    """Returns current time in UTC ISO format for DB logging."""
    return datetime.now(timezone.utc).isoformat()

def _format_log_entry(level: str, module: str, func: str, message: str):
    """Formats a log entry with the configured local timezone."""
    ts_aware = datetime.now(LOG_TIMEZONE_PYTZ)
    ts_formatted = ts_aware.strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"[{ts_formatted}] [{level.upper()}] [{module}:{func}] {message}"

def _try_log_to_db(level: str, module: str, function: str, message: str, traceback_str: str | None = None, timestamp_utc_iso: str | None = None):
    """Internal helper to dynamically import and call the DB logging function."""
    global _activity_db_log_func, ACTIVITY_DB_IMPORTED
    if not ACTIVITY_DB_IMPORTED:
        try:
            from tools.activity_db import log_system_event
            _activity_db_log_func = log_system_event
            ACTIVITY_DB_IMPORTED = True
        except ImportError:
            _activity_db_log_func = None

    if _activity_db_log_func:
        try:
            db_ts = timestamp_utc_iso or _timestamp_utc_iso()
            _activity_db_log_func(
                level=level.upper(),
                module=module,
                function=function,
                message=message,
                traceback_str=traceback_str,
                timestamp=db_ts
            )
        except Exception as db_log_err:
            print(f"CRITICAL DB LOG FAIL: {db_log_err} | Original Msg: {message}")

# --- Public Logging Functions ---
def log_info(module: str, func: str, message: str):
    """Logs informational messages to the console in debug mode."""
    if DEBUG_MODE:
        print(_format_log_entry("INFO", module, func, message))

def log_error(module: str, func: str, message: str, exception: Exception | None = None):
    """Logs error messages to console/file and attempts to log to the database."""
    level = "ERROR"
    traceback_str = traceback.format_exc() if exception else None
    entry = _format_log_entry(level, module, func, message)
    
    print(entry)
    if traceback_str:
        print(traceback_str)
    
    _try_log_to_db(level, module, func, message, traceback_str, _timestamp_utc_iso())

def log_warning(module: str, func: str, message: str):
    """Logs warning messages to console/file and attempts to log to the database."""
    level = "WARNING"
    entry = _format_log_entry(level, module, func, message)
    print(entry)
    _try_log_to_db(level, module, func, message, None, _timestamp_utc_iso())