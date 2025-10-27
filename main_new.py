"""
Main application with job scheduler and Flask dashboard API
"""
import logging
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from database import Database
from dashboard import DashboardStats
from config_loader import load_config
from jobs.fetch_chronos import fetch_chronos_data
from jobs.sync_calendar import sync_calendar
from jobs.notify_changes import detect_and_notify_changes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Global database instance
db = Database(config['database']['path'])

# Initialize scheduler
scheduler = BackgroundScheduler(daemon=True)


# ===== JOB ORCHESTRATION =====

def run_fetch_job():
    """Wrapper for fetch job with error handling"""
    try:
        fetch_chronos_data()
    except Exception as e:
        logger.error(f"Fetch job error: {e}", exc_info=True)


def run_sync_job():
    """Wrapper for sync job with error handling"""
    try:
        sync_calendar()
    except Exception as e:
        logger.error(f"Sync job error: {e}", exc_info=True)


def run_notify_job():
    """Wrapper for notify job with error handling"""
    try:
        detect_and_notify_changes()
    except Exception as e:
        logger.error(f"Notify job error: {e}", exc_info=True)


def schedule_jobs():
    """Schedule all jobs"""
    
    # Job 1: Fetch Chronos data - Every hour
    scheduler.add_job(
        func=run_fetch_job,
        trigger=IntervalTrigger(hours=1),
        id='fetch_chronos',
        name='Fetch Chronos Data',
        replace_existing=True,
        max_instances=1
    )
    logger.info("✓ Scheduled: Fetch Chronos (every hour)")
    
    # Job 2: Sync Calendar - Every 15-30 minutes
    sync_minutes = config['sync'].get('calendar_sync_minutes', 15)
    scheduler.add_job(
        func=run_sync_job,
        trigger=IntervalTrigger(minutes=sync_minutes),
        id='sync_calendar',
        name='Sync Calendar',
        replace_existing=True,
        max_instances=1
    )
    logger.info(f"✓ Scheduled: Sync Calendar (every {sync_minutes} minutes)")
    
    # Job 3: Notify Changes - Run after each sync (with a small delay)
    scheduler.add_job(
        func=run_notify_job,
        trigger=IntervalTrigger(minutes=sync_minutes + 2),
        id='notify_changes',
        name='Notify Changes',
        replace_existing=True,
        max_instances=1
    )
    logger.info(f"✓ Scheduled: Notify Changes (every {sync_minutes + 2} minutes)")
    
    # Run only fetch job on startup (not sync and notify)
    logger.info("\n" + "="*50)
    logger.info("Running initial fetch job on startup...")
    logger.info("="*50)
    
    # Run fetch first to populate database
    run_fetch_job()
    
    logger.info("="*50)
    logger.info("Initial fetch completed - sync and notify will run on schedule")
    logger.info("="*50 + "\n")


# ===== FLASK ROUTES =====

@app.route('/')
@app.route('/dashboard')
def dashboard():
    """Serve dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/dashboard/check-auth')
def check_auth():
    """Check if user is authenticated"""
    return jsonify({'authenticated': session.get('authenticated', False)})


@app.route('/api/dashboard/login', methods=['POST'])
def login():
    """Login to dashboard"""
    data = request.get_json()
    password = data.get('password', '')
    remember = data.get('remember', False)
    
    # Hash password and compare with environment variable
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    expected_password = os.getenv('DASHBOARD_PASSWORD', 'Laura2025!')
    expected_hash = hashlib.sha256(expected_password.encode()).hexdigest()
    
    if password_hash == expected_hash:
        session['authenticated'] = True
        if remember:
            session.permanent = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 401


@app.route('/api/dashboard/logout', methods=['POST'])
def logout():
    """Logout from dashboard"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/dashboard/stats')
