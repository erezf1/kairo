# bridge/whatsapp_interface.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
from threading import Lock
import json
import re

from tools.logger import log_info, log_error, log_warning
from bridge.request_router import handle_incoming_message

try:
    from tools.calendar_tool import router as calendar_router
    CALENDAR_ROUTER_IMPORTED = True
except ImportError:
    CALENDAR_ROUTER_IMPORTED = False
    from fastapi import APIRouter
    calendar_router = APIRouter()

# --- Bridge Definition ---
outgoing_whatsapp_messages = []
whatsapp_queue_lock = Lock()

class WhatsAppBridge:
    def __init__(self, message_queue, lock):
        self.message_queue = message_queue
        self.lock = lock
        log_info("WhatsAppBridge", "__init__", "WhatsApp Bridge initialized for queuing.")

    def send_message(self, user_id: str, message: str):
        if not user_id or not message:
             log_warning("WhatsAppBridge", "send_message", "Attempted to queue empty message or invalid user_id.")
             return
        formatted_user_id = f"{user_id}@c.us" if re.match(r'^\d+$', user_id) else user_id
        outgoing = {"user_id": formatted_user_id, "message": message, "message_id": str(uuid.uuid4())}
        with self.lock:
            self.message_queue.append(outgoing)
        log_info("WhatsAppBridge", "send_message", f"Message queued for {formatted_user_id}. Queue size: {len(self.message_queue)}")

# --- START OF FIX: Pass message_id to the handler ---
async def process_incoming_message_background(user_id: str, message: str, message_id: str | None):
    """Runs the message handler in the background, passing the unique message_id."""
    try:
        handle_incoming_message(user_id, message, message_id)
    except Exception as e:
        log_error("whatsapp_interface", "background_task", f"Exception in background processing for {user_id}", e)
# --- END OF FIX ---

def create_whatsapp_app() -> FastAPI:
    app = FastAPI(title="Kairo WhatsApp Bridge API", version="1.0.0")
    if CALENDAR_ROUTER_IMPORTED:
        app.include_router(calendar_router, prefix="", tags=["Authentication"])

    @app.post("/incoming", tags=["WhatsApp Bridge"])
    async def incoming_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
        data = await request.json()
        user_id = data.get("user_id")
        message_body = data.get("message")
        # --- START OF FIX: Get message_id from the payload ---
        message_id = data.get("message_id") # This can be None if the bridge is old
        # --- END OF FIX ---

        if not user_id or message_body is None:
            raise HTTPException(status_code=400, detail="Missing user_id or message")
        
        # --- START OF FIX: Pass message_id to the background task ---
        background_tasks.add_task(process_incoming_message_background, user_id, str(message_body), message_id)
        # --- END OF FIX ---

        log_info("whatsapp_interface", "incoming", f"ACK for incoming from {user_id}. Processing in background.")
        return JSONResponse(content={"ack": True})

    @app.get("/outgoing", tags=["WhatsApp Bridge"])
    async def get_outgoing_whatsapp_messages():
        with whatsapp_queue_lock:
            return JSONResponse(content={"messages": outgoing_whatsapp_messages[:]})

    @app.post("/ack", tags=["WhatsApp Bridge"])
    async def acknowledge_whatsapp_message(request: Request):
        data = await request.json()
        message_id = data.get("message_id")
        if not message_id:
            raise HTTPException(status_code=400, detail="Missing message_id")
        removed = False
        with whatsapp_queue_lock:
            initial_len = len(outgoing_whatsapp_messages)
            outgoing_whatsapp_messages[:] = [msg for msg in outgoing_whatsapp_messages if msg.get("message_id") != message_id]
            if len(outgoing_whatsapp_messages) != initial_len:
                removed = True
                log_info("whatsapp_interface", "ack", f"ACK received and message removed for ID: {message_id}")
        return JSONResponse(content={"ack_received": True, "removed": removed})

    return app

app = create_whatsapp_app()