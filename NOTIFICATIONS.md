# Push Notifications Setup Guide

Get instant notifications on your iPhone when your Chronos planning changes!

## Quick Setup (5 minutes)

### 1. Install ntfy App

Download the **free** ntfy app from the App Store:
- 🔗 [ntfy - push notifications](https://apps.apple.com/us/app/ntfy/id1625396347)
- No account needed
- 100% free
- Works with the public ntfy.sh server

### 2. Choose Your Topic

Pick a **unique, random topic name** for privacy. This is your private notification channel.

**Examples:**
- `chronos-laura-planning-8472`
- `mywork-schedule-abc123xyz`
- `planning-secret-789def`

⚠️ **Important:** Make it random! Anyone who knows your topic name can send you notifications.

### 3. Subscribe in the App

1. Open the ntfy app
2. Tap the **"+"** button
3. Enter your topic name (e.g., `chronos-laura-planning-8472`)
4. Tap **Subscribe**

### 4. Configure Your App

Edit your `.env` file:

```bash
# Enable notifications
ENABLE_NOTIFICATIONS=true

# Your unique topic (use your own random string!)
NTFY_TOPIC=chronos-laura-planning-8472

# Server (default is free public server)
NTFY_SERVER=https://ntfy.sh
```

### 5. Restart the App

```bash
# If using Docker
docker-compose restart

# If running locally
# Stop the app (Ctrl+C) and start again
python main.py
```

## What You'll Get Notified About

### 🆕 New Shifts
When a new shift is added to your planning:
```
🆕 New Shift
New shift added: Work: 07:15-19:15 on Fri Nov 01
```

### ❌ Deleted Shifts
When a shift is removed:
```
❌ Shift Deleted
Shift removed: Work: 08:00-17:00 on Tue Nov 05
```

### ✏️ Modified Shifts
When shift details change (time, date, type):
```
✏️ Shift Modified
Work: 08:00-17:00
Was: Mon Nov 04 08:00-17:00
Now: Mon Nov 04 07:00-16:00
```

### 🔔 Test Notification
On first start, you'll get:
```
🔔 Chronos Sync Active
Notifications are working! You'll be notified of any planning changes.
```

## Smart Filtering

The app **won't** notify you about:
- Events added exactly at your `SYNC_DAYS_AHEAD` boundary (to avoid noise as the sync window moves forward)
- The initial sync (only subsequent changes are notified)

## Privacy & Security

### Is it secure?
- ✅ Uses HTTPS for all communication
- ✅ Messages are **not encrypted** on ntfy.sh servers
- ✅ But they're deleted after delivery
- ✅ No account = no email/phone number tied to messages

### Can others see my notifications?
- ⚠️ Anyone who knows your topic name can send notifications to it
- ✅ Make your topic name **long and random**
- ✅ Don't share your topic name
- ✅ For extra security, self-host ntfy (see below)

### What data is sent?
Only the information you see in the notification:
- Shift title (e.g., "Work: 07:15-19:15")
- Date and time
- Change type (new/deleted/modified)

**Not sent:**
- Your Chronos username/password
- Your iCloud credentials
- Full event descriptions
- Any other personal data

## Self-Hosting ntfy (Optional)

For maximum privacy, you can run your own ntfy server:

### On Raspberry Pi

```bash
# Install ntfy
curl -sSL https://archive.heckel.io/apt/pubkey.txt | sudo apt-key add -
sudo apt install ntfy
sudo systemctl enable ntfy
sudo systemctl start ntfy
```

### Update Your Config

```bash
# In .env, change the server to your Raspberry Pi IP
NTFY_SERVER=http://192.168.1.100:80
NTFY_TOPIC=my-private-topic
```

### In the ntfy App

1. Tap Settings
2. Add your server URL
3. Subscribe to your topic on your server

## Troubleshooting

### Not receiving notifications?

**Check 1:** Is the app running?
```bash
docker-compose logs -f
```
Look for: `Notifications enabled` in the logs

**Check 2:** Is the topic name correct?
- Check `.env` file
- Check subscription in ntfy app
- They must match exactly (case-sensitive!)

**Check 3:** Did you subscribe in the app?
- Open ntfy app
- Make sure your topic appears in the list

**Check 4:** Test it manually
Visit in your browser:
```
https://ntfy.sh/YOUR_TOPIC_NAME
```
Then send a test:
```bash
curl -d "Test notification" https://ntfy.sh/YOUR_TOPIC_NAME
```

### Getting too many notifications?

**Increase sync interval:**
```bash
# In .env
SYNC_INTERVAL_MINUTES=120  # Check every 2 hours instead of 1
```

**Disable notifications temporarily:**
```bash
# In .env
ENABLE_NOTIFICATIONS=false
```

### Want to disable notifications?

```bash
# In .env
ENABLE_NOTIFICATIONS=false
```

The app will continue syncing to iCloud but won't send notifications.

## More Information

- 📱 [ntfy.sh Documentation](https://ntfy.sh)
- 🐳 [Self-hosting Guide](https://docs.ntfy.sh/install/)
- 🔒 [Privacy Policy](https://ntfy.sh/privacy)

## Questions?

Feel free to open an issue on GitHub!
