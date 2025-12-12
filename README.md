# Helix Telebot - Event Management Bot

A Telegram bot for managing camp/orientation events with role-based access, game routing, HP tracking, and Google Sheets integration.

## Features

- **Role-Based Access Control**: Different menus for EXCO, Game Masters, Facilitator Heads, and Facilitators
- **Alliance System**: Supports 4 alliances (Gaia, Hydro, Ignis, Cirrus) with sub-groups
- **Game Routing**: Track game stations and update statuses in real-time
- **HP Dashboard**: Monitor alliance HP across all groups
- **GM Interface**: Game Masters can record match results (Win/Draw/Lost)
- **Google Sheets Integration**: All data synced with Google Sheets for easy viewing
- **Firebase Backend**: User authorization stored in Firebase Firestore

---

## Required Secrets & Environment Variables

You need to set up the following secrets in your deployment environment (Replit Secrets, environment variables, etc.):

### 1. BOT_TOKEN (Required)
Your Telegram Bot Token from BotFather.

**How to get it:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

```
BOT_TOKEN=your_telegram_bot_token_here
```

### 2. FIREBASE_CREDENTIALS (Required)
JSON credentials for Firebase Firestore access.

**How to get it:**
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (or create one)
3. Go to Project Settings > Service Accounts
4. Click "Generate new private key"
5. Copy the entire JSON content

```
FIREBASE_CREDENTIALS={"type": "service_account", "project_id": "your-project", ...}
```

**Firebase Setup:**
- Create a Firestore database in your Firebase project
- Create collections for each alliance: `Gaia`, `Hydro`, `Ignis`, `Cirrus`
- Each collection should have documents with user data:
  ```json
  {
    "username": "@telegram_handle",
    "name": "User Name",
    "group": "G1",
    "role": "Facilitator",
    "is_active": true,
    "alliance": "Gaia"
  }
  ```

### 3. GOOGLE_SERVICE_ACCOUNT_JSON (Required)
JSON credentials for Google Sheets API access.

**How to get it:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API
4. Go to Credentials > Create Credentials > Service Account
5. Create a key (JSON format) and download it
6. Copy the entire JSON content
7. **Important:** Share your Google Sheet with the service account email (found in the JSON as `client_email`)

```
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "your-project", ...}
```

### 4. Optional Environment Variables

```
MAX_HP=100          # Maximum HP value (default: 100)
DEFAULT_HP=100      # Starting HP value (default: 100)
PORT=5000           # Health check server port (default: 5000)
```

---

## Google Sheets Setup

The bot expects a Google Sheet with the following structure:

### Required Sheets (Tabs):
1. **Dry Game** - Day 1 dry games schedule
2. **Night Game** - Day 1 night games schedule  
3. **Treasure Hunt (AM)** - Day 2 morning treasure hunt
4. **Treasure Hunt (PM)** - Day 2 afternoon treasure hunt
5. **Wet Game** - Day 3 wet games schedule
6. **Results** - Game results tracking

### Sheet Structure:
Each game sheet should have columns:
- `Alliance` - Alliance name (Gaia, Hydro, Ignis, Cirrus)
- `Group` - Sub-group (G1, G2, H1, H2, etc.)
- `Game` - Game/station name
- `Status` - Current status (Player Ready, Stage Engaged, Next Up, Stage Cleared)
- `Time Slot` - Scheduled time

