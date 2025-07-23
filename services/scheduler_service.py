# services/scheduler_service.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
import pytz
from datetime import datetime

from tools.logger import log_info, log_error
import users.user_manager as user_manager
from bridge.request_router import handle_internal_system_event

scheduler: BackgroundScheduler | None = None
ROUTINE_CHECK_INTERVAL_MINUTES = 1

def _job_listener(event):
    if event.exception:
        log_error("scheduler_service", "_job_listener", f"Job crashed: {event.job_id}", event.exception)

def _check_and_trigger_routines():
    all_users_prefs = user_manager.get_all_user_data()
    for user_id, prefs in all_users_prefs.items():
        if prefs.get("status") != "active" or not prefs.get("timezone"):
            continue
        try:
            # --- START OF FIX: Handle 'work_days' and check for null times ---
            ritual_days = prefs.get("ritual_days", prefs.get("work_days", [])) # Backward compatibility
            morning_time = prefs.get("morning_muster_time")
            evening_time = prefs.get("evening_reflection_time")

            user_tz = pytz.timezone(prefs["timezone"])
            now_local = datetime.now(user_tz)
            
            if now_local.strftime("%A") not in ritual_days:
                continue

            current_local_hm = now_local.strftime("%H:%M")
            today_str = now_local.strftime("%Y-%m-%d")

            if morning_time and current_local_hm == morning_time and prefs.get("last_morning_trigger_date") != today_str:
                handle_internal_system_event({"user_id": user_id, "trigger_type": "morning_muster"})
                user_manager.update_user_preferences(user_id, {"last_morning_trigger_date": today_str})

            if evening_time and current_local_hm == evening_time and prefs.get("last_evening_trigger_date") != today_str:
                handle_internal_system_event({"user_id": user_id, "trigger_type": "evening_reflection"})
                user_manager.update_user_preferences(user_id, {"last_evening_trigger_date": today_str})
            # --- END OF FIX ---
        except Exception as e:
            log_error("scheduler_service", "_check_routines", f"Error processing routines for user {user_id}", e)

def _check_and_send_reminders():
    try:
        from services.notification_service import check_and_send_reminders as send_reminders_func
        send_reminders_func()
    except Exception as e:
        log_error("scheduler_service", "_check_reminders", "Error during reminder check", e)

def start_scheduler() -> bool:
    global scheduler
    if scheduler and scheduler.running: return True
    try:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(_check_and_trigger_routines, 'interval', minutes=ROUTINE_CHECK_INTERVAL_MINUTES, id='kairo_ritual_check')
        scheduler.add_job(_check_and_send_reminders, 'interval', minutes=ROUTINE_CHECK_INTERVAL_MINUTES, id='kairo_reminder_check')
        scheduler.add_listener(_job_listener, EVENT_JOB_ERROR)
        scheduler.start()
        log_info("scheduler_service", "start", "Scheduler started successfully.")
        return True
    except Exception as e:
        log_error("scheduler_service", "start", "Failed to start APScheduler", e)
        return False

def shutdown_scheduler():
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        log_info("scheduler_service", "shutdown", "Scheduler has been shut down.")