"""
Job: Sync Calendar
Runs every 15-30 minutes to sync events from database to iCloud calendar.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from calendar_sync import CalendarSync
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


def sync_calendar():
    """Sync events from database to iCloud calendar."""
    db = Database()
    log_id = db.start_sync_log('sync_calendar')
    
    try:
        logger.info("="*50)
        logger.info("JOB: Sync Calendar - STARTED")
        logger.info("="*50)
        
        # Load configuration
        config = load_config()
        
        # Get events from database (only future events)
        now = datetime.now()
        future_end = now + timedelta(days=config['sync']['days_ahead'])
        
        logger.info(f"Loading events from DB: {now.date()} to {future_end.date()}")
        event_dicts = db.get_events(start_date=now, end_date=future_end)
        
        if not event_dicts:
            logger.warning("No events found in database to sync")
            db.complete_sync_log(log_id, 'success', 0)
            logger.info("="*50)
            return True
        
        # Convert to ChronosEvent objects
        events = [dict_to_event(e) for e in event_dicts]
        logger.info(f"Loaded {len(events)} events from database")
        
        # Initialize calendar sync
        cal_sync = CalendarSync(
            url=config['icalendar']['url'],
            username=config['icalendar']['username'],
            password=config['icalendar']['password'],
            calendar_name=config['icalendar']['calendar_name']
        )
        
        # Connect to calendar
        logger.info("Connecting to iCloud calendar...")
        if not cal_sync.connect():
            raise Exception("Failed to connect to calendar")
        
        # Sync events
        logger.info(f"Syncing {len(events)} events to calendar...")
        if not cal_sync.sync_events(events):
            raise Exception("Failed to sync events")
        
        # Update last sync time
        db.set_setting('last_calendar_sync', datetime.now().isoformat())
        
        # Complete sync log
        db.complete_sync_log(log_id, 'success', len(events))
        
        logger.info("="*50)
        logger.info(f"JOB: Sync Calendar - SUCCESS ({len(events)} events)")
        logger.info("="*50)
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Calendar sync job failed: {error_msg}", exc_info=True)
        db.complete_sync_log(log_id, 'failed', 0, error_msg)
        logger.info("="*50)
        return False
    
    finally:
        db.close()


if __name__ == '__main__':
    # Run as standalone script
    sync_calendar()
