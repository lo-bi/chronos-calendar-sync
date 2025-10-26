"""
Change detection for Chronos events
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime, timedelta
from chronos_parser import ChronosEvent
import locale

logger = logging.getLogger(__name__)

# Set French locale for day names
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except:
        logger.warning("Could not set French locale, using default")

class ChangeDetector:
    """Detect changes in Chronos events between syncs"""
    
    def __init__(self, state_file: str = "data/last_sync.json"):
        """
        Initialize change detector
        
        Args:
            state_file: Path to store previous sync state
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _event_to_dict(self, event: ChronosEvent) -> Dict:
        """Convert event to dictionary for comparison"""
        return {
            'uid': event.get_unique_id(),
            'title': event.get_calendar_title(),
            'start': event.start.isoformat() if event.start else None,
            'end': event.end.isoformat() if event.end else None,
            'description': event.get_calendar_description(),
            'all_day': event.all_day,
            'code': event.code
        }
    
    def _load_previous_state(self) -> Dict[str, Dict]:
        """Load previous sync state from file"""
        if not self.state_file.exists():
            logger.info("No previous sync state found")
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                return {item['uid']: item for item in data}
        except Exception as e:
            logger.error(f"Error loading previous state: {e}")
            return {}
    
    def _save_current_state(self, events: List[ChronosEvent]):
        """Save current sync state to file"""
        try:
            event_dicts = [self._event_to_dict(event) for event in events]
            with open(self.state_file, 'w') as f:
                json.dump(event_dicts, f, indent=2)
            logger.debug(f"Saved state for {len(event_dicts)} events")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def detect_changes(
        self, 
        current_events: List[ChronosEvent],
        sync_days_ahead: int
    ) -> Tuple[List[ChronosEvent], List[Dict], List[Tuple[Dict, Dict]]]:
        """
        Detect changes between previous and current sync
        
        Args:
            current_events: List of current events from Chronos
            sync_days_ahead: Number of days ahead to sync (for filtering)
            
        Returns:
            Tuple of (new_events, deleted_events, modified_events)
            - new_events: List of ChronosEvent objects
            - deleted_events: List of event dicts
            - modified_events: List of (old_dict, new_dict) tuples
        """
        # Load previous state
        previous_state = self._load_previous_state()
        
        # Convert current events to dicts
        current_state = {self._event_to_dict(event)['uid']: self._event_to_dict(event) 
                        for event in current_events}
        
        # Get current UIDs and previous UIDs
        current_uids = set(current_state.keys())
        previous_uids = set(previous_state.keys())
        
        # Detect changes
        new_uids = current_uids - previous_uids
        deleted_uids = previous_uids - current_uids
        potentially_modified_uids = current_uids & previous_uids
        
        # Filter out events at the boundary (exactly SYNC_DAYS_AHEAD)
        boundary_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=sync_days_ahead)
        
        def is_at_boundary(event_dict: Dict) -> bool:
            """Check if event is at the sync boundary"""
            if not event_dict.get('start'):
                return False
            event_date = datetime.fromisoformat(event_dict['start']).date()
            return event_date == boundary_date.date()
        
        # Find new events (excluding boundary)
        new_events = []
        for uid in new_uids:
            event_dict = current_state[uid]
            if not is_at_boundary(event_dict):
                # Find the original event object
                event_obj = next((e for e in current_events if self._event_to_dict(e)['uid'] == uid), None)
                if event_obj:
                    new_events.append(event_obj)
        
        # Find deleted events (excluding boundary)
        deleted_events = []
        for uid in deleted_uids:
            event_dict = previous_state[uid]
            if not is_at_boundary(event_dict):
                deleted_events.append(event_dict)
        
        # Find modified events
        modified_events = []
        for uid in potentially_modified_uids:
            old = previous_state[uid]
            new = current_state[uid]
            
            # Compare relevant fields
            if (old['title'] != new['title'] or 
                old['start'] != new['start'] or 
                old['end'] != new['end'] or
                old['description'] != new['description']):
                
                if not is_at_boundary(new):
                    modified_events.append((old, new))
        
        # Save current state for next comparison
        self._save_current_state(current_events)
        
        # Log summary
        if new_events or deleted_events or modified_events:
            logger.info(f"Changes detected: {len(new_events)} new, {len(deleted_events)} deleted, {len(modified_events)} modified")
        else:
            logger.info("No changes detected")
        
        return new_events, deleted_events, modified_events
    
    def format_event_time(self, event_dict: Dict) -> str:
        """Format event time for display in French"""
        try:
            start = datetime.fromisoformat(event_dict['start'])
            
            # French day names mapping (in case locale doesn't work)
            day_names_fr = {
                'Monday': 'Lundi',
                'Tuesday': 'Mardi', 
                'Wednesday': 'Mercredi',
                'Thursday': 'Jeudi',
                'Friday': 'Vendredi',
                'Saturday': 'Samedi',
                'Sunday': 'Dimanche'
            }
            
            # French month names
            month_names_fr = {
                'January': 'Jan', 'February': 'Fev', 'March': 'Mar',
                'April': 'Avr', 'May': 'Mai', 'June': 'Juin',
                'July': 'Juil', 'August': 'Aou', 'September': 'Sep',
                'October': 'Oct', 'November': 'Nov', 'December': 'Dec'
            }
            
            # Get day name in French
            day_name_en = start.strftime('%A')
            day_name = day_names_fr.get(day_name_en, day_name_en)
            
            # Get month name in French
            month_name_en = start.strftime('%B')
            month_name = month_names_fr.get(month_name_en, start.strftime('%b'))
            
            if event_dict.get('all_day'):
                # Format: "Lundi 04 Nov"
                return f"{day_name} {start.strftime('%d')} {month_name}"
            else:
                end = datetime.fromisoformat(event_dict['end'])
                # Format: "Lundi 04 Nov 08:00-17:00"
                return f"{day_name} {start.strftime('%d')} {month_name} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        except:
            return "Date inconnue"
