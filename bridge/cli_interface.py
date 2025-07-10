# bridge/cli_interface.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
from threading import Lock
import json

from tools.logger import log_info, log_error, log_warning

# Optional calendar tool import
try:
    from tools.calendar_tool import router as calendar_router
    CALENDAR_ROUTER_IMPORTED = True
except ImportError:
    CALENDAR_ROUTER_IMPORTED = False
    from fastapi import APIRouter
    calendar_router = APIRouter()

# Global in-memory store for CLI outgoing messages
outgoing_cli_messages = []
cli_queue_lock = Lock()

class CLIBridge:
    """Bridge that handles message queuing for CLI interaction."""
    def __init__(self, message_queue, lock):
        self.message_queue = message_queue
        self.lock = lock
        log_info("CLIBridge", "__init__", "CLI Bridge initialized for queuing.")

    def send_message(self, user_id: str, message: str):
        if not user_id or not message:
             log_warning("CLIBridge", "send_message", "Attempted to queue empty message or invalid user_id.")
             return
        outgoing = {"user_id": user_id, "message": message, "message_id": str(uuid.uuid4())}
        with self.lock:
            self.message_queue.append(outgoing)
        log_info("CLIBridge", "send_message", f"Message for CLI user {user_id} queued. Queue size: {len(self.message_queue)}")

async def process_incoming_cli_message_background(user_id: str, message: str):
    """Runs the message handler in the background."""
    try:
        from bridge.request_router import handle_incoming_message
        handle_incoming_message(user_id, message)
    except Exception as e:
        log_error("cli_interface", "background_task", f"Unhandled exception in CLI background processing for {user_id}", e)

def create_cli_app() -> FastAPI:
    """Creates the FastAPI app instance for the CLI Interface."""
    app = FastAPI(
        title="Kairo CLI Bridge API",
        description="Handles interaction for the CLI mock sender.",
        version="1.0.0"
    )

    if CALENDAR_ROUTER_IMPORTED:
        app.include_router(calendar_router, prefix="", tags=["Authentication"])

    @app.post("/incoming", tags=["CLI Bridge"])
    async def incoming_cli_message(request: Request, background_tasks: BackgroundTasks):
        """Receives message from CLI mock, acknowledges, and processes in the background."""
        endpoint_name = "incoming_cli_message"
        try:
            data = await request.json()
            user_id = data.get("user_id")
            message = data.get("message")
            if not user_id or message is None:
                raise HTTPException(status_code=400, detail="Missing user_id or message")
            background_tasks.add_task(process_incoming_cli_message_background, user_id, str(message))
            log_info("cli_interface", endpoint_name, f"ACK for incoming from {user_id}. Processing in background.")
            return JSONResponse(content={"ack": True})
        except Exception as e:
            log_error("cli_interface", endpoint_name, "Error processing incoming CLI message", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    # --- START OF FIX: Implement robust ACK mechanism ---
    @app.get("/outgoing", tags=["CLI Bridge"])
    async def get_outgoing_cli_messages():
        """
        Returns a COPY of the outgoing message queue.
        It NO LONGER clears the queue. Deletion is handled by /ack.
        """
        with cli_queue_lock:
            # Return a copy of the list, but leave the original intact
            msgs_to_send = outgoing_cli_messages[:]
        return JSONResponse(content={"messages": msgs_to_send})

    @app.post("/ack", tags=["CLI Bridge"])
    async def acknowledge_cli_message(request: Request):
        """
        Receives acknowledgment and REMOVES the message from the queue.
        This is now the only way messages are deleted.
        """
        endpoint_name = "acknowledge_cli_message"
        removed = False
        message_id = None
        try:
            data = await request.json()
            message_id = data.get("message_id")
            if not message_id:
                raise HTTPException(status_code=400, detail="Missing message_id in ACK")

            with cli_queue_lock:
                # Find the message by ID and remove it
                initial_len = len(outgoing_cli_messages)
                # Create a new list excluding the acknowledged message
                outgoing_cli_messages[:] = [msg for msg in outgoing_cli_messages if msg.get("message_id") != message_id]
                final_len = len(outgoing_cli_messages)
                removed = (initial_len != final_len)
            
            if removed:
                log_info(endpoint_name, "ack", f"ACK received and message removed for ID: {message_id}. Queue size: {len(outgoing_cli_messages)}")
            else:
                log_warning(endpoint_name, "ack", f"ACK received for unknown/already removed message ID: {message_id}")

            return JSONResponse(content={"ack_received": True, "removed": removed})
        except Exception as e:
            log_error(endpoint_name, "ack", f"Error processing ACK for message ID {message_id or 'N/A'}", e)
            raise HTTPException(status_code=500, detail="Internal server error processing ACK")
    # --- END OF FIX ---

    return app

app = create_cli_app()