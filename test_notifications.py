#!/usr/bin/env python3
"""
Script de test pour les notifications
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from notifier import Notifier
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_notifications():
    """Test sending notifications"""
    
    # Check if notifications are configured
    topic = os.getenv('NTFY_TOPIC')
    enabled = os.getenv('ENABLE_NOTIFICATIONS', 'false').lower() == 'true'
    
    if not topic:
        print("❌ NTFY_TOPIC n'est pas configuré dans le fichier .env")
        print("\nVeuillez définir NTFY_TOPIC dans votre fichier .env :")
        print("  NTFY_TOPIC=chronos-planning-VOTRE_CHAINE_ALEATOIRE")
        return False
    
    if not enabled:
        print("❌ ENABLE_NOTIFICATIONS est désactivé")
        print("\nVeuillez activer les notifications dans votre fichier .env :")
        print("  ENABLE_NOTIFICATIONS=true")
        return False
    
    print(f"✓ Configuration OK")
    print(f"  Topic: {topic}")
    print(f"  Server: {os.getenv('NTFY_SERVER', 'https://ntfy.sh')}")
    print()
    
    # Create notifier
    notifier = Notifier(
        topic=topic,
        server=os.getenv('NTFY_SERVER', 'https://ntfy.sh'),
        enabled=True
    )
    
    # Send test notification
    print("📱 Envoi de la notification de test...")
    success = notifier.send_test()
    
    if success:
        print("✓ Notification de test envoyée avec succès !")
        print()
        print("Vérifiez l'application ntfy sur votre iPhone - vous devriez voir :")
        print("  Titre: Chronos Sync Actif")
        print("  Message: 🔔 Les notifications fonctionnent !")
        print()
        
        # Send sample notifications
        print("📱 Envoi d'exemples de notifications...")
        print()
        
        print("  1. Nouveau créneau...")
        notifier.send_new_shift("Work: 08:00-17:00", "Lundi 04 Nov", "08:00-17:00")
        
        print("  2. Créneau supprimé...")
        notifier.send_deleted_shift("RTT", "Mardi 05 Nov")
        
        print("  3. Créneau modifié...")
        notifier.send_modified_shift("Work: 08:00-17:00", "Lundi 04 Nov 08:00-17:00", "Lundi 04 Nov 07:00-16:00")
        
        print()
        print("✓ Tous les exemples ont été envoyés !")
        print()
        print("Vous devriez recevoir 4 notifications au total sur votre iPhone.")
        print()
        
        return True
    else:
        print("❌ Échec de l'envoi de la notification")
        print("\nDépannage :")
        print("1. Vérifiez que votre NTFY_TOPIC est correct")
        print("2. Assurez-vous d'être abonné au topic dans l'application ntfy")
        print("3. Essayez de visiter : https://ntfy.sh/" + topic)
        return False

if __name__ == '__main__':
    success = test_notifications()
    sys.exit(0 if success else 1)
