import csv
import os
import pandas as pd
from firebase_manager import FirebaseManager

# Alliance CSV filenames mapped to alliance names
alliance_csv_map = {
    'Gaia': 'assets/Helix Facils Handles - Gaia.csv',
    'Ignis': 'assets/Helix Facils Handles - Ignis.csv',
    'Hydro': 'assets/Helix Facils Handles - Hydro.csv',
    'Cirrus': 'assets/Helix Facils Handles - Cirrus.csv',
}

# GM CSV file
gm_csv_file = 'assets/Helix GM Handles.csv'

# EXCO CSV file
exco_csv_file = 'assets/EXCO Handles.csv'

# Initialize FirebaseManager
firebase = FirebaseManager()


def parse_and_upload_alliance(alliance: str, csv_filename: str):
    """Upload facilitators from alliance CSV files."""
    if not os.path.exists(csv_filename):
        print(f"❌ CSV not found: {csv_filename}")
        return

    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            username = row['Telegram Handle'].strip().lstrip('@')
            name = row['Name'].strip()
            suballiance = row['Suballiance'].strip().upper()

            # Determine collection path
            group = 'Heads' if suballiance in ('FH', 'AFH') else suballiance

            # Determine role
            if suballiance == 'FH':
                role = 'Facilitator Head'
            elif suballiance == 'AFH':
                role = 'Assistant Facilitator Head'
            else:
                role = 'Facilitator'

            doc_path = f"Users/{alliance}/{group}/@{username}"
            print(f"Uploading Facilitator: {doc_path}")

            doc_ref = firebase.db.collection("Users").document(
                alliance).collection(group).document(f"@{username}")
            doc_ref.set({
                'name': name,
                'username': f"@{username}",
                'role': role,
                'alliance': alliance,
                'group': group,
                'is_active': True
            })

    print(f"✅ Uploaded facilitators for alliance: {alliance}")


