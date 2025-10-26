# Chronos to iCloud Calendar Sync

A Docker-based application that automatically syncs your Chronos work planning to your iCloud calendar using headless browser authentication. Perfect for carers who need their work schedule accessible on their Apple devices.

## Quick Start

```bash
# 1. Clone/download and navigate to the project
cd chronos-calendar-sync

# 2. Configure credentials
cp .env.example .env
nano .env  # Edit with your credentials

# 3. Run with Docker (recommended)
docker-compose up -d

# OR run locally
pip install -r requirements.txt
playwright install chromium
python main.py
```

That's it! Your calendar will sync automatically every hour.

## Features

- 🔄 Automatic synchronization of work schedules from Chronos
- 📅 Syncs working hours, absences (RTT, CA, etc.), and activities
- ☁️ Direct integration with iCloud Calendar via CalDAV
- 🤖 Headless browser authentication (supports JavaScript-based login)
- 🐳 Docker container ready for Raspberry Pi deployment
- 🏥 Health check endpoint for monitoring
- ⚙️ Configurable sync intervals and date ranges

## Prerequisites

### For iCloud Calendar Access

You need to generate an **App-Specific Password** from Apple:

1. Go to [appleid.apple.com](https://appleid.apple.com/)
2. Sign in with your Apple ID
3. Navigate to **Security** section
4. Under **App-Specific Passwords**, click **Generate Password**
5. Give it a name like "Chronos Sync"
6. Copy the generated password (you'll need this for configuration)

### For Raspberry Pi

- Raspberry Pi with Docker installed
- Internet connection
- At least 512MB of free RAM

## Installation

### 1. Clone or Download the Project

```bash
mkdir chronos-sync
cd chronos-sync
# Copy all project files here
```

### 2. Configure the Application

The application uses **environment variables** for configuration.

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Then edit `.env` with your credentials:

```bash
# Chronos Configuration
CHRONOS_USERNAME=your_username
CHRONOS_PASSWORD=your_password
CHRONOS_BASE_URL=https://chpcb.chronos-saas.com
CHRONOS_AUTH_URL=https://auth-saas-chronos.asys.fr

# iCloud Calendar Configuration
ICALENDAR_URL=https://caldav.icloud.com
ICALENDAR_USERNAME=your-apple-id@icloud.com
ICALENDAR_PASSWORD=xxxx-xxxx-xxxx-xxxx
ICALENDAR_CALENDAR_NAME=Chronos Planning

# Sync Configuration
SYNC_DAYS_AHEAD=7
SYNC_INTERVAL_MINUTES=60

# Application Configuration
APP_PORT=8000
APP_HOST=0.0.0.0
```

**Required environment variables:**
- `CHRONOS_USERNAME`, `CHRONOS_PASSWORD`
- `ICALENDAR_USERNAME`, `ICALENDAR_PASSWORD`

**Optional environment variables** (with defaults):
- `CHRONOS_BASE_URL` (default: `https://chpcb.chronos-saas.com`)
- `CHRONOS_AUTH_URL` (default: `https://auth-saas-chronos.asys.fr`)
- `ICALENDAR_URL` (default: `https://caldav.icloud.com`)
- `ICALENDAR_CALENDAR_NAME` (default: `Chronos Planning`)
- `SYNC_DAYS_AHEAD` (default: `7`)
- `SYNC_INTERVAL_MINUTES` (default: `60`)
- `APP_PORT` (default: `8000`)
- `APP_HOST` (default: `0.0.0.0`)

### 3. Build and Run with Docker

**Step 1:** Create a `.env` file with your credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

**Step 2:** Build and run:

```bash
# Build the Docker image (this will take a few minutes as it installs Playwright browsers)
docker-compose build

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f
```

**Note:** The first build will take longer as it downloads and installs Chromium for headless authentication.

The application will:
- Start immediately and perform the first sync using headless browser authentication
- Continue syncing every hour (or your configured interval)
- Expose port 8000 for the health check endpoint

### How Authentication Works

The application uses Playwright (headless Chromium) to:
1. Navigate to the Chronos login page
2. Fill in your credentials
3. Submit the form and wait for authentication
4. Extract session cookies for subsequent API calls

This approach handles JavaScript-based authentication flows that cannot be replicated with simple HTTP requests.

## Option 2: Running Directly with Python

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

This downloads the Chromium browser needed for headless authentication.

### 3. Configure Environment Variables

Create a `.env` file or export variables:

```bash
# Option A: Create .env file
cp .env.example .env
# Edit .env with your credentials

# Option B: Export directly
export CHRONOS_USERNAME="your_username"
export CHRONOS_PASSWORD="your_password"
export ICALENDAR_USERNAME="your-apple-id@icloud.com"
export ICALENDAR_PASSWORD="xxxx-xxxx-xxxx-xxxx"
```

### 4. Run the app

```bash
python main.py
```

### Health Check Endpoint

Check the sync status at any time:

```bash
curl http://localhost:8000/health
```

Response example:
```json
{
  "status": "success",
  "last_run": "2025-10-26T14:30:00",
  "last_error": null,
  "events_synced": 42
}
```

Status values:
- `never_run`: Application just started
- `success`: Last sync completed successfully
- `failed`: Last sync failed (check `last_error`)

### Accessing from Raspberry Pi Network

If your Raspberry Pi is at IP `192.168.1.100`:
```bash
curl http://192.168.1.100:8000/health
```

## Configuration Options

### Sync Period

Control how far ahead to sync:
```yaml
sync:
  days_ahead: 60  # Sync next 60 days (default)
```

### Sync Interval

Control how often to sync:
```yaml
sync:
  interval_minutes: 60  # Sync every hour (default)
```

Common intervals:
- `30`: Every 30 minutes (frequent updates)
- `60`: Every hour (recommended)
- `120`: Every 2 hours (less frequent)
- `360`: Every 6 hours (minimal)

## Viewing Your Calendar

After the first sync:

1. Open **Calendar** app on iPhone/iPad/Mac
2. Look for a calendar named **"Chronos Planning"** (or your configured name)
3. Enable it to view your work schedule

### Event Types

The sync includes:

- **Work Hours**: Shows as "Work: HH:MM-HH:MM"
- **Absences**: Shows as "RTT", "CA", etc. with descriptions
- **Activities**: Shows as "Activity: NAME"

Events include details like:
- Working hours
- Duration
- Type of absence
- Activity descriptions

## Troubleshooting

### Authentication Fails

**Error**: "Authentication failed"

**Solutions**:
1. Verify your Chronos credentials in `config.yaml`
2. Check if you can log in to Chronos web interface
3. Look at the logs: `docker-compose logs`

### Calendar Connection Fails

**Error**: "Failed to connect to calendar"

**Solutions**:
1. Verify your Apple ID is correct
2. Make sure you're using an **app-specific password**, not your regular Apple ID password
3. Generate a new app-specific password at appleid.apple.com
4. Check your internet connection

### Calendar Not Appearing

**Solutions**:
1. Wait a few minutes for iCloud to sync
2. Open Calendar app and go to **Calendars** view
3. Make sure "Chronos Planning" calendar is checked/enabled
4. Try force-closing and reopening the Calendar app

### Port Already in Use

**Error**: "Port 8000 already in use"

**Solution**: Change the port in `config.yaml`:
```yaml
app:
  port: 8001  # Use different port
```

And update `docker-compose.yml`:
```yaml
ports:
  - "8001:8001"  # Update external port
```

### Viewing Detailed Logs

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View last 50 lines
docker-compose logs --tail=50
```

## Docker Commands

```bash
# Start the service
docker-compose up -d

# Stop the service
docker-compose stop

# Restart the service
docker-compose restart

# View logs
docker-compose logs -f

# Update after code changes
docker-compose down
docker-compose build
docker-compose up -d

# Remove everything (including data)
docker-compose down -v
```

## File Structure

```
chronos-calendar-sync/
├── main.py                 # Main application and scheduler
├── chronos_client.py       # Chronos API authentication and fetching
├── chronos_parser.py       # XML parsing for Chronos responses
├── calendar_sync.py        # iCloud CalDAV integration
├── config.yaml             # Configuration file (edit this!)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker build instructions
├── docker-compose.yml      # Docker Compose configuration
├── README.md               # This file
└── data/                   # Persistent data (created automatically)
```

## Data Privacy & Security

- All credentials are stored in environment variables or `.env` file
- **Never commit `.env` files to version control**
- No data is sent to third parties
- The application only communicates with:
  - Chronos servers (to fetch your schedule)
  - iCloud servers (to sync your calendar)
- For production: Consider using Docker secrets or a secure vault for credentials

## Updating

To update the application:

```bash
# Stop the container
docker-compose down

# Pull/copy new code

# Rebuild and start
docker-compose build
docker-compose up -d
```

## Support

### Common Issues

1. **Events duplicated**: The app clears old events before syncing. If you see duplicates, restart the sync.
2. **Old events remain**: Events outside the sync window (60 days) are not automatically removed.
3. **Sync too frequent**: Increase `interval_minutes` in config.
4. **Missing events**: Check logs for parsing errors, some event types may need adjustment.

### Monitoring

Set up a simple monitoring script:

```bash
#!/bin/bash
# check-sync.sh
STATUS=$(curl -s http://localhost:8000/health | jq -r .status)
if [ "$STATUS" != "success" ]; then
  echo "Sync failed! Status: $STATUS"
  # Send notification, email, etc.
fi
```

Run it with cron every hour:
```bash
0 * * * * /path/to/check-sync.sh
```

## License

This project is provided as-is for personal use.

## Credits

Built for care workers using the Chronos SAAS planning system.
