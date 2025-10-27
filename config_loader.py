"""
Configuration loader from environment variables.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


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
            'days_ahead': int(get_env('SYNC_DAYS_AHEAD', '90', required=False)),
            'interval_minutes': int(get_env('SYNC_INTERVAL_MINUTES', '60', required=False)),
            'calendar_sync_minutes': int(get_env('CALENDAR_SYNC_MINUTES', '15', required=False))
        },
        'notifications': {
            'enabled': get_env('ENABLE_NOTIFICATIONS', 'false', required=False).lower() == 'true',
            'ntfy_topic': get_env('NTFY_TOPIC', '', required=False),
            'ntfy_server': get_env('NTFY_SERVER', 'https://ntfy.sh', required=False)
        },
        'app': {
            'port': int(get_env('APP_PORT', '8000', required=False)),
            'host': get_env('APP_HOST', '0.0.0.0', required=False)
        },
        'database': {
            'path': get_env('DB_PATH', 'chronos_sync.db', required=False)
        }
    }
    
    logger.info("Configuration loaded from environment variables")
    return config
