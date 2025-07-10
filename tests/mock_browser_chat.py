# tests/mock_browser_chat.py
import os
import requests
import json
import time
import threading
from flask import Flask, render_template, request, jsonify
from collections import deque
from datetime import datetime
from dotenv import load_dotenv
import logging

# --- Configuration ---
load_dotenv()
VIEWER_PORT = int(os.getenv("VIEWER_PORT", "5001"))
MAX_MESSAGES = 100
MAIN_BACKEND_PORT = os.getenv("PORT", "8001")
MAIN_BACKEND_BASE_URL = f"http://localhost:{MAIN_BACKEND_PORT}"
MAIN_BACKEND_OUTGOING_URL = f"{MAIN_BACKEND_BASE_URL}/outgoing"
MAIN_BACKEND_ACK_URL = f"{MAIN_BACKEND_BASE_URL}/ack"
MOCK_USER_ID = "1234"

# --- State ---
message_store_bot = deque(maxlen=MAX_MESSAGES)
message_lock = threading.Lock()
_stop_polling_event = threading.Event()

# --- Flask App Setup ---
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

def mock_log(level, component, message):
    """Custom logger to print formatted messages to the console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level.upper()}] [MockChat:{component}] {message}")

# --- START OF FIX: Refactored Polling Function ---
def poll_main_backend():
    """Polls the Kairo backend for outgoing messages."""
    session = requests.Session()
    while not _stop_polling_event.is_set():
        try:
            res = session.get(MAIN_BACKEND_OUTGOING_URL, timeout=5)
            res.raise_for_status()
            data = res.json()
            
            messages_from_backend = data.get("messages", [])
            
            if not messages_from_backend:
                time.sleep(1) # Wait a second if the queue is empty
                continue

            # If we get here, messages were found.
            mock_log("info", "PollingThread", f"Found {len(messages_from_backend)} message(s) in payload from Kairo.")
            
            for msg_data in messages_from_backend:
                # Log every message received, regardless of user ID for debugging
                mock_log("info", "PollingThread", f"RECEIVED: User='{msg_data.get('user_id')}', Msg='{msg_data.get('message', '')[:70]}...'")
                
                # Process only messages for our simulated user
                if msg_data.get('user_id') == MOCK_USER_ID:
                    with message_lock:
                        message_store_bot.appendleft({
                            "sender": "bot",
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "content": msg_data.get('message'),
                            "id": msg_data.get('message_id')
                        })
                    
                    # Acknowledge the message was processed
                    session.post(MAIN_BACKEND_ACK_URL, json={"message_id": msg_data.get('message_id'), "user_id": MOCK_USER_ID}, timeout=3)
        
        except requests.exceptions.RequestException:
            # This happens if the backend is down, wait before retrying.
            time.sleep(2)
        except Exception as e:
            mock_log("error", "PollingThread", f"An unexpected error occurred in polling loop: {e}")
            time.sleep(5)
# --- END OF FIX ---

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('browser_chat.html', title=f"Kairo Mock Chat (User: {MOCK_USER_ID})")

@app.route('/send_message', methods=['POST'])
def send_message_route():
    data = request.get_json()
    message_text = data.get('message')
    if not message_text:
        return jsonify({"status": "error", "message": "No message"}), 400

    backend_payload = {"user_id": MOCK_USER_ID, "message": message_text}
    mock_log("info", "SendRoute", f"SENDING to Kairo backend: '{message_text}'")
    try:
        requests.post(f"{MAIN_BACKEND_BASE_URL}/incoming", json=backend_payload, timeout=120)
        return jsonify({"status": "ok"}), 200
    except requests.exceptions.RequestException:
        return jsonify({"status": "error", "message": "Could not connect to Kairo backend."}), 503

@app.route('/get_messages')
def get_messages_route():
    with message_lock:
        return jsonify({"messages": list(message_store_bot)})

@app.route('/clear_messages', methods=['POST'])
def clear_messages_route():
    with message_lock:
        message_store_bot.clear()
    return jsonify({"status": "ok"})

# --- Main Execution ---
if __name__ == '__main__':
    mock_log("info", "Main", "--- Starting Kairo Mock Browser Chat ---")
    user_input_id_raw = input(f"Enter User ID to simulate (leave blank for '{MOCK_USER_ID}'): ").strip()
    if user_input_id_raw: MOCK_USER_ID = user_input_id_raw
    mock_log("info", "Main", f"Simulating as User ID: {MOCK_USER_ID}")
    
    polling_thread = threading.Thread(target=poll_main_backend, daemon=True)
    polling_thread.start()
    
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', port=VIEWER_PORT, debug=False, use_reloader=False)