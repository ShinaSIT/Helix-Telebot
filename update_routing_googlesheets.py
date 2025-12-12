import os
import json
import gspread
from google.oauth2.service_account import Credentials

# === SETUP GOOGLE SHEETS ACCESS FROM SECRET ===
scope = ['https://www.googleapis.com/auth/spreadsheets']
service_account_info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open("HELIX Telebot")


# === SHEET TO DAY LABEL MAP ===
sheet_day_mapping = {
    "Dry Game": "14 Aug (Day 1)",
    "Night Game": "14 Aug (Day 1)",
    "Treasure Hunt (AM)": "15 Aug (Day 2)",
    "Treasure Hunt (PM)": "15 Aug (Day 2)",
    "Wet Game": "16 Aug (Day 3)"
}

# === STATUS MAPPING ===
status_label_map: Dict[str, str] = {
    'Default': 'Player Ready',
    'In Progress': 'Stage Engaged',
    'Next Station': 'Next Up',
    'Completed': 'Stage Cleared',
}

upload_logs = []

# === PROCESS EACH SHEET ===
for sheet_name, day_label in sheet_day_mapping.items():
    worksheet = spreadsheet.worksheet(sheet_name)
    records = worksheet.get_all_records()

    print(f"📄 Sheet: {sheet_name} - {len(records)} records")
    for row in records:
        alliance = str(row.get("Alliance", "")).strip()
        group = str(row.get("Group", "")).strip()
        if not alliance or not group:
            print(f"⚠️ Missing alliance or group in row: {row}")
            continue

        game = row.get('Game', 'Unknown')
        location = row.get('Location', 'Unknown')
        status = row.get('Status', 'Default')
        status_label = status_label_map.get(status, 'Player Ready')  # type: ignore

        try:
            start_raw = row.get('Start Time')
            end_raw = row.get('End Time')

            start_raw_str = str(start_raw).strip()
            end_raw_str = str(end_raw).strip()

            start_dt = datetime.strptime(start_raw_str, "%H:%M") if start_raw_str else None
            end_dt = datetime.strptime(end_raw_str, "%H:%M") if end_raw_str else None

            start_time_str = start_dt.strftime("%H:%M") if start_dt else ""
            end_time_str = end_dt.strftime("%H:%M") if end_dt else ""

            print(f"✔ {alliance}/{group} | {day_label} | {start_time_str}-{end_time_str} | {game} @ {location} [{status_label}]")
        except Exception as e:
            print(f"⚠️ Skipping {game} due to invalid time in sheet {sheet_name}: {e}")