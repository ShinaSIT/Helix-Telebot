import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import List, Dict, Optional, Any
import os
import json
import logging
import time

logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    """Optimized manager class with caching and batch processing to avoid API quota limits."""

    def __init__(self):
        """Initialize Google Sheets connection and mappings."""
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        service_account_info = json.loads(
            os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=scope)
        client = gspread.authorize(creds)

        self.spreadsheet = client.open_by_key(
            "15iTCNjnwFNiCeVN-cNEwv6OMwSPenUQrGptNH5wU3e8")

        # Sheet name mappings
        self.sheet_day_mapping = {
            "day1_dry": "Dry Game",
            "day1_night": "Night Game",
            "day2_treasure": "Treasure Hunt (PM)",
            "day3_wet": "Wet Game"
        }

        # Alliance-specific sheet mapping for treasure hunt
        self.treasure_hunt_mapping = {
            "Gaia": "Treasure Hunt (PM)",
            "Hydro": "Treasure Hunt (AM)",
            "Ignis": "Treasure Hunt (AM)",
            "Cirrus": "Treasure Hunt (PM)"
        }

        # Status label mappings
        self.status_label_map = {
            'Default': 'Player Ready',
            'In Progress': 'Stage Engaged',
            'Next Station': 'Next Up',
            'Completed': 'Stage Cleared'
        }

        # Day mapping for GM interface
        self.gm_day_mapping = {
            "day1_dry": "Dry Game",
            "day1_night": "Night Game",
            "day2_treasure": "Treasure Hunt",
            "day3_wet": "Wet Game"
        }

        # ========================================
        # CACHING SYSTEM
        # ========================================
        self._results_cache = None
        self._results_cache_timestamp = None
        self._day_sheet_cache = {}  # Cache for individual day sheets
        self._day_sheet_cache_timestamp = {}
        self._cache_duration = 60  # Cache for 60 seconds

        logger.info("GoogleSheetsManager initialized with caching system")

    # ========================================
    # CACHING METHODS
    # ========================================

    def _get_cached_results(self) -> List[Dict]:
        """Get cached Results sheet data or fetch if cache is stale."""
        current_time = time.time()

        # Check if cache is valid
        if (self._results_cache is not None
                and self._results_cache_timestamp is not None
                and current_time - self._results_cache_timestamp
                < self._cache_duration):
            logger.info("Using cached Results sheet data")
            return self._results_cache

        # Fetch fresh data
        try:
            logger.info("Fetching fresh Results sheet data")
            worksheet = self.spreadsheet.worksheet("Results")
            records = worksheet.get_all_records()

            # Update cache
            self._results_cache = records
            self._results_cache_timestamp = current_time

            logger.info(f"Cached {len(records)} records from Results sheet")
            return records

        except Exception as e:
            logger.error(f"Error fetching Results sheet: {e}")
            # Return stale cache if available
            if self._results_cache is not None:
                logger.warning("Using stale cache due to API error")
                return self._results_cache
            return []

    def _get_cached_day_sheet(self, sheet_name: str) -> List[Dict]:
        """Get cached day sheet data or fetch if cache is stale."""
        current_time = time.time()

        # Check if cache is valid
        if (sheet_name in self._day_sheet_cache
                and sheet_name in self._day_sheet_cache_timestamp
                and current_time - self._day_sheet_cache_timestamp[sheet_name]
                < self._cache_duration):
            logger.info(f"Using cached data for sheet: {sheet_name}")
            return self._day_sheet_cache[sheet_name]

        # Fetch fresh data
        try:
            logger.info(f"Fetching fresh data for sheet: {sheet_name}")
            worksheet = self.spreadsheet.worksheet(sheet_name)
            records = worksheet.get_all_records()

            # Update cache
            self._day_sheet_cache[sheet_name] = records
            self._day_sheet_cache_timestamp[sheet_name] = current_time

            logger.info(
                f"Cached {len(records)} records from sheet: {sheet_name}")
            return records

        except Exception as e:
            logger.error(f"Error fetching sheet {sheet_name}: {e}")
            # Return stale cache if available
            if sheet_name in self._day_sheet_cache:
                logger.warning(
                    f"Using stale cache for sheet {sheet_name} due to API error"
                )
                return self._day_sheet_cache[sheet_name]
            return []

    def _invalidate_cache(self):
        """Invalidate all caches (call after updates)."""
        self._results_cache = None
        self._results_cache_timestamp = None
        self._day_sheet_cache.clear()
        self._day_sheet_cache_timestamp.clear()
        logger.info("All caches invalidated")

    def _invalidate_results_cache(self):
        """Invalidate only Results sheet cache."""
        self._results_cache = None
        self._results_cache_timestamp = None
        logger.info("Results sheet cache invalidated")

    # ========================================
    # OPTIMIZED HP/POINTS SYSTEM
    # ========================================

    def get_suballiance_hp(self, alliance: str, group: str) -> int:
        """Get current HP for a specific suballiance from cached Results sheet."""
        try:
            records = self._get_cached_results()

            total_hp = 0
            for row in records:
                row_alliance = str(row.get("Alliance", "")).strip()
                row_group = str(row.get("Group", "")).strip()

                if row_alliance == alliance and row_group == group:
                    hp_value = row.get("HP", 0)
                    if hp_value == "":
                        hp_value = 0
                    total_hp += int(hp_value) if str(hp_value).isdigit() else 0

            logger.info(
                f"Total HP for {alliance}/{group} from cached Results: {total_hp}"
            )
            return total_hp

        except Exception as e:
            logger.error(
                f"Error getting HP from cached Results for {alliance}/{group}: {e}"
            )
            return 0

    def get_all_suballiance_hp(self) -> Dict[str, Dict[str, int]]:
        """Get HP for all suballiances from cached Results sheet."""
        try:
            alliance_hp = {}
            records = self._get_cached_results()

            # Initialize structure
            alliances = ["Gaia", "Hydro", "Ignis", "Cirrus"]
            for alliance in alliances:
                alliance_hp[alliance] = {}

            # Process each row in cached Results
            for row in records:
                alliance = str(row.get("Alliance", "")).strip()
                group = str(row.get("Group", "")).strip()
                hp_value = row.get("HP", 0)

                if alliance in alliance_hp and group:
                    if hp_value == "":
                        hp_value = 0
                    hp = int(hp_value) if str(hp_value).isdigit() else 0

                    if group not in alliance_hp[alliance]:
                        alliance_hp[alliance][group] = 0
                    alliance_hp[alliance][group] += hp

            return alliance_hp

        except Exception as e:
            logger.error(f"Error getting all HP from cached Results: {e}")
            return {}

    def award_points(self, alliance: str, group: str, game: str,
                     points: int) -> bool:
        """Award points and invalidate cache."""
        try:
            if not (0 <= points <= 5):
                logger.error(f"Invalid points value: {points}. Must be 0-5.")
                return False

            worksheet = self.spreadsheet.worksheet("Results")
            records = worksheet.get_all_records()

            for idx, row in enumerate(records, start=2):
                row_alliance = str(row.get("Alliance", "")).strip()
                row_group = str(row.get("Group", "")).strip()
                row_game = str(row.get("Game", "")).strip()

                if (row_alliance == alliance and row_group == group
                        and row_game == game):
                    worksheet.update_cell(idx, 5, points)
                    logger.info(
                        f"Awarded {points} points to {alliance}/{group} for {game}"
                    )

                    # Invalidate cache after update
                    self._invalidate_results_cache()
                    return True

            logger.warning(f"Game not found: {alliance}/{group}/{game}")
            return False

        except Exception as e:
            logger.error(f"Error awarding points: {e}")
            return False

    def get_hp_color(self, hp: int) -> str:
        """Get heart color based on HP (0-100 scale)."""
        if hp >= 81:
            return "💚"  # Green: 81-100
        elif hp >= 61:
            return "💛"  # Yellow: 61-80
        elif hp >= 41:
            return "🧡"  # Orange: 41-60
        elif hp >= 21:
            return "❤️"  # Red: 21-40
        else:
            return "🖤"  # Black: 0-20

    def get_alliance_totals(self) -> Dict[str, int]:
        """Get total HP for each alliance (for owner dashboard)."""
        try:
            alliance_totals = {}
            all_hp = self.get_all_suballiance_hp()

            for alliance, groups in all_hp.items():
                total = sum(groups.values())
                alliance_totals[alliance] = total

            return alliance_totals

        except Exception as e:
            logger.error(f"Error getting alliance totals: {e}")
            return {}

    # ========================================
    # OPTIMIZED BATCH PROCESSING METHODS
    # ========================================

    def get_alliance_summary_batch(self, alliance: str,
                                   day_key: str) -> Dict[str, List[Dict]]:
        """Get alliance summary with minimal API calls using batch processing."""
        try:
            logger.info(
                f"Getting batch alliance summary for {alliance} on {day_key}")

            # Get all groups for this alliance (uses cached Results data)
            suballiances = self.get_all_suballiances_for_alliance(alliance)
            if not suballiances:
                logger.warning(
                    f"No suballiances found for alliance: {alliance}")
                return {}

            # Determine sheet name
            if day_key == "day2_treasure":
                sheet_name = self.treasure_hunt_mapping.get(alliance)
            else:
                sheet_name = self.sheet_day_mapping.get(day_key)

            if not sheet_name:
                logger.error(f"No sheet mapping found for day_key: {day_key}")
                return {}

            # ONE API call to get all data from day sheet (cached)
            day_records = self._get_cached_day_sheet(sheet_name)

            # ONE API call to get all Results data (cached)
            results_records = self._get_cached_results()

            # Build HP lookup dictionary for fast access
            hp_lookup = {}
            for row in results_records:
                key = f"{row.get('Alliance', '').strip()}|{row.get('Group', '').strip()}|{row.get('Game', '').strip()}"
                hp_value = row.get("HP", 0)
                try:
                    hp_lookup[key] = int(hp_value) if hp_value != "" else 0
                except (ValueError, TypeError):
                    hp_lookup[key] = 0

            # Process all groups at once
            summary_data = {}
            for group in suballiances:
                group_games = []

                for row in day_records:
                    if (str(row.get("Alliance", "")).strip() == alliance
                            and str(row.get("Group", "")).strip() == group):

                        game_name = str(row.get("Game", "")).strip()
                        hp_key = f"{alliance}|{group}|{game_name}"
                        hp = hp_lookup.get(hp_key, 0)

                        game_data = {
                            "game": game_name,
                            "location": str(row.get("Location", "")).strip(),
                            "start_time": str(row.get("Start Time",
                                                      "")).strip(),
                            "end_time": str(row.get("End Time", "")).strip(),
                            "status": str(row.get("Status",
                                                  "Default")).strip(),
                            "hp": hp
                        }
                        group_games.append(game_data)

                if group_games:
                    # Sort games by time for better display
                    group_games.sort(key=lambda x: x.get("start_time", ""))
                    summary_data[group] = group_games

            logger.info(
                f"Generated batch alliance summary for {alliance} with {len(summary_data)} groups using cached data"
            )
            return summary_data

        except Exception as e:
            logger.error(f"Error getting batch alliance summary: {e}")
            return {}

    def get_schedule_for_suballiance(self, alliance: str, group: str,
                                     day_key: str) -> List[Dict]:
        """Get detailed schedule for a suballiance using cached data."""
        try:
            # Determine which sheet to read from
            if day_key == "day2_treasure":
                sheet_name = self.treasure_hunt_mapping.get(alliance)
                if not sheet_name:
                    logger.error(
                        f"No treasure hunt sheet mapping found for alliance: {alliance}"
                    )
                    return []
            else:
                sheet_name = self.sheet_day_mapping.get(day_key)
                if not sheet_name:
                    logger.error(
                        f"No sheet mapping found for day_key: {day_key}")
                    return []

            logger.info(
                f"Getting schedule for Alliance='{alliance}', Group='{group}', Day='{day_key}' (Sheet: '{sheet_name}') using cached data"
            )

            # Use cached data instead of direct API call
            day_records = self._get_cached_day_sheet(sheet_name)
            results_records = self._get_cached_results()

            # Build HP lookup for this alliance/group
            hp_lookup = {}
            for row in results_records:
                if (str(row.get("Alliance", "")).strip() == alliance
                        and str(row.get("Group", "")).strip() == group):
                    game_name = str(row.get("Game", "")).strip()
                    hp_value = row.get("HP", 0)
                    try:
                        hp_lookup[game_name] = int(
                            hp_value) if hp_value != "" else 0
                    except (ValueError, TypeError):
                        hp_lookup[game_name] = 0

            results = []
            exact_matches = 0

            for row in day_records:
                row_alliance = str(row.get("Alliance", "")).strip()
                row_group = str(row.get("Group", "")).strip()

                if row_alliance != alliance or row_group != group:
                    continue

                exact_matches += 1
                game_name = str(row.get("Game", "")).strip()
                hp = hp_lookup.get(game_name, 0)

                result_entry = {
                    "game": game_name,
                    "location": str(row.get("Location", "")).strip(),
                    "start_time": str(row.get("Start Time", "")).strip(),
                    "end_time": str(row.get("End Time", "")).strip(),
                    "status": str(row.get("Status", "Default")).strip(),
                    "hp": hp
                }

                results.append(result_entry)

            logger.info(
                f"Found {exact_matches} exact matches, returning {len(results)} results using cached data"
            )
            return results

        except Exception as e:
            logger.error(f"Error getting schedule using cached data: {e}")
            return []

    def get_games_for_day_suballiance(self, alliance: str, group: str,
                                      day_key: str) -> List[Dict]:
        """Get all games for a specific suballiance on a specific day using cached Results sheet."""
        try:
            records = self._get_cached_results()

            # Map day_key to category
            category_mapping = {
                "day1_dry": "Dry Game",
                "day1_night": "Night Game",
                "day2_treasure": self._get_treasure_hunt_category(alliance),
                "day3_wet": "Wet Game"
            }

            target_category = category_mapping.get(day_key)
            if not target_category:
                logger.error(f"Unknown day_key: {day_key}")
                return []

            games = []
            for row in records:
                row_alliance = str(row.get("Alliance", "")).strip()
                row_group = str(row.get("Group", "")).strip()
                row_category = str(row.get("Category", "")).strip()

                if (row_alliance == alliance and row_group == group
                        and row_category == target_category):
                    # Ensure HP is always an integer
                    hp_value = row.get("HP", 0)
                    try:
                        if hp_value == "" or hp_value is None:
                            hp_value = 0
                        current_hp = int(hp_value)
                    except (ValueError, TypeError):
                        current_hp = 0

                    games.append({
                        'game': str(row.get("Game", "")).strip(),
                        'category': row_category,
                        'current_hp': current_hp,
                        'alliance': alliance,
                        'group': group
                    })

            logger.info(
                f"Found {len(games)} games for {alliance}/{group} on {day_key} using cached data"
            )
            return games

        except Exception as e:
            logger.error(
                f"Error getting games using cached data for {alliance}/{group} on {day_key}: {e}"
            )
            return []

    # ========================================
    # UTILITY AND HELPER METHODS
    # ========================================

    def _get_treasure_hunt_category(self, alliance: str) -> str:
        """Get the correct Treasure Hunt category based on alliance."""
        treasure_hunt_categories = {
            "Gaia": "Treasure Hunt (PM)",
            "Hydro": "Treasure Hunt (PM)",
            "Ignis": "Treasure Hunt (AM)",
            "Cirrus": "Treasure Hunt (AM)"
        }
        return treasure_hunt_categories.get(alliance, "Treasure Hunt (PM)")

    def get_all_suballiances_for_alliance(self, alliance: str) -> List[str]:
        """Get all suballiances for a given alliance using cached Results data."""
        logger.info(
            f"Getting suballiances for alliance: '{alliance}' using cached data"
        )

        try:
            # Get suballiances from cached Results sheet
            records = self._get_cached_results()

            suballiances = set()
            for row in records:
                row_alliance = str(row.get("Alliance", "")).strip()
                if row_alliance == alliance:
                    group = str(row.get("Group", "")).strip()
                    if group:
                        suballiances.add(group)

            result = sorted(list(suballiances), key=self._natural_sort_key)
            logger.info(
                f"Suballiances for '{alliance}' from cached Results: {result}")
            return result

        except Exception as e:
            logger.error(
                f"Error getting suballiances from cached Results: {e}")
            return []

    # ========================================
    # STATUS UPDATE OPERATIONS
    # ========================================

    def update_game_status(self, alliance: str, group: str, game: str,
                           new_status: str):
        """Update game status in the appropriate day sheets."""
        logger.info(
            f"Updating status for Alliance='{alliance}', Group='{group}', Game='{game}' to '{new_status}'"
        )

        sheets_to_check = list(self.sheet_day_mapping.values())

        # Add alliance-specific treasure hunt sheet if applicable
        if alliance in self.treasure_hunt_mapping:
            treasure_sheet = self.treasure_hunt_mapping[alliance]
            if treasure_sheet not in sheets_to_check:
                sheets_to_check.append(treasure_sheet)

        for sheet_name in sheets_to_check:
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
                records = worksheet.get_all_records()

                for idx, row in enumerate(records, start=2):  # Row 1 is header
                    row_alliance = str(row.get("Alliance", "")).strip()
                    row_group = str(row.get("Group", "")).strip()
                    row_game = str(row.get("Game", "")).strip()

                    if (row_alliance == alliance and row_group == group
                            and row_game == game):
                        worksheet.update_cell(
                            idx, 7, new_status)  # Assuming Status is column 7
                        logger.info(
                            f"Successfully updated status in sheet '{sheet_name}', row {idx}"
                        )

                        # Invalidate day sheet cache after update
                        if sheet_name in self._day_sheet_cache:
                            del self._day_sheet_cache[sheet_name]
                            del self._day_sheet_cache_timestamp[sheet_name]
                            logger.info(
                                f"Invalidated cache for sheet: {sheet_name}")
                        return

            except Exception as e:
                logger.error(
                    f"Error updating status in sheet '{sheet_name}': {e}")

    # ========================================
    # DEBUG AND TESTING METHODS
    # ========================================

    def test_connection(self) -> bool:
        """Test function to verify sheet connection and structure."""
        try:
            logger.info("=== TESTING GOOGLE SHEETS CONNECTION ===")

            worksheets = self.spreadsheet.worksheets()
            logger.info(
                f"Available worksheets: {[ws.title for ws in worksheets]}")

            # Test Results sheet
            logger.info("\n--- Testing Results Sheet ---")
            try:
                records = self._get_cached_results()
                logger.info("✅ Results sheet accessible via cache")
                logger.info(f"Total records: {len(records)}")

                if records:
                    logger.info(f"Sample record: {records[0]}")

            except Exception as e:
                logger.error(f"❌ Error with Results sheet: {e}")

            # Test day sheets
            for day_key, sheet_name in self.sheet_day_mapping.items():
                logger.info(f"\n--- Testing {day_key} -> {sheet_name} ---")
                try:
                    records = self._get_cached_day_sheet(sheet_name)
                    logger.info(f"✅ Sheet '{sheet_name}' accessible via cache")
                    logger.info(f"Total records: {len(records)}")

                    if records:
                        logger.info(f"Sample record: {records[0]}")

                except Exception as e:
                    logger.error(f"❌ Error with sheet '{sheet_name}': {e}")

            return True

        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        current_time = time.time()

        stats = {
            "results_cached": self._results_cache is not None,
            "results_age": None,
            "day_sheets_cached": len(self._day_sheet_cache),
            "day_sheet_names": list(self._day_sheet_cache.keys()),
            "cache_duration": self._cache_duration
        }

        if self._results_cache_timestamp:
            stats["results_age"] = current_time - self._results_cache_timestamp

        return stats

    def _natural_sort_key(self, text: str) -> tuple:
        """Generate a sorting key for natural number ordering."""
        import re
        parts = re.split(r'(\d+)', text)
        result = []
        for part in parts:
            if part.isdigit():
                result.append(int(part))
            else:
                result.append(part)
        return tuple(result)