def dashboard_stats():
    """Get dashboard statistics"""
    if not session.get('authenticated', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Initialize dashboard with database
        dashboard = DashboardStats(db)
        
        # Date ranges
        now = datetime.now()
        past_year_start = now - timedelta(days=365)
        future_end = now + timedelta(days=90)
        
        # Get events from database
        all_events = dashboard.get_events_from_db(past_year_start, future_end)
        
        # Calculate stats - include future months for planning
        past_year_monthly = dashboard.get_monthly_stats(all_events, past_year_start, future_end)
        
        # Get daily planning - support custom month via query parameter
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        if year and month:
            # Custom month requested
            from calendar import monthrange
            planning_start = datetime(year, month, 1)
            last_day = monthrange(year, month)[1]
            planning_end = datetime(year, month, last_day, 23, 59, 59)
        else:
            # Default to next 30 days
            planning_start = now
            planning_end = now + timedelta(days=30)
        
        daily_planning = dashboard.get_daily_planning(all_events, planning_start, planning_end)
        
        # Summary statistics
        current_month_events = [e for e in all_events if e.start and e.start.month == now.month and e.start.year == now.year]
        current_week_start = now - timedelta(days=now.weekday())
        current_week_events = [e for e in all_events if e.start and e.start >= current_week_start and e.start <= now]
        
        total_hours_past_year = sum(m['hours_worked'] for m in past_year_monthly)
        avg_monthly_hours = round(total_hours_past_year / len(past_year_monthly), 1) if past_year_monthly else 0
        
        return jsonify({
            'summary': {
                'current_month_hours': dashboard.calculate_hours_from_events(current_month_events),
                'current_week_hours': dashboard.calculate_hours_from_events(current_week_events),
                'total_hours_past_year': round(total_hours_past_year, 1),
                'average_monthly_hours': avg_monthly_hours
            },
            'past_year_monthly': past_year_monthly,
            'daily_planning': daily_planning,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    try:
        # Get last sync info from database
        last_fetch = db.get_last_sync('fetch_chronos')
        last_sync = db.get_last_sync('sync_calendar')
        last_notify = db.get_last_sync('notify_changes')
        
        # Get event counts
        now = datetime.now()
        total_events = db.get_events_count()
        future_events = db.get_events_count(start_date=now)
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'jobs': {
                'fetch_chronos': last_fetch,
                'sync_calendar': last_sync,
                'notify_changes': last_notify
            },
            'events': {
                'total': total_events,
                'future': future_events
            },
            'scheduler': {
                'running': scheduler.running,
                'jobs': [
                    {
                        'id': job.id,
                        'name': job.name,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                    }
                    for job in scheduler.get_jobs()
                ]
            }
        })
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.route('/api/sync-history')
def sync_history():
    """Get sync history"""
    if not session.get('authenticated', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        job_type = request.args.get('job_type')
        limit = int(request.args.get('limit', 50))
        
        history = db.get_sync_history(job_type, limit)
        return jsonify({'history': history})
    except Exception as e:
        logger.error(f"Sync history error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ===== MAIN =====

def main():
    """Main application entry point"""
    logger.info("="*50)
    logger.info("Chronos Calendar Sync - Job-Based Architecture")
    logger.info("="*50)
    
    # Schedule and start jobs
    schedule_jobs()
    scheduler.start()
    
    logger.info("\n🚀 Scheduler started successfully")
    logger.info(f"📊 Dashboard: http://{config['app']['host']}:{config['app']['port']}/")
    logger.info(f"❤️  Health: http://{config['app']['host']}:{config['app']['port']}/api/health")
    logger.info("\nPress Ctrl+C to stop\n")
    
    # Start Flask app
    try:
        app.run(
            host=config['app']['host'],
            port=config['app']['port'],
            debug=False,
            use_reloader=False  # Disable reloader to avoid duplicate scheduler
        )
    except KeyboardInterrupt:
        logger.info("\n\nShutting down...")
        scheduler.shutdown()
        db.close()
        logger.info("Goodbye!")


if __name__ == '__main__':
    main()
