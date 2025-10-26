"""
iCloud Calendar Sync using CalDAV
"""
import caldav
from caldav.elements import dav, cdav
from icalendar import Calendar, Event as ICalEvent
from datetime import datetime, timezone
from typing import List, Optional
import logging
from chronos_parser import ChronosEvent

logger = logging.getLogger(__name__)


class CalendarSync:
    """Syncs events to iCloud calendar using CalDAV"""
    
    def __init__(self, url: str, username: str, password: str, calendar_name: str):
        self.url = url
        self.username = username
        self.password = password
        self.calendar_name = calendar_name
        self.client = None
        self.calendar = None
        
    def connect(self) -> bool:
        """Connect to CalDAV server and get/create calendar"""
        try:
            logger.info("Connecting to CalDAV server...")
            self.client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password
            )
            
            principal = self.client.principal()
            calendars = principal.calendars()
            
            # Find or create the calendar
            for cal in calendars:
                if cal.name == self.calendar_name:
                    self.calendar = cal
                    logger.info(f"Found existing calendar: {self.calendar_name}")
                    break
            
            if not self.calendar:
                logger.info(f"Creating new calendar: {self.calendar_name}")
                self.calendar = principal.make_calendar(name=self.calendar_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to CalDAV: {e}")
            return False
    
    def sync_events(self, events: List[ChronosEvent]) -> bool:
        """
        Sync events to calendar
        Removes old events and adds new ones
        """
        if not self.calendar:
            logger.error("No calendar connection")
            return False
        
        try:
            # Get date range of events to sync
            if not events:
                logger.info("No events to sync")
                return True
            
            start_date = min(e.start for e in events if e.start)
            end_date = max(e.end if e.end else e.start for e in events if e.start)
            
            logger.info(f"Syncing {len(events)} events from {start_date} to {end_date}")
            
            # Delete existing events in this range with our prefix
            self._clear_existing_events(start_date, end_date)
            
            # Add new events
            for event in events:
                self._add_event(event)
            
            logger.info("Sync completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing events: {e}")
            return False
    
    def _clear_existing_events(self, start_date: datetime, end_date: datetime):
        """Remove existing Chronos events in the date range"""
        try:
            # Search for events in the date range
            events = self.calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True
            )
            
            deleted_count = 0
            for event in events:
                try:
                    # Check if this is a Chronos event (by UID or summary prefix)
                    cal_data = event.data
                    if 'CHRONOS-SYNC' in cal_data or 'Work:' in cal_data or 'Activity:' in cal_data:
                        event.delete()
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete event: {e}")
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} existing events")
                
        except Exception as e:
            logger.warning(f"Could not clear existing events: {e}")
    
    def _add_event(self, chronos_event: ChronosEvent):
        """Add a single event to the calendar"""
        try:
            if not chronos_event.start:
                logger.warning(f"Skipping event without start date: {chronos_event.title}")
                return
            
            logger.info(f"Creating event: {chronos_event.get_calendar_title()}")
            logger.debug(f"  Event details: type={chronos_event.event_id}, code={chronos_event.code}")
            logger.debug(f"  Start: {chronos_event.start}, End: {chronos_event.end}")
            logger.debug(f"  All-day: {chronos_event.all_day}")
            
            # Create iCalendar event
            cal = Calendar()
            cal.add('prodid', '-//Chronos Calendar Sync//EN')
            cal.add('version', '2.0')
            
            event = ICalEvent()
            
            # Generate unique UID
            uid = f"chronos-{chronos_event.code}-{chronos_event.start.strftime('%Y%m%d')}-CHRONOS-SYNC"
            event.add('uid', uid)
            logger.debug(f"  UID: {uid}")
            
            # Add summary (title)
            title = chronos_event.get_calendar_title()
            event.add('summary', title)
            logger.debug(f"  Title: {title}")
            
            # Add description
            description = chronos_event.get_calendar_description()
            event.add('description', description)
            logger.debug(f"  Description: {description}")
            
            # Add dates
            if chronos_event.all_day:
                # All-day event
                start_date = chronos_event.start.date()
                end_date = chronos_event.end.date() if chronos_event.end and chronos_event.end != chronos_event.start else chronos_event.start.date()
                event.add('dtstart', start_date)
                event.add('dtend', end_date)
                logger.debug(f"  All-day event: {start_date} to {end_date}")
            else:
                # Timed event
                start_time = chronos_event.start
                end_time = chronos_event.end if chronos_event.end else chronos_event.start
                event.add('dtstart', start_time)
                event.add('dtend', end_time)
                logger.debug(f"  Timed event: {start_time} to {end_time}")
            
            # Add timestamp
            event.add('dtstamp', datetime.now(timezone.utc))
            
            # Add categories for filtering
            categories = ['CHRONOS-SYNC']
            if chronos_event.event_id:
                categories.append(chronos_event.event_id)
            if chronos_event.code:
                categories.append(chronos_event.code)
            event.add('categories', categories)
            logger.debug(f"  Categories: {', '.join(categories)}")
            
            cal.add_component(event)
            
            # Save to calendar
            ical_data = cal.to_ical().decode('utf-8')
            logger.debug(f"  iCal data length: {len(ical_data)} bytes")
            self.calendar.save_event(ical_data)
            logger.info(f"✓ Successfully added event: {title}")
            
        except Exception as e:
            logger.error(f"✗ Error adding event {chronos_event.title}: {e}")
            import traceback
            logger.debug(f"  Traceback: {traceback.format_exc()}")
    
    def test_connection(self) -> bool:
        """Test if the calendar connection is working"""
        try:
            if not self.client:
                return False
            principal = self.client.principal()
            calendars = principal.calendars()
            logger.info(f"Connection test successful, found {len(calendars)} calendars")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
