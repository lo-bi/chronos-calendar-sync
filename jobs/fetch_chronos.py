"""
Job: Fetch Chronos Data
Runs every hour to fetch events from Chronos and store in database.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chronos_client import ChronosClient
from chronos_parser import ChronosParser
from database import Database
from config_loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_chronos_data():
    """Fetch data from Chronos and store in database."""
    db = Database()
    log_id = db.start_sync_log('fetch_chronos')
    
    try:
        logger.info("="*50)
        logger.info("JOB: Fetch Chronos Data - STARTED")
        logger.info("="*50)
        
        # Load configuration
        config = load_config()
        
        # Initialize Chronos client
        chronos = ChronosClient(
            username=config['chronos']['username'],
            password=config['chronos']['password'],
            base_url=config['chronos']['base_url'],
            auth_url=config['chronos']['auth_url']
        )
        
        # Authenticate
        logger.info("Authenticating with Chronos...")
        if not chronos.authenticate():
            raise Exception("Authentication failed")
        
        # Calculate date range - fetch past year AND future for dashboard
        now = datetime.now()
        past_year_start = now - timedelta(days=365)
        future_end = now + timedelta(days=config['sync']['days_ahead'])
        
        logger.info(f"Fetching data from {past_year_start.date()} to {future_end.date()}")
        
        # Fetch all data types
        schedule_xml = chronos.fetch_schedule(past_year_start, future_end)
        absences_xml = chronos.fetch_absences(past_year_start, future_end)
        activities_xml = chronos.fetch_activities(past_year_start, future_end)
        
        # Parse XML responses
        parser = ChronosParser()
        schedule_events = parser.parse_xml(schedule_xml) if schedule_xml else []
        absence_events = parser.parse_xml(absences_xml) if absences_xml else []
        activity_events = parser.parse_xml(activities_xml) if activities_xml else []
        
        logger.info(f"Parsed {len(schedule_events)} schedule events")
        logger.info(f"Parsed {len(absence_events)} absence events")
        logger.info(f"Parsed {len(activity_events)} activity events")
        
        # Merge events
        all_events = parser.merge_events(schedule_events, absence_events, activity_events)
        logger.info(f"Total events after merge: {len(all_events)}")
        
        # Save to database
        saved_count = db.save_events(all_events)
        logger.info(f"Saved {saved_count} events to database")
        
        # Store last fetch time
        db.set_setting('last_fetch_time', datetime.now().isoformat())
        db.set_setting('last_fetch_count', len(all_events))
        
        # Cleanup old events (older than 2 years)
        two_years_ago = now - timedelta(days=730)
        deleted = db.delete_old_events(two_years_ago)
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old events")
        
        # Complete sync log
        db.complete_sync_log(log_id, 'success', saved_count)
        
        logger.info("="*50)
        logger.info(f"JOB: Fetch Chronos Data - SUCCESS ({saved_count} events)")
        logger.info("="*50)
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Fetch job failed: {error_msg}", exc_info=True)
        db.complete_sync_log(log_id, 'failed', 0, error_msg)
        logger.info("="*50)
        return False
    
    finally:
        db.close()


if __name__ == '__main__':
    # Run as standalone script
    fetch_chronos_data()
