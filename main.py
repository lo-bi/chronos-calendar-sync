"""
Main application with scheduler and Flask API
"""
import logging
import threading
import time
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv
from chronos_client import ChronosClient
from chronos_parser import ChronosParser
from calendar_sync import CalendarSync
from notifier import Notifier
from change_detector import ChangeDetector
from dashboard import DashboardStats

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
    'events_synced': 0,
    'all_events': []  # Store events for dashboard
}

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)


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
        'notifications': {
            'enabled': get_env('ENABLE_NOTIFICATIONS', 'false', required=False).lower() == 'true',
            'ntfy_topic': get_env('NTFY_TOPIC', '', required=False),
            'ntfy_server': get_env('NTFY_SERVER', 'https://ntfy.sh', required=False)
        },
        'app': {
            'port': int(get_env('APP_PORT', '8000', required=False)),
            'host': get_env('APP_HOST', '0.0.0.0', required=False)
        }
    }
    
    logger.info("Configuration loaded from environment variables")
    return config


def perform_sync(config, is_first_run=False):
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
        
        # Calculate date range - fetch past year AND future for dashboard
        now = datetime.now()
        # For dashboard: get past year data
        past_year_start = now - timedelta(days=365)
        # For calendar sync: get future data
        future_end = now + timedelta(days=config['sync']['days_ahead'])
        
        logger.info(f"Fetching data from {past_year_start.date()} to {future_end.date()}")
        
        # Fetch all data types (full range for dashboard)
        schedule_xml = chronos.fetch_schedule(past_year_start, future_end)
        absences_xml = chronos.fetch_absences(past_year_start, future_end)
        activities_xml = chronos.fetch_activities(past_year_start, future_end)
        
        # Parse XML responses
        parser = ChronosParser()
        schedule_events = parser.parse_xml(schedule_xml) if schedule_xml else []
        absence_events = parser.parse_xml(absences_xml) if absences_xml else []
        activity_events = parser.parse_xml(activities_xml) if activities_xml else []
        
        # Merge events (absences take priority over work schedule)
        all_events = parser.merge_events(schedule_events, absence_events, activity_events)
        
        logger.info(f"Total events fetched: {len(all_events)}")
        
        # For calendar sync, filter to only future events
        calendar_events = [e for e in all_events if e.start and e.start >= now]
        logger.info(f"Events to sync to calendar: {len(calendar_events)}")
        
        # Initialize notifier if enabled
        notifier = None
        if config['notifications']['enabled'] and config['notifications']['ntfy_topic']:
            notifier = Notifier(
                topic=config['notifications']['ntfy_topic'],
                server=config['notifications']['ntfy_server'],
                enabled=True
            )
            logger.info("Notifications enabled")
            
            # Send test notification on first run only
            if is_first_run:
                notifier.send_test()
        
        # Detect changes (only if not first run)
        if not is_first_run and notifier:
            change_detector = ChangeDetector()
            new_events, deleted_events, modified_events = change_detector.detect_changes(
                all_events,
                config['sync']['days_ahead']
            )
            
            # Send notifications for changes
            for event in new_events:
                title = event.get_calendar_title()
                time_str = change_detector.format_event_time(change_detector._event_to_dict(event))
                logger.info(f"📱 Notifying: New event - {title} at {time_str}")
                
                if event.all_day:
                    notifier.send_new_shift(title, time_str)
                else:
                    # Extract time portion
                    parts = time_str.split()
                    date_part = ' '.join(parts[:3]) if len(parts) >= 3 else time_str
                    time_part = parts[-1] if len(parts) >= 4 else None
                    notifier.send_new_shift(title, date_part, time_part)
            
            for event_dict in deleted_events:
                title = event_dict['title']
                time_str = change_detector.format_event_time(event_dict)
                logger.info(f"📱 Notifying: Deleted event - {title} at {time_str}")
                
                if event_dict['all_day']:
                    notifier.send_deleted_shift(title, time_str)
                else:
                    parts = time_str.split()
                    date_part = ' '.join(parts[:3]) if len(parts) >= 3 else time_str
                    time_part = parts[-1] if len(parts) >= 4 else None
                    notifier.send_deleted_shift(title, date_part, time_part)
            
            for old, new in modified_events:
                title = new['title']
                old_time = change_detector.format_event_time(old)
                new_time = change_detector.format_event_time(new)
                logger.info(f"📱 Notifying: Modified event - {title}")
                notifier.send_modified_shift(title, old_time, new_time)
        
        elif not is_first_run:
            # Still track changes even without notifications
            change_detector = ChangeDetector()
            change_detector.detect_changes(all_events, config['sync']['days_ahead'])
        else:
            # First run - just save state
            change_detector = ChangeDetector()
            change_detector._save_current_state(all_events)
        
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
        if not cal_sync.sync_events(calendar_events):
            raise Exception("Failed to sync events")
        
        # Update state (store ALL events for dashboard, not just calendar ones)
        sync_state['last_status'] = 'success'
        sync_state['last_error'] = None
        sync_state['events_synced'] = len(calendar_events)
        sync_state['all_events'] = all_events  # Store for dashboard (includes past year)
        logger.info(f"Sync completed successfully - {len(calendar_events)} events synced to calendar, {len(all_events)} total events loaded for dashboard")
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
    
    # Perform initial sync (mark as first run)
    perform_sync(config, is_first_run=True)
    
    # Then run on schedule (subsequent runs detect changes)
    while True:
        time.sleep(interval_seconds)
        perform_sync(config, is_first_run=False)


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': sync_state['last_status'],
        'last_run': sync_state['last_run'],
        'last_error': sync_state['last_error'],
        'events_synced': sync_state['events_synced']
    })


