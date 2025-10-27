"""
Job: Notify Changes
Detects event changes and sends notifications.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from notifier import Notifier
from chronos_parser import ChronosEvent
from database import Database
from config_loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def dict_to_event(event_dict):
    """Convert database dict to ChronosEvent object."""
    # Reconstruct event_data dict for ChronosEvent constructor
    event_data = {
        'p_id': event_dict['event_id'],
        'p_start': event_dict['start_time'],
        'p_end': event_dict['end_time'],
        'p_allday': 'true' if event_dict['all_day'] else 'false',
        'p_cod': event_dict['code'],
        'p_lib': event_dict['lib'],
        'p_tpm': event_dict['duration_hours'],
        'p_title': event_dict['title']
    }
    return ChronosEvent(event_data)


def format_event_time(event):
    """Format event time in French."""
    if not event.start:
        return "Date inconnue"
    
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    months = ['Jan', 'Fév', 'Mars', 'Avr', 'Mai', 'Juin', 
              'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
    
    day_name = days[event.start.weekday()]
    month_name = months[event.start.month - 1]
    
    if event.all_day:
        return f"{day_name} {event.start.day:02d} {month_name}"
    else:
        time_str = f"{event.start.strftime('%H:%M')}-{event.end.strftime('%H:%M')}"
        return f"{day_name} {event.start.day:02d} {month_name} {time_str}"


def detect_and_notify_changes():
    """Detect changes and send notifications."""
    db = Database()
    log_id = db.start_sync_log('notify_changes')
    
    try:
        logger.info("="*50)
        logger.info("JOB: Notify Changes - STARTED")
        logger.info("="*50)
        
        # Load configuration
        config = load_config()
        
        # Check if notifications are enabled
        if not config['notifications']['enabled']:
            logger.info("Notifications disabled in config")
            db.complete_sync_log(log_id, 'skipped', 0)
            logger.info("="*50)
            return True
        
        # Initialize notifier
        notifier = Notifier(
            topic=config['notifications']['ntfy_topic'],
            server=config['notifications']['ntfy_server'],
            enabled=True
        )
        
        # Get current events (future only)
        now = datetime.now()
        future_end = now + timedelta(days=config['sync']['days_ahead'])
        current_events_dicts = db.get_events(start_date=now, end_date=future_end)
        current_events = [dict_to_event(e) for e in current_events_dicts]
        
        # Get previous state
        previous_state = db.get_setting('previous_events_state', {})
        
        # Convert to dict for comparison (key = unique_id)
        current_dict = {e.get_unique_id(): e for e in current_events}
        previous_dict = previous_state if isinstance(previous_state, dict) else {}
        
        changes_notified = 0
        
        # Detect new events
        for unique_id, event in current_dict.items():
            if unique_id not in previous_dict:
                title = event.get_calendar_title()
                time_str = format_event_time(event)
                
                logger.info(f"📱 New event: {title} at {time_str}")
                
                # Record change in DB
                db.record_change('new', event.event_id, title, None, time_str)
                
                # Send notification
                if event.all_day:
                    notifier.send_new_shift(title, time_str)
                else:
                    parts = time_str.split()
                    date_part = ' '.join(parts[:3]) if len(parts) >= 3 else time_str
                    time_part = parts[-1] if len(parts) >= 4 else None
                    notifier.send_new_shift(title, date_part, time_part)
                
                changes_notified += 1
        
        # Detect deleted events
        for unique_id, prev_data in previous_dict.items():
            if unique_id not in current_dict:
                # Reconstruct event from previous data
                if isinstance(prev_data, dict):
                    title = prev_data.get('title', 'Unknown')
                    time_str = prev_data.get('time_str', 'Unknown time')
                else:
                    # Old format - skip
                    continue
                
                logger.info(f"📱 Deleted event: {title} at {time_str}")
                
                # Record change in DB
                db.record_change('deleted', unique_id, title, time_str, None)
                
                # Send notification
                notifier.send_deleted_shift(title, time_str)
                changes_notified += 1
        
        # Detect modified events
        for unique_id, event in current_dict.items():
            if unique_id in previous_dict:
                prev_data = previous_dict[unique_id]
                if isinstance(prev_data, dict):
                    prev_time = prev_data.get('time_str', '')
                    curr_time = format_event_time(event)
                    
                    if prev_time != curr_time:
                        title = event.get_calendar_title()
                        logger.info(f"📱 Modified event: {title}")
                        
                        # Record change in DB
                        db.record_change('modified', event.event_id, title, prev_time, curr_time)
                        
                        # Send notification
                        notifier.send_modified_shift(title, prev_time, curr_time)
                        changes_notified += 1
        
        # Save current state for next comparison
        new_state = {}
        for unique_id, event in current_dict.items():
            new_state[unique_id] = {
                'title': event.get_calendar_title(),
                'time_str': format_event_time(event)
            }
        db.set_setting('previous_events_state', new_state)
        
        # Complete sync log
        db.complete_sync_log(log_id, 'success', changes_notified)
        
        logger.info("="*50)
        logger.info(f"JOB: Notify Changes - SUCCESS ({changes_notified} notifications sent)")
        logger.info("="*50)
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Notify changes job failed: {error_msg}", exc_info=True)
        db.complete_sync_log(log_id, 'failed', 0, error_msg)
        logger.info("="*50)
        return False
    
    finally:
        db.close()


if __name__ == '__main__':
    # Run as standalone script
    detect_and_notify_changes()
