"""
Database module for storing Chronos events and sync state.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for Chronos sync app."""
    
    def __init__(self, db_path: str = "chronos_sync.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Events table - stores all Chronos events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                unique_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration_hours REAL NOT NULL,
                code TEXT,
                lib TEXT,
                title TEXT NOT NULL,
                all_day INTEGER DEFAULT 0,
                event_type TEXT DEFAULT 'work',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(unique_id, start_time)
            )
        """)
        
        # Sync log table - tracks sync operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                events_count INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_seconds REAL
            )
        """)
        
        # Settings table - runtime configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Change tracking table - for notifications
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_type TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_title TEXT,
                old_time TEXT,
                new_time TEXT,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_unique_id ON events(unique_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_log_job ON sync_log(job_type, started_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_changes_notified ON event_changes(notified, detected_at)")
        
        self.conn.commit()
        logger.info(f"Database initialized: {self.db_path}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    # ===== EVENT OPERATIONS =====
    
    def save_events(self, events: List[Any]) -> int:
        """
        Save or update events in database.
        
        Args:
            events: List of ChronosEvent objects
            
        Returns:
            Number of events saved/updated
        """
        cursor = self.conn.cursor()
        count = 0
        
        for event in events:
            try:
                cursor.execute("""
                    INSERT INTO events (
                        event_id, unique_id, start_time, end_time, 
                        duration_hours, code, lib, title, all_day, event_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(unique_id, start_time) DO UPDATE SET
                        end_time = excluded.end_time,
                        duration_hours = excluded.duration_hours,
                        code = excluded.code,
                        lib = excluded.lib,
                        title = excluded.title,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    event.event_id,
                    event.get_unique_id(),
                    event.start.isoformat() if event.start else None,
                    event.end.isoformat() if event.end else None,
                    event.duration,
                    event.code,
                    event.lib,
                    event.get_calendar_title(),
                    1 if event.all_day else 0,
                    'absence' if event.event_id.startswith('ABS-') else 'work'
                ))
                count += 1
            except Exception as e:
                logger.error(f"Failed to save event {event.event_id}: {e}")
        
        self.conn.commit()
        return count
    
    def get_events(self, start_date: Optional[datetime] = None, 
                   end_date: Optional[datetime] = None) -> List[Dict]:
        """
        Retrieve events from database.
        
        Args:
            start_date: Filter events starting after this date
            end_date: Filter events starting before this date
            
        Returns:
            List of event dictionaries
        """
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND start_time >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND start_time <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY start_time ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_events_count(self, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> int:
        """Get count of events in date range."""
        cursor = self.conn.cursor()
        
        query = "SELECT COUNT(*) as count FROM events WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND start_time >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND start_time <= ?"
            params.append(end_date.isoformat())
        
        cursor.execute(query, params)
        return cursor.fetchone()[0]
    
    def delete_old_events(self, before_date: datetime) -> int:
        """Delete events older than specified date."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM events WHERE start_time < ?", (before_date.isoformat(),))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
    
    # ===== SYNC LOG OPERATIONS =====
    
    def start_sync_log(self, job_type: str) -> int:
        """
        Start a new sync log entry.
        
        Args:
            job_type: Type of job (fetch_chronos, sync_calendar, notify_changes)
            
        Returns:
            Log ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sync_log (job_type, status, started_at)
            VALUES (?, 'running', ?)
        """, (job_type, datetime.now().isoformat()))
        self.conn.commit()
        return cursor.lastrowid
    
    def complete_sync_log(self, log_id: int, status: str, events_count: int = 0,
                         error_message: Optional[str] = None):
        """Complete a sync log entry."""
        cursor = self.conn.cursor()
        completed_at = datetime.now().isoformat()
        
        cursor.execute("""
            UPDATE sync_log 
            SET status = ?, 
                events_count = ?,
                error_message = ?,
                completed_at = ?,
                duration_seconds = (julianday(?) - julianday(started_at)) * 86400
            WHERE id = ?
        """, (status, events_count, error_message, completed_at, completed_at, log_id))
        self.conn.commit()
    
    def get_last_sync(self, job_type: str) -> Optional[Dict]:
        """Get the last sync log for a job type."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM sync_log 
            WHERE job_type = ? 
            ORDER BY started_at DESC 
            LIMIT 1
        """, (job_type,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_sync_history(self, job_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get sync history."""
        cursor = self.conn.cursor()
        
        if job_type:
            cursor.execute("""
                SELECT * FROM sync_log 
                WHERE job_type = ?
                ORDER BY started_at DESC 
                LIMIT ?
            """, (job_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM sync_log 
                ORDER BY started_at DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    # ===== SETTINGS OPERATIONS =====
    
    def set_setting(self, key: str, value: Any):
        """Set a setting value."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, json.dumps(value)))
        self.conn.commit()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        
        if row:
            try:
                return json.loads(row[0])
            except:
                return row[0]
        return default
    
    # ===== CHANGE TRACKING OPERATIONS =====
    
    def record_change(self, change_type: str, event_id: str, event_title: str,
                     old_time: Optional[str] = None, new_time: Optional[str] = None):
        """Record an event change for notification."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO event_changes 
            (change_type, event_id, event_title, old_time, new_time)
            VALUES (?, ?, ?, ?, ?)
        """, (change_type, event_id, event_title, old_time, new_time))
        self.conn.commit()
    
    def get_unnotified_changes(self) -> List[Dict]:
        """Get changes that haven't been notified yet."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM event_changes 
            WHERE notified = 0 
            ORDER BY detected_at ASC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def mark_changes_notified(self, change_ids: List[int]):
        """Mark changes as notified."""
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(change_ids))
        cursor.execute(f"""
            UPDATE event_changes 
            SET notified = 1 
            WHERE id IN ({placeholders})
        """, change_ids)
        self.conn.commit()
    
    def cleanup_old_changes(self, days: int = 30):
        """Delete old change records."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM event_changes 
            WHERE notified = 1 
            AND julianday('now') - julianday(detected_at) > ?
        """, (days,))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
