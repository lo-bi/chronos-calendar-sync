"""
Dashboard module for visualizing work statistics and planning
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database import Database
from chronos_parser import ChronosEvent
import json

logger = logging.getLogger(__name__)


class DashboardStats:
    """Calculate statistics for dashboard"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def _dict_to_event(self, event_dict: Dict) -> ChronosEvent:
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
    
    def get_events_from_db(self, start_date: datetime = None, end_date: datetime = None) -> List[ChronosEvent]:
        """Get events from database and convert to ChronosEvent objects."""
        event_dicts = self.db.get_events(start_date, end_date)
        return [self._dict_to_event(e) for e in event_dicts]
        
    def calculate_hours_from_events(self, events: List[ChronosEvent]) -> float:
        """Calculate total hours from events"""
        total_hours = 0
        
        for event in events:
            # Skip events without proper time data
            if not event.start or not event.end:
                continue
                
            duration = event.end - event.start
            hours = duration.total_seconds() / 3600
            total_hours += hours
            
        return round(total_hours, 2)
    
    def get_monthly_stats(self, events: List[ChronosEvent], start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Calculate monthly statistics
        
        Returns list of dicts with: month, year, hours_worked, expected_hours_80, percentage
        Takes into account absences to adjust expected hours
        """
        # Group events by month
        monthly_data = {}
        
        for event in events:
            # Skip events without start date
            if not event.start:
                continue
                
            if event.start < start_date or event.start > end_date:
                continue
            
            month_key = event.start.strftime('%Y-%m')
            
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'work_events': [],
                    'absence_days': set(),
                    'work_hours': 0
                }
            
            # Count work hours (HORAIRE)
            if event.event_id == 'HORAIRE' and event.end:
                duration = event.end - event.start
                hours = duration.total_seconds() / 3600
                monthly_data[month_key]['work_hours'] += hours
                monthly_data[month_key]['work_events'].append(event)
            
            # Track absence days (ABSENCEJ, ACTIVITES with all_day)
            elif event.event_id.startswith('ABSENCEJ') or event.event_id == 'ACTIVITES':
                # For absences, track the dates
                if event.end:
                    current_date = event.start.date()
                    end_date_only = event.end.date()
                    while current_date <= end_date_only:
                        monthly_data[month_key]['absence_days'].add(current_date)
                        current_date = current_date + timedelta(days=1)
                else:
                    monthly_data[month_key]['absence_days'].add(event.start.date())
        
        # Base expected hours: 80% = 28h/week, average month = 4.33 weeks = 121.24h/month
        BASE_MONTHLY_HOURS_80 = 121.24
        DAILY_HOURS_80 = 28 / 5  # 5.6h per working day at 80%
        
        results = []
        for month_key in sorted(monthly_data.keys()):
            date = datetime.strptime(month_key, '%Y-%m')
            data = monthly_data[month_key]
            actual_hours = round(data['work_hours'], 2)
            
            # Adjust expected hours based on absence days
            absence_days_count = len(data['absence_days'])
            absence_hours = absence_days_count * DAILY_HOURS_80
            expected_hours = max(0, BASE_MONTHLY_HOURS_80 - absence_hours)
            
            results.append({
                'month': date.strftime('%b'),
                'year': date.year,
                'month_num': date.month,
                'hours_worked': actual_hours,
                'expected_hours_80': round(expected_hours, 2),
                'absence_days': absence_days_count,
                'percentage': round((actual_hours / expected_hours) * 100, 1) if expected_hours > 0 else 0,
                'days_worked': len(set(e.start.date() for e in data['work_events']))
            })
        
        return results
    
    def get_week_stats(self, events: List[ChronosEvent], start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Calculate weekly statistics for upcoming weeks
        Takes into account absences to adjust expected hours
        """
        weekly_data = {}
        
        for event in events:
            # Skip events without start date
            if not event.start:
                continue
                
            if event.start < start_date or event.start > end_date:
                continue
            
            # Get week number
            week_key = event.start.strftime('%Y-W%W')
            
            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    'start': event.start - timedelta(days=event.start.weekday()),
                    'work_hours': 0,
                    'work_days': set(),
                    'absence_days': set()
                }
            
            # Count work hours (HORAIRE)
            if event.event_id == 'HORAIRE' and event.end:
                duration = event.end - event.start
                hours = duration.total_seconds() / 3600
                weekly_data[week_key]['work_hours'] += hours
                weekly_data[week_key]['work_days'].add(event.start.date())
            
            # Track absence days
            elif event.event_id.startswith('ABSENCEJ') or event.event_id == 'ACTIVITES':
                if event.end:
                    current_date = event.start.date()
                    end_date_only = event.end.date()
                    while current_date <= end_date_only:
                        weekly_data[week_key]['absence_days'].add(current_date)
                        current_date = current_date + timedelta(days=1)
                else:
                    weekly_data[week_key]['absence_days'].add(event.start.date())
        
        # Base expected hours per week at 80% = 28h
        BASE_WEEKLY_HOURS_80 = 28
        DAILY_HOURS_80 = 28 / 5  # 5.6h per working day at 80%
        
        results = []
        for week_key in sorted(weekly_data.keys()):
            data = weekly_data[week_key]
            actual_hours = round(data['work_hours'], 2)
            
            # Adjust expected hours based on absence days
            absence_days_count = len(data['absence_days'])
            absence_hours = absence_days_count * DAILY_HOURS_80
            expected_hours = max(0, BASE_WEEKLY_HOURS_80 - absence_hours)
            
            results.append({
                'week_start': data['start'].strftime('%d %b'),
                'week_start_date': data['start'].isoformat(),
                'hours_worked': actual_hours,
                'expected_hours_80': round(expected_hours, 2),
                'absence_days': absence_days_count,
                'percentage': round((actual_hours / expected_hours) * 100, 1) if expected_hours > 0 else 0,
                'days_worked': len(data['work_days'])
            })
        
        return results
    
    def get_daily_planning(self, events: List[ChronosEvent], start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get daily planning for a date range
        
        Returns list of dicts with: date, day_name, hours_worked, events, is_absence
        """
        daily_data = {}
        
        for event in events:
            if not event.start:
                continue
                
            if event.start < start_date or event.start > end_date:
                continue
            
            date_key = event.start.date()
            
            if date_key not in daily_data:
                daily_data[date_key] = {
                    'work_hours': 0,
                    'work_events': [],
                    'absences': [],
                    'is_absence': False
                }
            
            # Track work hours
            if event.event_id == 'HORAIRE' and event.end:
                duration = event.end - event.start
                hours = duration.total_seconds() / 3600
                daily_data[date_key]['work_hours'] += hours
                daily_data[date_key]['work_events'].append({
                    'start': event.start.strftime('%H:%M'),
                    'end': event.end.strftime('%H:%M'),
                    'title': event.get_calendar_title()
                })
            
            # Track absences
            elif event.event_id.startswith('ABSENCEJ'):
                daily_data[date_key]['is_absence'] = True
                daily_data[date_key]['absences'].append({
                    'type': event.lib or event.code or 'Absence',
                    'title': event.get_calendar_title()
                })
            
            # Track ACTIVITES separately (different color in UI)
            elif event.event_id == 'ACTIVITES':
                daily_data[date_key]['is_absence'] = True
                daily_data[date_key]['absences'].append({
                    'type': 'ACTIVITES - ' + (event.lib or event.code or 'Activité'),
                    'title': event.get_calendar_title()
                })
        
        # Convert to sorted list
        results = []
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            data = daily_data.get(current_date, {
                'work_hours': 0,
                'work_events': [],
                'absences': [],
                'is_absence': False
            })
            
            # French day names
            day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            day_name = day_names[current_date.weekday()]
            
            results.append({
                'date': current_date.isoformat(),
                'date_display': current_date.strftime('%d/%m/%Y'),
                'day_name': day_name,
                'hours_worked': round(data['work_hours'], 2),
                'events': data['work_events'],
                'absences': data['absences'],
                'is_absence': data['is_absence'],
                'is_weekend': current_date.weekday() >= 5
            })
            
            current_date = current_date + timedelta(days=1)
        
        return results
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get all dashboard data
        
        Returns dict with: past_year_stats, upcoming_stats, summary
        """
        now = datetime.now()
        
        # Past year stats
        past_year_start = now - timedelta(days=365)
        
        # Upcoming stats (next 3 months)
        upcoming_end = now + timedelta(days=90)
        
        # This would need to fetch from calendar or database
        # For now, return structure
        return {
            'summary': {
                'total_hours_past_year': 0,
                'expected_hours_80_past_year': 0,
                'average_monthly_hours': 0,
                'current_month_hours': 0,
                'current_week_hours': 0
            },
            'past_year_monthly': [],
            'upcoming_weeks': [],
            'last_updated': now.isoformat()
        }
