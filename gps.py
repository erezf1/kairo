# gps.py - Generate Project Snapshot for Kairo
import os
from datetime import datetime
from pathlib import Path

# --- Configuration ---
# This list contains only the files required for the final Kairo MVP.
# Obsolete files have been removed.
FILES_TO_DUMP = [
    # Root Files
    "requirements.txt",
    "package.json",
    ".gitignore",

    # Core Application & Logic
    "main.py",
    "agents/kairo_agent.py",
    "agents/tool_definitions.py",
    "bridge/request_router.py",
    "services/llm_interface.py",
    "services/notification_service.py",
    "services/scheduler_service.py",
    "services/task_manager.py",
    "services/cheats.py",
    "services/shared_resources.py",

    # Data & User Management (The new single source of truth)
    "tools/activity_db.py",
    "users/user_manager.py",

    # Bridge Interfaces
    "bridge/cli_interface.py",
    "bridge/twilio_interface.py",
    "bridge/whatsapp_interface.py",
    "WA/wa_bridge.js",

    # Configuration Files
    "config/prompts.yaml",
    "config/messages.yaml",
    "config/settings.yaml",

    # Utilities & Scripts
    "tools/logger.py",
    "gps.py", # The script itself
    "session_viewer.py", # The debug tool

    # Testing
    "tests/mock_browser_chat.py",
    "tests/templates/browser_chat.html",
]

OUTPUT_FILENAME_PATTERN = "kairo_mvp_snapshot.txt"
SEPARATOR = "=" * 80
# --- End Configuration ---

def generate_dump(output_filename: str, files_to_include: list):
    """Generates the project dump file."""
    project_root = Path(__file__).parent
    dump_content = []
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dump_content.append(f"# Kairo Project Code Dump (v1.0 MVP)")
    dump_content.append(f"# Generated: {timestamp_str}\n\n")

    for relative_path_str in files_to_include:
        full_path = project_root / Path(relative_path_str)
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding='utf-8', errors='replace')
                header_path = Path(relative_path_str).as_posix()
                dump_content.append(SEPARATOR)
                dump_content.append(f"📄 {header_path}")
                dump_content.append(SEPARATOR)
                dump_content.append(f"\n# --- START OF FILE {header_path} ---\n")
                dump_content.append(content)
                dump_content.append(f"\n# --- END OF FILE {header_path} ---\n\n\n")
                print(f"✅ Included: {header_path}")
            except Exception as e:
                print(f"❌ Error reading {relative_path_str}: {e}")
        else:
            print(f"⚠️  Skipped (Not Found): {relative_path_str}")

    try:
        (project_root / output_filename).write_text("\n".join(dump_content), encoding='utf-8')
        print(f"\n✅ Dump generated successfully: {output_filename}")
    except Exception as e:
        print(f"\n❌ Error writing dump file {output_filename}: {e}")

if __name__ == "__main__":
    generate_dump(OUTPUT_FILENAME_PATTERN, FILES_TO_DUMP)