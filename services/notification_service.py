# services/notification_service.py
from datetime import datetime, timezone, timedelta
from tools.logger import log_info, log_error, log_warning
from users.user_manager import get_all_user_data
from bridge.request_router import send_message
import tools.activity_db as db  # Use the database directly
import services.task_manager as task_manager # For updating the item status

NOTIFICATION_TRANSLATIONS = {
    "en": {"reminder_alert": "🔔 Reminder: {description}"},
    "he": {"reminder_alert": "🔔 תזכורת: {description}"}
}

def _get_notification_translation(lang: str, key: str) -> str:
    """Fetches a translation string for notifications."""
    return NOTIFICATION_TRANSLATIONS.get(lang, {}).get(key, "{description}")

def check_and_send_reminders():
    """
    Scheduled job that iterates through all users, checks for due reminders
    in the database, and sends notifications.
    """
    fn_name = "check_and_send_reminders"
    now_utc = datetime.now(timezone.utc)
    all_user_prefs = get_all_user_data()

    for user_id, prefs in all_user_prefs.items():
        if prefs.get("status") != "active":
            continue

        try:
            # Fetch 'new' reminders for this specific user from the database
            reminders_to_check = db.list_items_for_user(user_id, status_filter=["new"])
            
            for item in reminders_to_check:
                if item.get("type") != "reminder" or not item.get("remind_at"):
                    continue

                item_id = item.get("item_id")
                remind_at_utc = datetime.fromisoformat(item["remind_at"].replace('Z', '+00:00'))
                
                # Send notification if the reminder time is in the past or within the next minute
                if remind_at_utc <= (now_utc + timedelta(minutes=1)):
                    user_lang = prefs.get("language", "en")
                    description = item.get("description", "(No Title)")
                    
                    template = _get_notification_translation(user_lang, "reminder_alert")
                    message = template.format(description=description)
                    
                    log_info(fn_name, "notification_service", f"Sending reminder '{item_id}' to user {user_id}")
                    send_message(user_id, message)
                    
                    # Mark the reminder as complete in the database
                    task_manager.update_item(user_id, item_id, {"status": "completed"})

        except (ValueError, TypeError) as e:
            log_warning(fn_name, "notification_service", f"Could not parse date for a reminder for user {user_id}. Error: {e}")
        except Exception as e:
            log_error(fn_name, "notification_service", f"Error processing reminders for user {user_id}", e)