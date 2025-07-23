# bridge/twilio_interface.py
from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks
from fastapi.responses import Response as FastAPIResponse
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
import os

from tools.logger import log_info, log_error
# --- THIS IS THE FIX: 'set_bridge' is removed ---
from bridge.request_router import handle_incoming_message

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None

class TwilioBridge:
    """Bridge for Twilio WhatsApp interactions."""
    def __init__(self, client: TwilioClient, twilio_sender_number: str):
        self.client = client
        self.twilio_sender_number = twilio_sender_number
        log_info("TwilioBridge", "__init__", "Twilio Bridge instance initialized.")

    def send_message(self, user_id: str, message_body: str):
        if not self.client or not self.twilio_sender_number:
            log_error("twilio_interface", "send", "Twilio client or sender number not configured.")
            return
        twilio_recipient_id = f"whatsapp:+{user_id}"
        try:
            message_instance = self.client.messages.create(from_=self.twilio_sender_number, body=message_body, to=twilio_recipient_id)
            log_info("twilio_interface", "send", f"Twilio message sent. SID: {message_instance.sid}")
        except Exception as e:
            log_error("twilio_interface", "send", f"Error sending Twilio message to {twilio_recipient_id}", e)

async def process_incoming_twilio_message_background(user_id: str, message: str):
    """Runs the message handler in the background."""
    try:
        handle_incoming_message(user_id, message)
    except Exception as e:
        log_error("twilio_interface", "background_task", f"Exception in background processing for {user_id}", e)

def create_twilio_app() -> FastAPI:
    app_instance = FastAPI(title="Kairo Twilio Bridge API", version="1.0.0")
    # Optional calendar router import can be added here if needed

    @app_instance.post("/twilio/incoming", tags=["Twilio Bridge"])
    async def incoming_twilio_message(request: Request, background_tasks: BackgroundTasks, From: str = Form(...), Body: str = Form(...)):
        # Optional signature validation
        if twilio_validator:
            # (Validation logic would go here)
            pass
        
        background_tasks.add_task(process_incoming_twilio_message_background, From, Body)
        log_info("twilio_interface", "incoming", f"ACK for Twilio from {From}. Processing in background.")
        return FastAPIResponse(content="<Response/>", media_type="application/xml")
    
    return app_instance

app = create_twilio_app()