"""
Push notification service using ntfy.sh
"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Notifier:
    """Send push notifications via ntfy.sh"""
    
    def __init__(self, topic: str, server: str = "https://ntfy.sh", enabled: bool = True):
        """
        Initialize notifier
        
        Args:
            topic: Your unique ntfy topic name
            server: ntfy server URL (default: public ntfy.sh)
            enabled: Whether notifications are enabled
        """
        self.topic = topic
        self.server = server.rstrip('/')
        self.enabled = enabled
        self.url = f"{self.server}/{self.topic}"
        
    def send(self, title: str, message: str, priority: str = "default", tags: Optional[list] = None) -> bool:
        """
        Send a push notification
        
        Args:
            title: Notification title
            message: Notification message body
            priority: Notification priority (min, low, default, high, urgent)
            tags: List of emoji tags (e.g., ['calendar', 'warning'])
            
        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False
            
        try:
            headers = {
                "Title": title,
                "Priority": priority,
            }
            
            if tags:
                headers["Tags"] = ",".join(tags)
            
            # Encode message as UTF-8 to handle emojis
            response = requests.post(
                self.url,
                data=message.encode('utf-8'),
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Notification sent: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def send_new_shift(self, title: str, date: str, time: str = None) -> bool:
        """Send notification for a new shift"""
        time_str = f" à {time}" if time else ""
        message = f"Nouveau créneau ajouté : {title}{time_str} le {date}"
        return self.send(
            title="Nouveau Creneau",  # ASCII-safe title
            message=f"🆕 {message}",  # Emoji in message body
            priority="default",
            tags=["calendar", "heavy_plus_sign"]
        )
    
    def send_deleted_shift(self, title: str, date: str, time: str = None) -> bool:
        """Send notification for a deleted shift"""
        time_str = f" à {time}" if time else ""
        message = f"Créneau supprimé : {title}{time_str} le {date}"
        return self.send(
            title="Creneau Supprime",  # ASCII-safe title
            message=f"❌ {message}",  # Emoji in message body
            priority="default",
            tags=["calendar", "x"]
        )
    
    def send_modified_shift(self, title: str, old_info: str, new_info: str) -> bool:
        """Send notification for a modified shift"""
        message = f"{title}\nAvant : {old_info}\nMaintenant : {new_info}"
        return self.send(
            title="Creneau Modifie",  # ASCII-safe title
            message=f"✏️ {message}",  # Emoji in message body
            priority="default",
            tags=["calendar", "pencil2"]
        )
    
    def send_test(self) -> bool:
        """Send a test notification"""
        return self.send(
            title="Chronos Sync Actif",
            message="🔔 Les notifications fonctionnent ! Vous serez notifié de tout changement dans votre planning.",
            priority="low",
            tags=["white_check_mark"]
        )