@app.route('/')
@app.route('/dashboard')
def dashboard_page():
    """Dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/dashboard/check-auth')
def check_auth():
    """Check if user is authenticated"""
    return jsonify({
        'authenticated': session.get('authenticated', False)
    })


@app.route('/api/dashboard/login', methods=['POST'])
def dashboard_login():
    """Login to dashboard"""
    data = request.get_json()
    password = data.get('password', '')
    remember = data.get('remember', False)
    
    # Get dashboard password from environment
    correct_password = os.getenv('DASHBOARD_PASSWORD', 'chronos2025')
    
    # Simple password check (in production, use proper hashing)
    if password == correct_password:
        session['authenticated'] = True
        if remember:
            session.permanent = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 401


@app.route('/api/dashboard/logout', methods=['POST'])
def dashboard_logout():
    """Logout from dashboard"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/dashboard/stats')
def dashboard_stats():
    """Get dashboard statistics"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get events from sync state
        all_events = sync_state.get('all_events', [])
        
        if not all_events:
            return jsonify({
                'summary': {
                    'total_hours_past_year': 0,
                    'expected_hours_80_past_year': 0,
                    'average_monthly_hours': 0,
                    'current_month_hours': 0,
                    'current_week_hours': 0
                },
                'past_year_monthly': [],
                'upcoming_weeks': [],
                'last_updated': datetime.now().isoformat()
            })
        
        # Initialize dashboard stats calculator
        dashboard = DashboardStats(None)
        
        # Calculate date ranges
        now = datetime.now()
        past_year_start = now - timedelta(days=365)
        upcoming_end = now + timedelta(days=90)
        
        # Calculate monthly stats for past year
        past_year_monthly = dashboard.get_monthly_stats(all_events, past_year_start, now)
        
        # Calculate weekly stats for upcoming period
        upcoming_weeks = dashboard.get_week_stats(all_events, now, upcoming_end)
        
        # Calculate summary statistics
        total_hours_past_year = sum(m['hours_worked'] for m in past_year_monthly)
        average_monthly_hours = round(total_hours_past_year / len(past_year_monthly), 2) if past_year_monthly else 0
        
        # Current month and week
        current_month = now.strftime('%Y-%m')
        current_month_data = next((m for m in past_year_monthly if f"{m['year']}-{m['month_num']:02d}" == current_month), None)
        current_month_hours = current_month_data['hours_worked'] if current_month_data else 0
        
        current_week_data = upcoming_weeks[0] if upcoming_weeks else None
        current_week_hours = current_week_data['hours_worked'] if current_week_data else 0
        
        # Return full dashboard data
        return jsonify({
            'summary': {
                'total_hours_past_year': round(total_hours_past_year, 2),
                'expected_hours_80_past_year': round(121.24 * len(past_year_monthly), 2),
                'average_monthly_hours': average_monthly_hours,
                'current_month_hours': round(current_month_hours, 2),
                'current_week_hours': round(current_week_hours, 2)
            },
            'past_year_monthly': past_year_monthly,
            'upcoming_weeks': upcoming_weeks,
            'last_updated': sync_state.get('last_run', datetime.now().isoformat())
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500


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