### Spreadsheet ID:
Update the spreadsheet ID in `sheets_manager.py` line 26:
```python
self.spreadsheet = client.open_by_key("YOUR_SPREADSHEET_ID_HERE")
```
The ID is found in your Google Sheets URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit`

---

## Firebase Structure

### Alliance Collections
Create these collections in Firestore:
- `Gaia`
- `Hydro`
- `Ignis`
- `Cirrus`
- `GM` (for Game Masters)
- `EXCO` (for Executive Committee)

### User Document Structure:
```json
{
  "username": "@telegram_handle",
  "name": "Full Name",
  "group": "G1",
  "role": "Facilitator",
  "is_active": true,
  "alliance": "Gaia"
}
```

### Roles:
- `Owner` / `EXCO` - Full access to all features
- `Game Master` / `GM` - Access to GM interface for recording results
- `Facilitator Head` / `Assistant Facilitator Head` - Routing + full HP dashboard
- `Facilitator` - Routing + sub-group HP only

---

## File Structure

```
├── main.py                 # Entry point, bot initialization, health server
├── bot_handlers.py         # All Telegram message/callback handlers
├── firebase_manager.py     # Firebase Firestore operations
├── sheets_manager.py       # Google Sheets integration with caching
├── user_manager.py         # User registration and management
├── config.py               # Configuration and environment variables
├── utils.py                # Helper functions and keyboards
├── upload_users_to_firebase.py    # Script to bulk upload users
├── update_routing_googlesheets.py # Script to update routing data
├── assets/                 # CSV files with user handles (DO NOT COMMIT)
│   ├── EXCO Handles.csv
│   ├── Helix GM Handles.csv
│   └── Helix Facils Handles - *.csv
└── functions/              # Firebase Cloud Functions (optional)
```

---

## Deployment

### On Replit:
1. Fork or import this repository
2. Add all required secrets in the Secrets tab
3. Run the project - it will start automatically

### On Other Platforms:
1. Install dependencies: `pip install -r requirements.txt` or use `pyproject.toml`
2. Set environment variables
3. Run: `python main.py`

### Health Check:
The bot runs a health server on port 5000 with these endpoints:
- `/` - Basic health check
- `/health` - Health status
- `/status` - Detailed status

---

## Customization for Future Batches

### Things to Update:

1. **Spreadsheet ID** (`sheets_manager.py` line 26)
   - Create a new Google Sheet for your batch
   - Update the spreadsheet ID

2. **Alliance Names** (if different)
   - Update `ALLIANCE_NAMES` in `bot_handlers.py`
   - Update Firebase collections accordingly

3. **Game/Day Mappings** (`sheets_manager.py` and `bot_handlers.py`)
   - Update `sheet_day_mapping` for your event schedule
   - Update `DAY_NAMES` dictionary

4. **User Data**
   - Prepare CSV files with facilitator handles
   - Use `upload_users_to_firebase.py` to bulk upload

5. **Treasure Hunt Timing** (`bot_handlers.py`)
   - Update `TREASURE_HUNT_NAMES` for AM/PM allocation per alliance

---

## Potential Improvements / Future Work

Here are ideas for future developers to work on:

### High Priority
- [ ] **Auto-refresh Dashboard**: Add periodic refresh for HP dashboard instead of manual
- [ ] **Notification System**: Send alerts when HP drops below threshold
- [ ] **Export Results**: Button to export game results to PDF/CSV
- [ ] **Multi-language Support**: Add support for different languages

### Medium Priority
- [ ] **Admin Panel**: Web-based admin interface for managing users
- [ ] **Leaderboard**: Real-time leaderboard display
- [ ] **Photo Upload**: Allow facilitators to upload game photos
- [ ] **QR Code Check-in**: Generate QR codes for station check-ins
- [ ] **Scheduled Messages**: Auto-send reminders before games start

### Nice to Have
- [ ] **Analytics Dashboard**: Track engagement and response times
- [ ] **Undo Feature**: Allow reversing accidental status changes
- [ ] **Audit Log**: Track all changes made through the bot
- [ ] **Offline Mode**: Cache data for areas with poor connectivity
- [ ] **Voice Commands**: Support for voice messages

### Code Improvements
- [ ] **Unit Tests**: Add comprehensive test coverage
- [ ] **Error Recovery**: Better handling of API failures
- [ ] **Rate Limiting**: Implement proper rate limiting for API calls
- [ ] **Database Migrations**: Add migration scripts for schema changes
- [ ] **Docker Support**: Add Dockerfile for containerized deployment

---

## Troubleshooting

### Common Issues:

**Bot not responding:**
- Check if BOT_TOKEN is correct
- Ensure only one bot instance is running (409 error means multiple instances)

**Firebase errors:**
- Verify FIREBASE_CREDENTIALS JSON is valid
- Check Firestore rules allow read/write

**Google Sheets errors:**
- Ensure the service account email has Editor access to the sheet
- Check if spreadsheet ID is correct
- Verify sheet names match exactly (case-sensitive)

**409 Conflict Error:**
- Another instance of the bot is running
- Wait 30 seconds and restart, or check for deployed versions using the same token

---

## Support

For questions or issues, contact the EXCO team or raise an issue in this repository.

---

## License

Internal use only - Helix Camp Committee
