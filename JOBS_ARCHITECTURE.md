# Chronos Calendar Sync - Architecture Jobs

## 🎯 Architecture

L'application est maintenant divisée en **jobs indépendants** qui s'exécutent à des intervalles différents :

### 📦 Jobs

1. **Fetch Chronos** (`jobs/fetch_chronos.py`)
   - **Fréquence**: Toutes les heures
   - **Rôle**: Récupère les données de Chronos (365 jours passés + 90 jours futurs)
   - **Stockage**: Base de données SQLite
   - **Avantage**: Authentification Chronos 1x/heure au lieu de chaque sync

2. **Sync Calendar** (`jobs/sync_calendar.py`)
   - **Fréquence**: Toutes les 15-30 minutes (configurable)
   - **Rôle**: Synchronise les événements futurs de la DB vers iCloud
   - **Source**: Base de données SQLite
   - **Avantage**: Sync plus fréquent sans surcharger Chronos

3. **Notify Changes** (`jobs/notify_changes.py`)
   - **Fréquence**: Après chaque sync calendar (+2 min)
   - **Rôle**: Détecte les changements et envoie les notifications ntfy.sh
   - **Stockage**: Table event_changes pour traçabilité
   - **Avantage**: Notifications précises avec historique

4. **Dashboard** (Flask web server)
   - **Rôle**: Interface web pour visualiser les statistiques
   - **Source**: Base de données SQLite
   - **Avantage**: Toujours disponible, même si les jobs échouent

## 💾 Base de Données

SQLite (`chronos_sync.db`) avec 4 tables :

- **events**: Tous les événements Chronos
- **sync_log**: Historique des exécutions (succès/erreurs)
- **settings**: Configuration runtime (dernière exécution, état précédent)
- **event_changes**: Historique des changements pour notifications

## ⚙️ Configuration

Nouvelles variables dans `.env` :

```bash
# Fréquence du sync calendrier (minutes)
CALENDAR_SYNC_MINUTES=15

# Chemin de la base de données
DB_PATH=chronos_sync.db
```

## 🚀 Lancement

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application (tous les jobs + dashboard)
python main_new.py
```

## 📊 Endpoints API

- `GET /` - Dashboard interface
- `GET /api/health` - Health check avec statut des jobs
- `GET /api/dashboard/stats` - Statistiques (authentifié)
- `GET /api/sync-history` - Historique des syncs (authentifié)

## 🔍 Exécution Manuelle des Jobs

Chaque job peut être exécuté indépendamment :

```bash
# Fetch Chronos data
python jobs/fetch_chronos.py

# Sync to calendar
python jobs/sync_calendar.py

# Detect and notify changes
python jobs/notify_changes.py
```

## 📈 Avantages de cette Architecture

✅ **Performance**: Authentification Chronos réduite (1x/heure)  
✅ **Réactivité**: Sync calendar fréquent (15 min) sans surcharge  
✅ **Fiabilité**: Jobs isolés, une erreur n'affecte pas les autres  
✅ **Traçabilité**: Historique complet en DB (sync_log, event_changes)  
✅ **Scalabilité**: Facile d'ajouter de nouveaux jobs  
✅ **Dashboard persistant**: Toujours disponible, même si jobs échouent

## 🔄 Migration depuis l'Ancienne Version

L'ancien `main.py` est conservé. Pour utiliser la nouvelle architecture :

1. Installer APScheduler : `pip install apscheduler>=3.10.4`
2. Lancer `python main_new.py` au lieu de `python main.py`
3. Premier lancement : jobs initiaux s'exécutent immédiatement
4. Database `chronos_sync.db` créée automatiquement

## 📝 Logs

Tous les jobs loggent avec le format :
```
==================================================
JOB: Fetch Chronos Data - STARTED
==================================================
[... détails ...]
==================================================
JOB: Fetch Chronos Data - SUCCESS (44 events)
==================================================
```

## 🛠️ Maintenance

- **Nettoyage automatique**: Événements > 2 ans supprimés
- **Historique limité**: 50 derniers syncs par défaut
- **Notifications tracées**: event_changes avec flag `notified`
