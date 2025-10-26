"""
Parser for Chronos XML responses
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ChronosEvent:
    """Represents a single event from Chronos"""
    
    def __init__(self, event_data: Dict[str, Any]):
        self.event_id = event_data.get('p_id', '')
        self.title = event_data.get('p_title', '')
        self.all_day = event_data.get('p_allday', 'true') == 'true'
        self.start = self._parse_date(event_data.get('p_start', ''))
        self.end = self._parse_date(event_data.get('p_end', ''))
        self.description = event_data.get('p_desc', '')
        self.code = event_data.get('p_cod', '')
        self.lib = event_data.get('p_lib', '')
        self.planning = event_data.get('p_plg', '')
        self.duration = event_data.get('p_tpm', '')
        self.symbol = event_data.get('p_sym', '')
        self.abbreviation = event_data.get('p_abr', '')
        
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string from Chronos format"""
        if not date_str:
            return None
        try:
            # Try ISO format: 2025-10-24T07:15:00
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            try:
                # Try date only: 2025-10-24
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                logger.warning(f"Could not parse date: {date_str}")
                return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'id': self.event_id,
            'title': self.title,
            'all_day': self.all_day,
            'start': self.start.isoformat() if self.start else None,
            'end': self.end.isoformat() if self.end else None,
            'description': self.description,
            'code': self.code,
            'lib': self.lib,
            'planning': self.planning,
            'duration': self.duration,
            'symbol': self.symbol,
            'abbreviation': self.abbreviation
        }
    
    def get_calendar_title(self) -> str:
        """Get formatted title for calendar"""
        if self.event_id == 'HORAIRE':
            return f"Work: {self.planning}"
        elif self.event_id == 'ABSENCEJ':
            return f"{self.code}: {self.lib}"
        elif self.event_id == 'ACTIVITES':
            return f"Activity: {self.lib}"
        return self.title
    
    def get_calendar_description(self) -> str:
        """Get formatted description for calendar"""
        parts = []
        if self.lib:
            parts.append(self.lib)
        if self.planning:
            parts.append(f"Time: {self.planning}")
        if self.duration:
            parts.append(f"Duration: {self.duration}")
        if self.description:
            # Remove HTML tags from description
            clean_desc = self.description.replace('<br>', '\n').replace('&gt;', '>').replace('&lt;', '<')
            parts.append(clean_desc)
        return '\n'.join(parts)
    
    def get_unique_id(self) -> str:
        """Generate unique identifier for this event"""
        # Combine event type, date, and planning/code to create unique ID
        start_str = self.start.isoformat() if self.start else 'no-date'
        if self.event_id == 'HORAIRE':
            return f"HORAIRE-{start_str}-{self.planning}"
        elif self.event_id == 'ABSENCEJ':
            return f"ABSENCE-{start_str}-{self.code}"
        elif self.event_id == 'ACTIVITES':
            return f"ACTIVITY-{start_str}-{self.lib}"
        return f"{self.event_id}-{start_str}-{self.title}"


class ChronosParser:
    """Parser for Chronos XML responses"""
    
    @staticmethod
    def parse_xml(xml_string: str) -> List[ChronosEvent]:
        """
        Parse XML response from Chronos API
        Returns list of ChronosEvent objects
        """
        if not xml_string:
            return []
        
        try:
            root = ET.fromstring(xml_string)
            events = []
            
            for event_row in root.findall('.//eventRow'):
                event_data = {}
                for child in event_row:
                    event_data[child.tag] = child.text or ''
                
                event = ChronosEvent(event_data)
                events.append(event)
                logger.debug(f"Parsed event: {event.get_calendar_title()} on {event.start}")
            
            logger.info(f"Parsed {len(events)} events from XML")
            return events
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing events: {e}")
            return []
    
    @staticmethod
    def merge_events(schedule: List[ChronosEvent], absences: List[ChronosEvent], 
                     activities: List[ChronosEvent]) -> List[ChronosEvent]:
        """
        Merge different event types, handling conflicts
        Priority: absences > activities > schedule
        """
        logger.info(f"Merging events: {len(schedule)} schedule, {len(absences)} absences, {len(activities)} activities")
        
        # Create a date map for absences (highest priority)
        absence_dates = {event.start.date(): event for event in absences if event.start}
        logger.debug(f"Absence dates: {list(absence_dates.keys())}")
        
        # Filter out schedule items on dates with absences
        filtered_schedule = []
        removed_count = 0
        for event in schedule:
            if not event.start or event.start.date() not in absence_dates:
                filtered_schedule.append(event)
            else:
                removed_count += 1
                logger.debug(f"Removed schedule event on {event.start.date()} due to absence")
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} schedule events due to absences")
        
        # Combine all events
        all_events = absences + activities + filtered_schedule
        
        # Sort by start date
        all_events.sort(key=lambda x: x.start if x.start else datetime.max)
        
        logger.info(f"Merged events: {len(absences)} absences, {len(activities)} activities, "
                   f"{len(filtered_schedule)} schedule items, {len(all_events)} total")
        
        # Log summary of merged events
        for i, event in enumerate(all_events, 1):
            logger.debug(f"  {i}. {event.get_calendar_title()} - {event.start} to {event.end}")
        
        return all_events
