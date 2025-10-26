"""
Main application with scheduler and Flask API
"""
import logging
import threading
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify
from dotenv import load_dotenv
from chronos_client import ChronosClient
from chronos_parser import ChronosParser
from calendar_sync import CalendarSync

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state for health endpoint
sync_state = {
    'last_run': None,
    'last_status': 'never_run',
    'last_error': None,
    'events_synced': 0
}

# Flask app
app = Flask(__name__)


def load_config():
    """Load configuration from environment variables"""
    
    # Helper function to get required env var
    def get_env(key, default=None, required=True):
        value = os.getenv(key, default)
        if required and not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value
    
    config = {
        'chronos': {
            'username': get_env('CHRONOS_USERNAME'),
            'password': get_env('CHRONOS_PASSWORD'),
            'base_url': get_env('CHRONOS_BASE_URL', 'https://chpcb.chronos-saas.com'),
            'auth_url': get_env('CHRONOS_AUTH_URL', 'https://auth-saas-chronos.asys.fr')
        },
        'icalendar': {
            'url': get_env('ICALENDAR_URL', 'https://caldav.icloud.com'),
            'username': get_env('ICALENDAR_USERNAME'),
            'password': get_env('ICALENDAR_PASSWORD'),
            'calendar_name': get_env('ICALENDAR_CALENDAR_NAME', 'Chronos Planning')
        },
        'sync': {
            'days_ahead': int(get_env('SYNC_DAYS_AHEAD', '7', required=False)),
            'interval_minutes': int(get_env('SYNC_INTERVAL_MINUTES', '60', required=False))
        },
        'app': {
            'port': int(get_env('APP_PORT', '8000', required=False)),
            'host': get_env('APP_HOST', '0.0.0.0', required=False)
        }
    }
    
    logger.info("Configuration loaded from environment variables")
    return config


def perform_sync(config):
    """Perform a single sync operation"""
    global sync_state
    
    try:
        logger.info("=" * 50)
        logger.info("Starting sync operation")
        sync_state['last_run'] = datetime.now().isoformat()
        
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
        
        # Calculate date range
        start_date = datetime.now()
        end_date = start_date + timedelta(days=config['sync']['days_ahead'])
        
        logger.info(f"Fetching data from {start_date.date()} to {end_date.date()}")
        
        # Fetch all data types
        schedule_xml = chronos.fetch_schedule(start_date, end_date)
        absences_xml = chronos.fetch_absences(start_date, end_date)
        activities_xml = chronos.fetch_activities(start_date, end_date)
        
        # Parse XML responses
        parser = ChronosParser()
        schedule_events = parser.parse_xml(schedule_xml) if schedule_xml else []
        absence_events = parser.parse_xml(absences_xml) if absences_xml else []
        activity_events = parser.parse_xml(activities_xml) if activities_xml else []
        
        # Merge events (absences take priority over work schedule)
        all_events = parser.merge_events(schedule_events, absence_events, activity_events)
        
        logger.info(f"Total events to sync: {len(all_events)}")
        
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
        logger.info("Syncing events to calendar...")
        if not cal_sync.sync_events(all_events):
            raise Exception("Failed to sync events")
        
        # Update state
        sync_state['last_status'] = 'success'
        sync_state['last_error'] = None
        sync_state['events_synced'] = len(all_events)
        logger.info(f"Sync completed successfully - {len(all_events)} events synced")
        logger.info("=" * 50)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Sync failed: {error_msg}")
        sync_state['last_status'] = 'failed'
        sync_state['last_error'] = error_msg
        logger.info("=" * 50)


def sync_scheduler(config):
    """Background thread that runs sync periodically"""
    interval_seconds = config['sync']['interval_minutes'] * 60
    
    logger.info(f"Scheduler started - will sync every {config['sync']['interval_minutes']} minutes")
    
    # Perform initial sync
    perform_sync(config)
    
    # Then run on schedule
    while True:
        time.sleep(interval_seconds)
        perform_sync(config)


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': sync_state['last_status'],
        'last_run': sync_state['last_run'],
        'last_error': sync_state['last_error'],
        'events_synced': sync_state['events_synced']
    })


def main():
    """Main application entry point"""
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()
        
        # Start sync scheduler in background thread
        scheduler_thread = threading.Thread(
            target=sync_scheduler,
            args=(config,),
            daemon=True
        )
        scheduler_thread.start()
        
        # Start Flask web server
        host = config['app']['host']
        port = config['app']['port']
        logger.info(f"Starting web server on {host}:{port}")
        logger.info(f"Health endpoint available at http://{host}:{port}/health")
        
        app.run(host=host, port=port, debug=False)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == '__main__':
    main()
