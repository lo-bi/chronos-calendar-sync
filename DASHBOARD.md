# Dashboard Feature

## Overview

The Chronos Dashboard provides a beautiful web interface to visualize your work statistics and planning. It includes:

- 📊 **Monthly statistics** for the past year with 80% time tracking
- 📈 **Visual charts** showing hours worked vs. expected hours
- 📅 **Upcoming weeks** planning view
- 🔐 **Password protected** with 30-day session persistence
- 📱 **Fully responsive** - works on desktop, tablet, and mobile

## Features

### Statistics Cards
- **This Month**: Current month hours with progress toward 80% target
- **This Week**: Current week hours vs. 28h target
- **Past Year**: Total hours and monthly average
- **Contract Status**: 80% part-time indicator

### Charts
- **Monthly Hours Chart**: Bar chart showing past 12 months with actual vs. expected hours (121h/month at 80%)
- **Upcoming Weeks Chart**: Line chart showing planned hours for upcoming weeks

### Detailed Table
- Month-by-month breakdown
- Hours worked vs. expected
- Percentage of target achieved
- Days worked per month
- Color-coded performance indicators

## Setup

### 1. Set Dashboard Password

Edit your `.env` file:

```bash
# Dashboard Configuration
DASHBOARD_PASSWORD=YourSecurePassword123
FLASK_SECRET_KEY=your-random-secret-key-for-sessions
```

**Important**: Change the default password to something secure!

### 2. Start the Application

```bash
# Locally
python main.py

# With Docker
docker-compose up -d
```

### 3. Access the Dashboard

Open your browser and navigate to:
```
http://localhost:8000/
```

Or if running on Raspberry Pi at `192.168.1.100`:
```
http://192.168.1.100:8000/
```

### 4. Login

- Enter your `DASHBOARD_PASSWORD`
- Check "Se souvenir de moi" to stay logged in for 30 days
- Click "Se connecter"

## Understanding Your Stats

### 80% Time Calculation

For an 80% part-time position:
- **Full-time**: 35 hours/week
- **80% time**: 28 hours/week
- **Monthly target**: ~121 hours (28h × 4.33 weeks)

### Color Indicators

**In the table:**
- 🟢 **Green**: Meeting or exceeding target (≥100%)
- 🟡 **Yellow**: Close to target (90-99%)
- 🔴 **Red**: Below target (<90%)

### Chart Interpretation

**Monthly Chart (Bar)**:
- Blue bars = Your actual hours
- Gray bars = 80% target (121h)
- Compare to see if you're on track

**Weekly Chart (Line)**:
- Purple line = Your planned hours
- Gray dashed line = 80% target (28h/week)
- Shows upcoming workload

## Security

### Password Protection
- Dashboard is protected by password authentication
- Password stored in environment variable (not in code)
- Sessions last 30 days if "remember me" is checked
- Logout available in top navigation

### Best Practices
1. Use a strong, unique password
2. Keep `.env` file secure and never commit it to git
3. Change `FLASK_SECRET_KEY` to a random string
4. If exposing to internet, use HTTPS (reverse proxy with nginx/caddy)

## Customization

### Change Session Duration

Edit `main.py`:
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Change days
```

### Adjust 80% Calculation

If your contract is different, edit `dashboard.py`:
```python
EXPECTED_MONTHLY_HOURS_80 = 121.24  # Adjust this
EXPECTED_WEEKLY_HOURS_80 = 28       # And this
```

### Styling

The dashboard uses Tailwind CSS via CDN. To customize colors:

Edit `templates/dashboard.html` and change Tailwind classes:
- `bg-indigo-600` → Change primary color
- `text-gray-800` → Change text color
- `rounded-xl` → Change border radius

## Troubleshooting

### "Dashboard password not set"
→ Add `DASHBOARD_PASSWORD` to your `.env` file

### "Unauthorized" error when viewing stats
→ Login again (session may have expired)

### No data showing
→ Wait for first sync to complete, or check that `SYNC_DAYS_AHEAD` is set to at least 90 days for yearly stats

### Charts not loading
→ Check browser console for errors. Make sure Chart.js CDN is accessible.

### Session not persisting
→ Make sure you check "Se souvenir de moi" when logging in

## Mobile Access

The dashboard is fully responsive and works great on mobile:

1. Find your computer/Raspberry Pi's IP address
2. Open browser on phone
3. Navigate to `http://YOUR_IP:8000`
4. Login and enjoy!

**Tip**: Add to your iPhone home screen for quick access:
1. Open in Safari
2. Tap Share button
3. "Add to Home Screen"
4. Now it opens like an app!

## Data Privacy

- All data stays on your server
- No external analytics or tracking
- Charts render client-side (your browser)
- Only you can access with the password

## Future Enhancements

Potential additions:
- Export data to CSV/Excel
- Vacation planning calculator
- Comparison with colleagues (anonymized)
- Email reports
- Dark mode toggle

## API Endpoints

If you want to build custom integrations:

### Check Authentication
```bash
GET /api/dashboard/check-auth
```

### Login
```bash
POST /api/dashboard/login
Content-Type: application/json

{
  "password": "your-password",
  "remember": true
}
```

### Get Statistics
```bash
GET /api/dashboard/stats
# Requires authentication
```

Returns:
```json
{
  "summary": {
    "total_hours_past_year": 1450.5,
    "current_month_hours": 125.0,
    "current_week_hours": 30.5,
    "average_monthly_hours": 120.8
  },
  "past_year_monthly": [...],
  "upcoming_weeks": [...],
  "last_updated": "2025-10-26T15:30:00"
}
```

## Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Verify `.env` configuration
3. Test API endpoints manually with `curl`
4. Open an issue on GitHub