def parse_and_upload_game_masters():
    """Upload Game Masters from CSV file."""
    if not os.path.exists(gm_csv_file):
        print(f"❌ GM CSV file not found: {gm_csv_file}")
        return

    try:
        with open(gm_csv_file, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            gm_count = 0

            # Print available columns to debug
            print(f"📋 Available columns in GM CSV: {reader.fieldnames}")

            for row in reader:
                # Try different possible column names for name
                name = None
                username = None
                gm_role = None

                # Find name column (handle BOM and case variations)
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['name']:
                        name = row[key].strip()
                        break

                # Find username column
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['telegram handle', 'username', 'handle']:
                        username = row[key].strip().lstrip('@')
                        break

                # Find role column
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['roles', 'role']:
                        gm_role = row[key].strip().upper()
                        break

                # Skip empty rows
                if not name or not username:
                    print(
                        f"⚠️ Skipping GM row with missing data: name='{name}', username='{username}'"
                    )
                    continue

                # Determine collection path and role
                if gm_role == 'GMH':
                    group = 'Heads'
                    role = 'Game Master Head'
                elif gm_role == 'AGMH':
                    group = 'Heads'
                    role = 'Assistant Game Master Head'
                elif gm_role == 'GM':
                    group = 'GM'
                    role = 'Game Master'
                else:
                    print(
                        f"⚠️ Unknown GM role '{gm_role}' for {name}, defaulting to Game Master"
                    )
                    group = 'GM'
                    role = 'Game Master'

                doc_path = f"Users/Game Masters/{group}/@{username}"
                print(f"Uploading Game Master: {doc_path}")

                doc_ref = firebase.db.collection("Users").document(
                    "Game Masters").collection(group).document(f"@{username}")
                doc_ref.set({
                    'name': name,
                    'username': f"@{username}",
                    'role': role,
                    'alliance': 'Game Masters',
                    'group': group,
                    'is_active': True
                })

                gm_count += 1

        print(f"✅ Uploaded {gm_count} Game Masters")

    except Exception as e:
        print(f"❌ Error uploading Game Masters: {str(e)}")
        import traceback
        traceback.print_exc()


def parse_and_upload_exco():
    """Upload EXCO members from CSV file."""
    if not os.path.exists(exco_csv_file):
        print(f"❌ EXCO CSV file not found: {exco_csv_file}")
        return

    try:
        with open(exco_csv_file, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            exco_count = 0

            # Print available columns to debug
            print(f"📋 Available columns in EXCO CSV: {reader.fieldnames}")

            for row in reader:
                # Try different possible column names (case-insensitive and BOM-aware)
                name = None
                username = None
                role = None

                # Find name column (handle BOM character)
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['name']:
                        name = row[key].strip()
                        break

                # Find username column
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['username', 'telegram handle', 'handle']:
                        username = row[key].strip().lstrip('@')
                        break

                # Find role column
                for key in row.keys():
                    clean_key = key.strip().lstrip('\ufeff').lower()
                    if clean_key in ['role', 'roles']:
                        role = row[key].strip()
                        break

                # Skip empty rows
                if not name or not username:
                    print(
                        f"⚠️ Skipping EXCO row with missing data: name='{name}', username='{username}'"
                    )
                    continue

                # Determine group based on role
                if role and role.upper() == 'OWNER':
                    group = 'EXCO'
                    final_role = 'Owner'
                elif role and role.upper() == 'EXCO':
                    group = 'EXCO'
                    final_role = 'EXCO'
                else:
                    print(
                        f"⚠️ Unknown EXCO role '{role}' for {name}, defaulting to EXCO"
                    )
                    group = 'EXCO'
                    final_role = 'EXCO'

                doc_path = f"Users/EXCO/{group}/@{username}"
                print(f"Uploading EXCO Member: {doc_path}")

                doc_ref = firebase.db.collection("Users").document(
                    "EXCO").collection(group).document(f"@{username}")
                doc_ref.set({
                    'name': name,
                    'username': f"@{username}",
                    'role': final_role,
                    'alliance': 'EXCO Staff',
                    'group': group,
                    'is_active': True
                })

                exco_count += 1

        print(f"✅ Uploaded {exco_count} EXCO members")

    except Exception as e:
        print(f"❌ Error uploading EXCO members: {str(e)}")
        import traceback
        traceback.print_exc()


def upload_manual_exco_users():
    """Upload manual EXCO override users (if needed for additional users not in CSV)."""
    # This function is kept for any manual overrides if needed
    # Currently commented out since we're using CSV
    pass


if __name__ == "__main__":
    print("🚀 Starting user upload process...")

    # Upload Facilitators from CSV files
    print("\n📋 Uploading Facilitators...")
    for alliance, csv_name in alliance_csv_map.items():
        parse_and_upload_alliance(alliance, csv_name)

    # Upload Game Masters from CSV file
    print("\n🎮 Uploading Game Masters...")
    parse_and_upload_game_masters()

    # Upload EXCO members from CSV file
    print("\n👑 Uploading EXCO members...")
    parse_and_upload_exco()

    print("\n🎉 Upload complete!")
    print("\n📊 Database Structure Created:")
    print("Users/")
    print("  ├── Gaia/")
    print("  │   ├── Heads/ (FH, AFH)")
    print("  │   ├── G1/, G2/, G3/, ... (Regular Facilitators)")
    print("  ├── Hydro/")
    print("  │   ├── Heads/ (FH, AFH)")
    print("  │   ├── H1/, H2/, H3/, ... (Regular Facilitators)")
    print("  ├── Ignis/")
    print("  │   ├── Heads/ (FH, AFH)")
    print("  │   ├── I1/, I2/, I3/, ... (Regular Facilitators)")
    print("  ├── Cirrus/")
    print("  │   ├── Heads/ (FH, AFH)")
    print("  │   ├── C1/, C2/, C3/, ... (Regular Facilitators)")
    print("  ├── Game Masters/")
    print("  │   ├── Heads/ (GMH, AGMH)")
    print("  │   └── GM/ (Regular Game Masters)")
    print("  └── EXCO/")
    print("      └── EXCO/ (Owner, EXCO members)")
