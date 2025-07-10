# main.py
import os
import sys
import asyncio
import signal
import argparse
from dotenv import load_dotenv
import traceback

# Load .env first
load_dotenv()

# --- START OF CHANGE: Set BRIDGE_TYPE as an environment variable ---
# This makes the bridge choice globally accessible to any module in any process.
DEFAULT_BRIDGE = "cli"
ALLOWED_BRIDGES = ["cli", "whatsapp", "twilio"]
parser = argparse.ArgumentParser(description="Run the Kairo Productivity Coach Backend")
parser.add_argument("--bridge", type=str, choices=ALLOWED_BRIDGES, help=f"Specify the bridge interface ({', '.join(ALLOWED_BRIDGES)})")
args = parser.parse_args()

cli_arg = args.bridge.lower() if args.bridge else None
env_var = os.getenv("BRIDGE_TYPE", "").lower()
# Priority for setting bridge type: CLI argument > Environment variable > Default
bridge_type = cli_arg or env_var or DEFAULT_BRIDGE
os.environ["BRIDGE_TYPE"] = bridge_type
# --- END OF CHANGE ---

# Import other modules after setting the environment
from tools.activity_db import init_db
init_db()  # Initialize DB before any other service
from tools.logger import log_info, log_error, log_warning

import uvicorn
from users.user_manager import init_all_agents
from services.scheduler_service import start_scheduler, shutdown_scheduler

# Determine which FastAPI app to run based on the configured bridge
UVICORN_APP_MAP = {
    "cli": "bridge.cli_interface:app",
    "whatsapp": "bridge.whatsapp_interface:app",
    "twilio": "bridge.twilio_interface:app"
}
uvicorn_app_path = UVICORN_APP_MAP.get(bridge_type)

if not uvicorn_app_path:
    log_error("main", "init", f"Invalid bridge type '{bridge_type}' configured. Exiting.")
    sys.exit(1)

log_info("main", "init", f"Kairo v1.0 starting with bridge: '{bridge_type}'")

# Graceful shutdown handler remains the same
server: uvicorn.Server | None = None
async def handle_shutdown_signal(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
    log_warning("main", "shutdown", f"Received signal {sig.name}. Initiating shutdown...")
    if server:
        server.should_exit = True
    await asyncio.sleep(1)
    shutdown_scheduler()

async def main_async():
    global server
    log_info("main", "startup", "Initializing agent states...")
    init_all_agents()
    log_info("main", "startup", "Agent state initialization complete.")

    log_info("main", "startup", "Starting scheduler service...")
    if not start_scheduler():
        log_error("main", "startup", "Scheduler service FAILED to start.")
    else:
        log_info("main", "startup", "Scheduler service started successfully.")

    reload_enabled = os.getenv("APP_ENV", "production").lower() == "development"
    log_level = "debug" if reload_enabled else "info"
    server_port = int(os.getenv("PORT", "8001")) # Changed default port to 8001

    log_info("main", "startup", "Configuring FastAPI server...")
    config = uvicorn.Config(
        uvicorn_app_path, host="0.0.0.0", port=server_port,
        reload=reload_enabled, access_log=False, log_level=log_level, lifespan="on"
    )
    server = uvicorn.Server(config)

    loop = asyncio.get_running_loop()
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig_name, lambda s=sig_name: asyncio.create_task(handle_shutdown_signal(s, loop)))
        except NotImplementedError:
             signal.signal(sig_name, lambda s, f: asyncio.create_task(handle_shutdown_signal(signal.Signals(s), loop)))

    await server.serve()
    log_info("main", "shutdown", "Server has stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        log_warning("main", "exit", "Application exit requested.")
    except Exception as e:
        log_error("main", "critical", "Unhandled error during server execution.", e)
        traceback.print_exc()
        sys.exit(1)
    finally:
        log_info("main", "exit", "Application has shut down.")