import logging
import re
from html import escape as html_escape
from typing import Dict, List, Optional, Any

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telebot.apihelper import ApiTelegramException

from utils import create_suballiance_keyboard
from sheets_manager import GoogleSheetsManager

logger = logging.getLogger(__name__)

# Constants
STATUS_LABELS = {
    "Default": "Player Ready ⚪",
    "In Progress": "Stage Engaged 🔴",
    "Next Station": "Next Up 🟡",
    "Completed": "Stage Cleared ✅",
}

ALLIANCE_NAMES = ["Gaia", "Hydro", "Ignis", "Cirrus"]

TREASURE_HUNT_NAMES = {
    "Gaia": "Day 2 Treasure Hunt (PM)",
    "Hydro": "Day 2 Treasure Hunt (AM)",
    "Ignis": "Day 2 Treasure Hunt (AM)",
    "Cirrus": "Day 2 Treasure Hunt (PM)"
}

DAY_NAMES = {
    "day1_dry": "Day 1 Dry Games",
    "day1_night": "Day 1 Night Games",
    "day2_treasure": "Day 2 Treasure Hunt",
    "day3_wet": "Day 3 Wet Games"
}

GAME_RESULT_OPTIONS = {
    "Win": {
        "points": 5,
        "emoji": "🏆",
        "color": "🟢"
    },
    "Draw": {
        "points": 3,
        "emoji": "🤝",
        "color": "🟡"
    },
    "Lost": {
        "points": 0,
        "emoji": "❌",
        "color": "🔴"
    }
}

STATUS_ICONS = {
    "Default": "⚪",
    "In Progress": "🔴",
    "Next Station": "🟡",
    "Completed": "✅",
}


class BotHandlers:
    """Main bot handlers class for managing Telegram bot interactions."""

    def __init__(self, bot, user_manager, firebase_manager):
        self.bot = bot
        self.user_manager = user_manager
        self.firebase = firebase_manager
        self.sheets = GoogleSheetsManager()

    # ========================================
    # KEYBOARD BUILDERS
    # ========================================

    def build_reply_menu(self, user_role: str = "") -> ReplyKeyboardMarkup:
        """Build the main reply keyboard menu based on user role."""
        kb = ReplyKeyboardMarkup(resize_keyboard=True)

        # Basic buttons that most users have
        basic_buttons = []

        # Determine what buttons to show based on role
        role_lower = user_role.lower()

        if role_lower in ['owner', 'exco']:
            # EXCO/Owner: Full access to everything
            basic_buttons.append(KeyboardButton("📍 Routing"))
            basic_buttons.append(KeyboardButton("🔧 Test Connection"))
            kb.row(*basic_buttons)
            kb.row(KeyboardButton("💚 HP Dashboard"), KeyboardButton("🎮 GM Interface"))
            kb.row(KeyboardButton("📊 Cache Stats"))

        elif 'gm' in role_lower or 'game master' in role_lower:
            # Game Masters: ONLY GM interface and test connection
            basic_buttons.append(KeyboardButton("🔧 Test Connection"))
            kb.row(*basic_buttons)
            kb.row(KeyboardButton("🎮 GM Interface"))

        elif user_role in ['Facilitator Head', 'Assistant Facilitator Head'] or 'facilitator' in role_lower:
            # Facilitators: Routing + their HP view
            basic_buttons.append(KeyboardButton("📍 Routing"))
            basic_buttons.append(KeyboardButton("🔧 Test Connection"))
            kb.row(*basic_buttons)

            # Different HP view based on head status
            if user_role in ['Facilitator Head', 'Assistant Facilitator Head']:
                kb.row(KeyboardButton("💚 HP Dashboard"))  # Alliance heads see full dashboard
            else:
                kb.row(KeyboardButton("💚 Suballiance HP"))  # Regular facilitators see only their group

        else:
            # Default case - minimal access
            basic_buttons.append(KeyboardButton("🔧 Test Connection"))
            kb.row(*basic_buttons)

        return kb

    def build_alliance_picker_kb(self,
                                 prefix: str = "routing_alliance"
                                 ) -> InlineKeyboardMarkup:
        """Build alliance selection keyboard."""
        kb = InlineKeyboardMarkup()
        for name in ALLIANCE_NAMES:
            kb.row(
                InlineKeyboardButton(f"🏛️ {name}",
                                     callback_data=f"{prefix}_{name}"))
        kb.row(InlineKeyboardButton("🔙 Back", callback_data="show_routing"))
        return kb

    def build_gm_alliance_picker_kb(self) -> InlineKeyboardMarkup:
        """Build GM alliance selection keyboard."""
        kb = InlineKeyboardMarkup()
        for name in ALLIANCE_NAMES:
            kb.row(
                InlineKeyboardButton(f"🏛️ {name}",
                                     callback_data=f"gm_alliance_{name}"))
        kb.row(
            InlineKeyboardButton("🔙 Back to GM Menu",
                                 callback_data="show_gm_interface"))
        return kb

    def build_day_selection_keyboard(
            self,
            alliance: str,
            group: str,
            prefix: str = "",
            show_back: bool = True) -> InlineKeyboardMarkup:
        """Build day selection keyboard with proper treasure hunt labels."""
        kb = InlineKeyboardMarkup()

        treasure_hunt_label = TREASURE_HUNT_NAMES.get(alliance,
                                                      "Day 2 Treasure Hunt")

        if prefix:
            kb.row(
                InlineKeyboardButton(
                    "🌅 Day 1 Dry Games",
                    callback_data=f"{prefix}_{alliance}_{group}_day1_dry"))
            kb.row(
                InlineKeyboardButton(
                    "🌙 Day 1 Night Games",
                    callback_data=f"{prefix}_{alliance}_{group}_day1_night"))
            kb.row(
                InlineKeyboardButton(
                    f"🗺️ {treasure_hunt_label}",
                    callback_data=f"{prefix}_{alliance}_{group}_day2_treasure")
            )
            kb.row(
                InlineKeyboardButton(
                    "💦 Day 3 Wet Games",
                    callback_data=f"{prefix}_{alliance}_{group}_day3_wet"))
        else:
            kb.row(
                InlineKeyboardButton(
                    "🌅 Day 1 Dry Games",
                    callback_data=f"day1_dry_{alliance}_{group}"))
            kb.row(
                InlineKeyboardButton(
                    "🌙 Day 1 Night Games",
                    callback_data=f"day1_night_{alliance}_{group}"))
            kb.row(
                InlineKeyboardButton(
                    f"🗺️ {treasure_hunt_label}",
                    callback_data=f"day2_treasure_{alliance}_{group}"))
            kb.row(
                InlineKeyboardButton(
                    "💦 Day 3 Wet Games",
                    callback_data=f"day3_wet_{alliance}_{group}"))

        if show_back:
            kb.row(InlineKeyboardButton("🔙 Back",
                                        callback_data="show_routing"))

        return kb

    def build_game_result_keyboard(self, alliance: str, group: str, game: str,
                                   day: str) -> InlineKeyboardMarkup:
        """Build game result selection keyboard with Win/Lost/Draw options."""
        kb = InlineKeyboardMarkup()

        # Create result buttons in a single row
        buttons = []
        for result, details in GAME_RESULT_OPTIONS.items():
            emoji = details["emoji"]
            color = details["color"]
            button_text = f"{color} {emoji} {result}"

            buttons.append(
                InlineKeyboardButton(
                    button_text,
                    callback_data=
                    f"gm_result_{alliance}_{group}_{game}_{result}"))

        # Add buttons in a single row for compact display
        kb.row(*buttons)

        kb.row(
            InlineKeyboardButton(
                "🔙 Back", callback_data=f"gm_day_{alliance}_{group}_{day}"))
        return kb

    # ========================================
    # UTILITY METHODS
    # ========================================

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

    def _parse_time(self, time_str):
        """Convert time string to minutes for sorting"""
        try:
            if ':' in str(time_str):
                hours, minutes = map(int, str(time_str).split(':'))
                return hours * 60 + minutes
            return 0  # Default for invalid times
        except:
            return 0

    def _parse_time_slot(self, time_slot):
        """Parse time slot for chronological sorting"""
        try:
            start_time = time_slot.split(" - ")[0]
            if ':' in start_time:
                hours, minutes = map(int, start_time.split(':'))
                return hours * 60 + minutes
            return 0
        except:
            return 9999  # Put invalid times at the end

    def safe_send_message(self,
                          chat_id: int,
                          text: str,
                          parse_mode: Optional[str] = None,
                          reply_markup: Optional[Any] = None):
        """Safely send message with fallback to plain text on formatting errors."""
        try:
            return self.bot.send_message(chat_id,
                                         text,
                                         parse_mode=parse_mode,
                                         reply_markup=reply_markup)
        except ApiTelegramException as e:
            if e.error_code == 400 and "can't parse entities" in str(
                    e).lower():
                logger.warning(
                    f"Formatting failed, sending as plain text: {e}")
                clean_text = re.sub(r"<[^>]+>|[*_`\[\]\(\)~>#\+=\|\{\}\.!]",
                                    "", text)
                return self.bot.send_message(chat_id,
                                             clean_text,
                                             reply_markup=reply_markup)
            raise

    def safe_edit_message(self,
                          chat_id: int,
                          message_id: int,
                          text: str,
                          parse_mode: Optional[str] = None,
                          reply_markup: Optional[Any] = None):
        """Try to edit message; fallback to sending new message if edit fails."""
        try:
            return self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except ApiTelegramException as e:
            desc = str(e).lower()
            if (e.error_code == 400
                    and ("can't parse entities" in desc
                         or "message can't be edited" in desc)):
                logger.warning(
                    f"Edit failed ({e.error_code}): {e}. Falling back to SEND."
                )
                return self.safe_send_message(chat_id,
                                              text,
                                              parse_mode=parse_mode,
                                              reply_markup=reply_markup)
            raise

    def safe_delete_message(self, chat_id: int, message_id: int):
        """Safely delete message, ignoring errors."""
        try:
            self.bot.delete_message(chat_id, message_id)
        except Exception:
            pass

    def get_treasure_hunt_display_name(self, alliance: str) -> str:
        """Get the display name for treasure hunt based on alliance."""
        return TREASURE_HUNT_NAMES.get(alliance, "Day 2 Treasure Hunt (PM)")

    def check_user_authorization(self,
                                 username: str) -> Optional[Dict[str, Any]]:
        """Check if user is authorized and return user data."""
        return self.firebase.check_user_authorization(username)

    def is_user_authorized_for_role(self, user_data: Dict[str, Any],
                                    required_roles: List[str]) -> bool:
        """Check if user has any of the required roles."""
        user_role = user_data.get("role", "").lower()
        return any(role.lower() in user_role or user_role == role.lower()
                   for role in required_roles)

    # ========================================
    # MAIN HANDLERS
    # ========================================

    def handle_start(self, message):
        """Handle /start command."""
        try:
            self._go_home(message.chat.id, message.from_user)
        except Exception as e:
            logger.error(f"Error in handle_start: {e}")
            self.bot.reply_to(message,
                              "❌ An error occurred. Please try again.")

    def _go_home(self, chat_id: int, user):
        """Send the welcome screen with appropriate menu."""
        first_name = getattr(user, "first_name", "") or ""
        username = getattr(user, "username", "") or ""
        user_data = self.check_user_authorization(username)

        if not user_data:
            self.safe_send_message(
                chat_id,
                "❌ Access Denied\n\nYou are not authorised. Please ask EXCO to grant you access."
            )
            return

        alliance = user_data.get("alliance", "EXCO Staff")
        role = user_data.get("role", "Member")

        welcome_text = (
            f"🎮 Welcome, {user_data.get('name', first_name)}!\n\n"
            f"You are authorized as: {role}\n"
            f"{'Alliance: ' + alliance if alliance != 'EXCO Staff' else 'EXCO Staff Member'}\n\n"
            f"Choose an option below:")

        self.safe_send_message(chat_id,
                               welcome_text,
                               reply_markup=self.build_reply_menu(role))

    # ========================================
    # MENU HANDLERS (Reply Keyboard)
    # ========================================

    def handle_menu_routing(self, message):
        """Handle '📍 Routing' button press."""
        self.open_routing_menu(message.chat.id, message.from_user)

    def handle_menu_test(self, message):
        """Handle '🔧 Test Connection' button press."""
        success = self.sheets.test_connection()
        message_text = "✅ Connection OK" if success else "❌ Connection failed"
        self.safe_send_message(message.chat.id, message_text)

    def handle_menu_hp_dashboard(self, message):
        """Handle '💚 HP Dashboard' button press."""
        self.handle_hp_dashboard(message)

    def handle_menu_my_hp(self, message):
        """Handle '💚 Suballiance HP' button press."""
        self.handle_my_hp(message)

    def handle_menu_gm_interface(self, message):
        """Handle '🎮 GM Interface' button press."""
        self.handle_gm_interface(message)

    def handle_menu_cache_stats(self, message):
        """Handle '📊 Cache Stats' button press."""
        self.handle_cache_stats(message)

    # ========================================
    # HP SYSTEM HANDLERS
    # ========================================

    def handle_hp_dashboard(self, message):
        """Display HP dashboard for EXCO/Owner users."""
        try:
            username = message.from_user.username or ""
            user_data = self.check_user_authorization(username)

            if not user_data:
                self.safe_send_message(message.chat.id, "❌ Access Denied")
                return

            if not self.is_user_authorized_for_role(user_data,
                                                    ['owner', 'exco']):
                self.safe_send_message(message.chat.id,
                                       "❌ Access Denied - EXCO/Owner only")
                return

            response = self._build_hp_dashboard_response(
                user_data.get("role", "").lower())
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Refresh",
                                     callback_data="refresh_hp_dashboard"))

            self.safe_send_message(message.chat.id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in handle_hp_dashboard: {e}")
            self.safe_send_message(message.chat.id,
                                   "❌ Error loading HP dashboard")

    def _build_hp_dashboard_response(self, role: str) -> str:
        """Build HP dashboard response based on user role."""
        all_hp = self.sheets.get_all_suballiance_hp()
        alliance_totals = self.sheets.get_alliance_totals()
        h = html_escape

        if role == 'owner':
            # Owner sees exact numbers
            response = "👑 <b>Owner HP Dashboard</b>\n\n"
            grand_total = sum(alliance_totals.values())
            response += f"🏆 <b>Grand Total: {grand_total}/400 HP</b>\n\n"

            for alliance in ALLIANCE_NAMES:
                total = alliance_totals.get(alliance, 0)
                heart = self.sheets.get_hp_color(total)
                response += f"🏛️ <b>{alliance}</b>: {total}/100 HP {heart}\n"

                if alliance in all_hp:
                    # SORT GROUPS USING NATURAL SORTING
                    sorted_groups = sorted(
                        all_hp[alliance].items(),
                        key=lambda x: self._natural_sort_key(x[0]))
                    for group, hp in sorted_groups:
                        group_heart = self.sheets.get_hp_color(hp)
                        response += f"  └ {group}: {hp}/100 HP {group_heart}\n"
                response += "\n"
        else:
            # EXCO sees only heart colors
            response = "🏛️ <b>EXCO HP Dashboard</b>\n\n"

            for alliance in ALLIANCE_NAMES:
                total = alliance_totals.get(alliance, 0)
                heart = self.sheets.get_hp_color(total)
                response += f"🏛️ <b>{alliance}</b> {heart}\n"

                if alliance in all_hp:
                    # SORT GROUPS USING NATURAL SORTING
                    sorted_groups = sorted(
                        all_hp[alliance].items(),
                        key=lambda x: self._natural_sort_key(x[0]))
                    for group, hp in sorted_groups:
                        group_heart = self.sheets.get_hp_color(hp)
                        response += f"  └ {group} {group_heart}\n"
                response += "\n"

        return response

    def handle_my_hp(self, message):
        """Handle HP view for facilitators and heads."""
        try:
            username = message.from_user.username or ""
            user_data = self.check_user_authorization(username)

            if not user_data:
                self.safe_send_message(message.chat.id, "❌ Access Denied")
                return

            alliance = user_data.get("alliance")
            group = user_data.get("group")  # This can be None
            role = user_data.get("role", "")

            if not alliance:
                self.safe_send_message(message.chat.id,
                                       "❌ No alliance assigned")
                return

            is_alliance_head = (
                role in ["Facilitator Head", "Assistant Facilitator Head"]
                or group == "Heads")

            # Handle the case where group might be None for non-heads
            if not is_alliance_head and not group:
                self.safe_send_message(message.chat.id, "❌ No group assigned")
                return

            response = self._build_my_hp_response(alliance, group, role,
                                                  is_alliance_head)
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Refresh",
                                     callback_data="refresh_my_hp"))

            self.safe_send_message(message.chat.id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in handle_my_hp: {e}")
            self.safe_send_message(message.chat.id,
                                   "❌ Error loading HP status")

    def _build_my_hp_response(self, alliance: str, group: Optional[str],
                              role: str, is_alliance_head: bool) -> str:
        """Build HP response for individual users."""
        h = html_escape

        if is_alliance_head:
            # Alliance Heads see heart-only view for their alliance
            all_hp = self.sheets.get_all_suballiance_hp()
            alliance_total = self.sheets.get_alliance_totals().get(alliance, 0)
            alliance_heart = self.sheets.get_hp_color(alliance_total)

            response = f"👑 <b>{alliance} Alliance HP Dashboard</b>\n\n"
            response += f"🏆 <b>Alliance Total: {alliance_heart}</b>\n\n"

            if alliance in all_hp:
                # SORT GROUPS USING NATURAL SORTING
                sorted_groups = sorted(
                    all_hp[alliance].items(),
                    key=lambda x: self._natural_sort_key(x[0]))
                for group_name, hp in sorted_groups:
                    group_heart = self.sheets.get_hp_color(hp)
                    response += f"👥 <b>{group_name}</b> {group_heart}\n"

            response += f"\n<i>You can see all groups in {alliance} alliance as an Alliance Head.</i>"
            return response
        else:
            # Regular facilitators see only their group
            if not group:
                return "❌ No group assigned"

            hp = self.sheets.get_suballiance_hp(alliance, group)
            heart = self.sheets.get_hp_color(hp)

            response = f"💚 <b>HP Status for {group} ({alliance})</b>\n\n"
            response += f"Current HP: {heart}\n\n"
            response += "<i>Your current performance level is represented by the heart color above.</i>"
            return response

    # ========================================
    # GM INTERFACE HANDLERS
    # ========================================

    def handle_gm_interface(self, message):
        """GM interface - simple scoring without notifications."""
        try:
            username = message.from_user.username or ""
            user_data = self.check_user_authorization(username)

            if not user_data:
                self.safe_send_message(message.chat.id, "❌ Access Denied")
                return

            if not self._is_gm_authorized(user_data):
                self.safe_send_message(message.chat.id,
                                       "❌ Access Denied - GM/EXCO only")
                return

            response = "🎮 <b>Game Master Interface</b>\n\n"
            response += "Select an alliance to record game results:"

            keyboard = self.build_gm_alliance_picker_kb()

            self.safe_send_message(message.chat.id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in handle_gm_interface: {e}")
            self.safe_send_message(message.chat.id,
                                   "❌ Error loading GM interface")

    def _is_gm_authorized(self, user_data: Dict[str, Any]) -> bool:
        """Check if user is authorized for GM functions."""
        role = user_data.get("role", "").lower()
        return (role in ['owner', 'exco'] or 'gm' in role
                or 'game master' in role)

    # ========================================
    # ROUTING HANDLERS
    # ========================================

    def open_routing_menu(self, chat_id: int, from_user):
        """Open the routing menu based on user permissions."""
        user_data = self.check_user_authorization(from_user.username or "")
        if not user_data:
            self.safe_send_message(chat_id, "❌ Access Denied")
            return

        role = user_data.get("role", "")
        alliance = user_data.get("alliance")
        group = user_data.get("group")

        # Check if user is EXCO/Owner (should have full access)
        is_exco_or_owner = (role.lower() in ['owner', 'exco'] or 
                           alliance == "EXCO Staff" or
                           alliance == "Game Masters")

        # Check if user is alliance head
        is_head = (role in ["Facilitator Head", "Assistant Facilitator Head"] or 
                  group == "Heads")

        if is_exco_or_owner:
            # EXCO/Owner/GM see alliance selection for full system access
            keyboard = self.build_alliance_picker_kb(prefix="routing_alliance")
            self.safe_send_message(chat_id, "📍 Select Alliance to Manage", 
                                 reply_markup=keyboard)
        elif alliance and is_head:
            # Alliance heads see their alliance overview
            suballiances = self.sheets.get_all_suballiances_for_alliance(alliance)
            keyboard = create_suballiance_keyboard(
                suballiances=suballiances, alliance=alliance, prefix="routing_sub",
                include_all=True, show_back=False,
            )
            self.safe_send_message(
                chat_id, f"📍 {alliance} Alliance - Select Suballiance to View", 
                reply_markup=keyboard
            )
        elif alliance and group:
            # Regular users see their group schedule
            keyboard = self.build_day_selection_keyboard(alliance, group, show_back=True)
            self.safe_send_message(
                chat_id, f"🗺️ Routing for {group} ({alliance})\n\nChoose a day:", 
                reply_markup=keyboard
            )
        else:
            # Fallback for users without proper alliance/group setup
            self.safe_send_message(
                chat_id, 
                "❌ Routing Access Issue\n\n"
                f"Role: {role}\n"
                f"Alliance: {alliance}\n"
                f"Group: {group}\n\n"
                "Please contact EXCO to verify your permissions are set up correctly."
            )

    # ========================================
    # CACHE AND MONITORING
    # ========================================

    def handle_cache_stats(self, message):
        """Handle cache statistics command for debugging."""
        try:
            username = message.from_user.username or ""
            user_data = self.check_user_authorization(username)

            if not user_data:
                self.safe_send_message(message.chat.id, "❌ Access Denied")
                return

            # Only allow EXCO/Owner to see cache stats
            if not self.is_user_authorized_for_role(user_data,
                                                    ['owner', 'exco']):
                self.safe_send_message(message.chat.id,
                                       "❌ Access Denied - EXCO/Owner only")
                return

            stats = self.sheets.get_cache_stats()

            response = "📊 <b>Cache Statistics</b>\n\n"
            response += f"🗂️ Results Sheet Cached: {'✅' if stats['results_cached'] else '❌'}\n"

            if stats['results_age']:
                response += f"📅 Results Age: {stats['results_age']:.1f} seconds\n"

            response += f"📋 Day Sheets Cached: {stats['day_sheets_cached']}\n"
            response += f"⏱️ Cache Duration: {stats['cache_duration']} seconds\n\n"

            if stats['day_sheet_names']:
                response += f"📑 Cached Sheets:\n"
                for sheet in stats['day_sheet_names']:
                    response += f"  • {sheet}\n"

            response += f"\n<i>Cache helps reduce API calls and improves performance.</i>"

            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🔄 Refresh Cache",
                                     callback_data="refresh_cache"))
            keyboard.row(
                InlineKeyboardButton("🧹 Clear Cache",
                                     callback_data="clear_cache"))

            self.safe_send_message(message.chat.id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in handle_cache_stats: {e}")
            self.safe_send_message(message.chat.id,
                                   "❌ Error getting cache statistics")

    def warm_cache_on_startup(self):
        """Pre-warm cache with frequently accessed data on bot startup."""
        try:
            logger.info("Warming up cache on startup...")

            # Pre-load Results sheet
            self.sheets._get_cached_results()

            # Pre-load day sheets
            for day_key, sheet_name in self.sheets.sheet_day_mapping.items():
                self.sheets._get_cached_day_sheet(sheet_name)

            # Pre-load treasure hunt sheets
            for alliance, sheet_name in self.sheets.treasure_hunt_mapping.items(
            ):
                self.sheets._get_cached_day_sheet(sheet_name)

            logger.info("Cache warming completed successfully")

        except Exception as e:
            logger.error(f"Error warming cache: {e}")

    def track_api_usage(self):
        """Track and log API usage for monitoring."""
        try:
            cache_stats = self.sheets.get_cache_stats()

            logger.info("=== API USAGE TRACKING ===")
            logger.info(f"Results cache hits: {cache_stats['results_cached']}")
            logger.info(
                f"Day sheet cache hits: {cache_stats['day_sheets_cached']}")

            if cache_stats['results_age']:
                logger.info(
                    f"Results cache age: {cache_stats['results_age']:.1f}s")

            # Calculate estimated API calls saved
            estimated_calls_saved = 0
            if cache_stats['results_cached']:
                estimated_calls_saved += 50  # Rough estimate for Results sheet reuse

            estimated_calls_saved += cache_stats['day_sheets_cached'] * 10

            logger.info(
                f"Estimated API calls saved by caching: {estimated_calls_saved}"
            )

        except Exception as e:
            logger.error(f"Error tracking API usage: {e}")

    # ========================================
    # CALLBACK QUERY HANDLER
    # ========================================

    def handle_callback_query(self, call):
        """Main callback query handler - routes to specific handlers."""
        try:
            username = call.from_user.username or ""
            user_data = self.check_user_authorization(username)

            if not user_data:
                self._handle_unauthorized_callback(call)
                return

            data = call.data
            logger.info(
                f"Callback data received: {data} from authorized user: {username}"
            )

            # Route to appropriate handler
            if self._handle_gm_callbacks(call, data, user_data):
                return
            elif self._handle_hp_callbacks(call, data, user_data):
                return
            elif self._handle_routing_callbacks(call, data, user_data):
                return
            else:
                logger.warning(f"Unknown callback data: {data}")
                try:
                    self.bot.answer_callback_query(call.id, "❓ Unknown option")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error in handle_callback_query: {e}")
            try:
                self.bot.answer_callback_query(call.id, "❌ An error occurred.")
            except Exception:
                pass

    def _handle_unauthorized_callback(self, call):
        """Handle callbacks from unauthorized users."""
        try:
            self.bot.answer_callback_query(call.id,
                                           "❌ Access Denied",
                                           show_alert=True)
        except Exception:
            pass

        self.safe_edit_message(
            call.message.chat.id, call.message.message_id,
            "❌ Access Denied\n\nYou are not authorised or your access has been revoked. "
            "Please ask EXCO to grant you access.")

    def _handle_gm_callbacks(self, call, data: str,
                             user_data: Dict[str, Any]) -> bool:
        """Handle GM-related callbacks. Returns True if handled."""
        if data == "show_gm_interface":
            self._show_gm_interface(call)
            return True
        elif data.startswith("gm_alliance_"):
            alliance = data.replace("gm_alliance_", "")
            self._handle_gm_alliance_selection(call, alliance)
            return True
        elif data.startswith("gm_suballiance_"):
            parts = data.split("_", 3)
            alliance, group = parts[2], parts[3]
            self._handle_gm_suballiance_selection(call, alliance, group)
            return True
        elif data.startswith("gm_day_"):
            parts = data.split("_", 5)
            alliance, group = parts[2], parts[3]
            day = f"{parts[4]}_{parts[5]}"
            self._handle_gm_day_selection(call, alliance, group, day)
            return True
        elif data.startswith("gm_game_"):
            parts = data.split("_", 6)
            alliance, group = parts[2], parts[3]
            day = f"{parts[4]}_{parts[5]}"
            game = parts[6]
            self._handle_gm_game_selection(call, alliance, group, day, game)
            return True
        elif data.startswith("gm_result_"):
            parts = data.split("_", 5)
            alliance, group, game = parts[2], parts[3], parts[4]
            result = parts[5]
            self._handle_gm_result_award(call, alliance, group, game, result)
            return True
        return False

    def _handle_hp_callbacks(self, call, data: str,
                             user_data: Dict[str, Any]) -> bool:
        """Handle HP-related callbacks. Returns True if handled."""
        if data == "refresh_hp_dashboard":
            self._refresh_hp_dashboard(call, user_data)
            return True
        elif data == "refresh_my_hp":
            self._refresh_my_hp(call, user_data)
            return True
        return False

    def _handle_routing_callbacks(self, call, data: str,
                                  user_data: Dict[str, Any]) -> bool:
        """Handle routing-related callbacks. Returns True if handled."""
        if data == "back_main":
            self._go_home(call.message.chat.id, call.from_user)
            self.safe_delete_message(call.message.chat.id,
                                     call.message.message_id)
            return True
        elif data == "test_sheets":
            self._test_sheets_connection(call)
            return True
        elif data == "refresh_cache":
            self._handle_cache_refresh_callback(call)
            return True
        elif data == "clear_cache":
            self._handle_cache_clear_callback(call)
            return True
        elif data == "show_routing":
            self.open_routing_menu(call.message.chat.id, call.from_user)
            return True
        elif data.startswith("routing_alliance_"):
            alliance = data.replace("routing_alliance_", "")
            self._handle_routing_alliance_selection(call, alliance)
            return True
        elif data.startswith("routing_sub_"):
            parts = data.split("_", 3)
            alliance, suballiance = parts[2], parts[3]
            self._handle_routing_suballiance_selection(call, alliance,
                                                       suballiance)
            return True
        elif data.startswith("summary_"):
            parts = data.split("_", 3)
            day_key = f"{parts[1]}_{parts[2]}"
            alliance = parts[3]
            self._handle_alliance_summary_callback(call, day_key, alliance)
            return True
        elif any(
                data.startswith(day) for day in
            ["day1_dry", "day1_night", "day2_treasure", "day3_wet"]):
            self._handle_day_callback(call, data)
            return True
        elif data.startswith("status|"):
            self._handle_status_update(call, data)
            return True
        elif data.startswith("game|"):
            self._handle_game_selection(call, data)
            return True
        return False

    # ========================================
    # GM CALLBACK IMPLEMENTATIONS
    # ========================================

    def _show_gm_interface(self, call):
        """Show the main GM interface."""
        try:
            self.bot.answer_callback_query(call.id)
        except Exception:
            pass

        response = "🎮 <b>Game Master Interface</b>\n\nSelect an alliance to record game results:"
        keyboard = self.build_gm_alliance_picker_kb()

        self.safe_edit_message(call.message.chat.id,
                               call.message.message_id,
                               response,
                               parse_mode="HTML",
                               reply_markup=keyboard)

    def _handle_gm_alliance_selection(self, call, alliance: str):
        """Handle GM alliance selection."""
        try:
            suballiances = self.sheets.get_all_suballiances_for_alliance(
                alliance)

            if not suballiances:
                self.bot.answer_callback_query(
                    call.id, f"❌ No suballiances found for {alliance}")
                return

            h = html_escape
            response = f"🎮 <b>GM Interface - {h(alliance)} Alliance</b>\n\nSelect a suballiance to record game results:"

            keyboard = InlineKeyboardMarkup()
            for group in suballiances:
                keyboard.add(
                    InlineKeyboardButton(
                        f"👥 {group}",
                        callback_data=f"gm_suballiance_{alliance}_{group}"))

            keyboard.row(
                InlineKeyboardButton("🔙 Back to GM Menu",
                                     callback_data="show_gm_interface"))

            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in _handle_gm_alliance_selection: {e}")
            self.bot.answer_callback_query(call.id,
                                           "❌ Error loading suballiances")

    def _handle_gm_suballiance_selection(self, call, alliance: str,
                                         group: str):
        """Handle GM suballiance selection."""
        try:
            current_hp = self.sheets.get_suballiance_hp(alliance, group)
            heart = self.sheets.get_hp_color(current_hp)

            h = html_escape
            response = f"🎯 <b>Scoreboard for {h(group)} ({h(alliance)})</b>\n\n"
            response += f"Current HP: {heart}\n\nChoose a day to record game results:"

            keyboard = self.build_day_selection_keyboard(alliance,
                                                         group,
                                                         prefix="gm_day",
                                                         show_back=False)
            keyboard.row(
                InlineKeyboardButton("🔙 Back",
                                     callback_data=f"gm_alliance_{alliance}"))

            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in _handle_gm_suballiance_selection: {e}")
            self.bot.answer_callback_query(call.id,
                                           "❌ Error loading scoreboard")

    def _handle_gm_day_selection(self, call, alliance: str, group: str,
                                 day: str):
        """Handle GM day selection - show games with any existing results."""
        try:
            games = self.sheets.get_games_for_day_suballiance(
                alliance, group, day)

            if not games:
                self.bot.answer_callback_query(call.id,
                                               f"❌ No games found for {day}")
                return

            # Updated day names with alliance-specific treasure hunt
            day_names = {
                "day1_dry": "Day 1 Dry Games",
                "day1_night": "Day 1 Night Games",
                "day2_treasure": self.get_treasure_hunt_display_name(alliance),
                "day3_wet": "Day 3 Wet Games"
            }

            h = html_escape
            response = f"🎯 <b>{h(group)} ({h(alliance)}) - {day_names.get(day, day)}</b>\n\n"
            response += "Select a game to record the result:\n\n"

            keyboard = InlineKeyboardMarkup()

            for game_info in games:
                game_name = game_info['game']
                current_score = game_info['current_hp']

                # Convert current_score to int for comparison
                try:
                    current_score = int(
                        current_score) if current_score not in [None, "", 0
                                                                ] else 0
                except (ValueError, TypeError):
                    current_score = 0

                # Show result if any points awarded
                if current_score > 0:
                    # Determine what result this score represents
                    result_display = ""
                    for result, details in GAME_RESULT_OPTIONS.items():
                        if details["points"] == current_score:
                            result_display = f" {details['emoji']} {result}"
                            break

                    if not result_display:
                        result_display = f" ({current_score}pts)"
                else:
                    result_display = ""

                button_text = f"🎮 {game_name}{result_display}"

                # Truncate if too long
                if len(button_text) > 35:
                    button_text = f"🎮 {game_name[:25]}...{result_display}"

                keyboard.add(
                    InlineKeyboardButton(
                        button_text,
                        callback_data=
                        f"gm_game_{alliance}_{group}_{day}_{game_name}"))

            keyboard.row(
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"gm_suballiance_{alliance}_{group}"))

            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in _handle_gm_day_selection: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error loading games")

    def _handle_gm_game_selection(self, call, alliance: str, group: str,
                                  day: str, game: str):
        """Handle GM game selection - show Win/Lost/Draw options."""
        try:
            current_hp = self.sheets.get_suballiance_hp(alliance, group)
            heart = self.sheets.get_hp_color(current_hp)

            h = html_escape
            response = f"🎯 <b>Record Game Result</b>\n\n"
            response += f"Game: {h(game)}\n"
            response += f"Suballiance: {h(group)} ({h(alliance)})\n"
            response += f"Current HP: {heart}\n\n"
            response += "Select the game result:"

            keyboard = self.build_game_result_keyboard(alliance, group, game,
                                                       day)

            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   response,
                                   parse_mode="HTML",
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in _handle_gm_game_selection: {e}")
            self.bot.answer_callback_query(
                call.id, "❌ Error loading game result options")

    def _handle_gm_result_award(self, call, alliance: str, group: str,
                                game: str, result: str):
        """Award points based on game result and update display."""
        try:
            # Get points for the result
            if result not in GAME_RESULT_OPTIONS:
                self.bot.answer_callback_query(call.id,
                                               "❌ Invalid result",
                                               show_alert=True)
                return

            points = GAME_RESULT_OPTIONS[result]["points"]
            result_emoji = GAME_RESULT_OPTIONS[result]["emoji"]

            # Award the points
            success = self.sheets.award_points(alliance, group, game, points)

            if success:
                new_hp = self.sheets.get_suballiance_hp(alliance, group)
                heart = self.sheets.get_hp_color(new_hp)

                self.bot.answer_callback_query(
                    call.id,
                    f"✅ {result} recorded! {points} points awarded to {group}",
                    show_alert=True)

                # Update message to show completion
                h = html_escape
                response = f"✅ <b>Game Result Recorded!</b>\n\n"
                response += f"Game: {h(game)}\n"
                response += f"Suballiance: {h(group)} ({h(alliance)})\n"
                response += f"Result: {result_emoji} <b>{result}</b> ({points} points)\n"
                response += f"New HP Status: {heart}\n\n"
                response += f"<i>Result has been updated in the system.</i>"

                keyboard = InlineKeyboardMarkup()
                keyboard.row(
                    InlineKeyboardButton(
                        "🎯 Record More Results",
                        callback_data=f"gm_suballiance_{alliance}_{group}"))
                keyboard.row(
                    InlineKeyboardButton("🏠 Back to GM Menu",
                                         callback_data="show_gm_interface"))

                self.safe_edit_message(call.message.chat.id,
                                       call.message.message_id,
                                       response,
                                       parse_mode="HTML",
                                       reply_markup=keyboard)

                logger.info(
                    f"GM recorded {result} ({points} points): {alliance}/{group} for {game}"
                )

            else:
                self.bot.answer_callback_query(call.id,
                                               "❌ Failed to record result",
                                               show_alert=True)

        except Exception as e:
            logger.error(f"Error in _handle_gm_result_award: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error recording result")

    # ========================================
    # HP CALLBACK IMPLEMENTATIONS
    # ========================================

    def _refresh_hp_dashboard(self, call, user_data: Dict[str, Any]):
        """Refresh the HP dashboard."""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Refreshing...")
        except Exception:
            pass

        if not self.is_user_authorized_for_role(user_data, ['owner', 'exco']):
            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   "❌ Access Denied - EXCO/Owner only")
            return

        response = self._build_hp_dashboard_response(
            user_data.get("role", "").lower())
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🔄 Refresh",
                                 callback_data="refresh_hp_dashboard"))

        self.safe_edit_message(call.message.chat.id,
                               call.message.message_id,
                               response,
                               parse_mode="HTML",
                               reply_markup=keyboard)

    def _refresh_my_hp(self, call, user_data: Dict[str, Any]):
        """Refresh the user's HP view."""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Refreshing...")
        except Exception:
            pass

        alliance = user_data.get("alliance")
        group = user_data.get("group")  # This can be None
        role = user_data.get("role", "")

        if not alliance:
            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   "❌ No alliance assigned")
            return

        is_alliance_head = (
            role in ["Facilitator Head", "Assistant Facilitator Head"]
            or group == "Heads")

        # Handle the case where group might be None for non-heads
        if not is_alliance_head and not group:
            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   "❌ No group assigned")
            return

        response = self._build_my_hp_response(alliance, group, role,
                                              is_alliance_head)
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_my_hp"))

        self.safe_edit_message(call.message.chat.id,
                               call.message.message_id,
                               response,
                               parse_mode="HTML",
                               reply_markup=keyboard)

    # ========================================
    # ROUTING CALLBACK IMPLEMENTATIONS
    # ========================================

    def _test_sheets_connection(self, call):
        """Test sheets connection."""
        try:
            self.bot.answer_callback_query(call.id, "Testing connection...")
        except Exception:
            pass

        success = self.sheets.test_connection()
        result_text = ("✅ Connection test completed. Check logs for details."
                       if success else "❌ Connection test failed. Check logs.")
        self.safe_send_message(call.message.chat.id, result_text)

    def _handle_cache_refresh_callback(self, call):
        """Handle cache refresh requests."""
        try:
            self.bot.answer_callback_query(call.id, "🔄 Refreshing cache...")

            # Invalidate all caches to force fresh data
            self.sheets._invalidate_cache()

            # Pre-warm the cache by fetching fresh data
            self.sheets._get_cached_results()

            self.bot.answer_callback_query(call.id,
                                           "✅ Cache refreshed!",
                                           show_alert=True)

        except Exception as e:
            logger.error(f"Error refreshing cache: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error refreshing cache")

    def _handle_cache_clear_callback(self, call):
        """Handle cache clear requests."""
        try:
            self.bot.answer_callback_query(call.id, "🧹 Clearing cache...")

            # Clear all caches
            self.sheets._invalidate_cache()

            self.bot.answer_callback_query(call.id,
                                           "✅ Cache cleared!",
                                           show_alert=True)

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            self.bot.answer_callback_query(call.id, "❌ Error clearing cache")

    def _handle_routing_alliance_selection(self, call, alliance: str):
        """Handle routing alliance selection."""
        suballiances = self.sheets.get_all_suballiances_for_alliance(alliance)

        keyboard = create_suballiance_keyboard(
            suballiances=suballiances,
            alliance=alliance,
            prefix="routing_sub",
            include_all=True,
            show_back=True,
        )

        self.safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            f"📍 {alliance} Alliance - Select Suballiance to View",
            reply_markup=keyboard,
        )

    def _handle_routing_suballiance_selection(self, call, alliance: str,
                                              suballiance: str):
        """Handle routing suballiance selection."""
        if suballiance == "ALL":
            # Show summary for all groups
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton(
                    "🌅 Day 1 Dry Games Summary",
                    callback_data=f"summary_day1_dry_{alliance}"))
            keyboard.row(
                InlineKeyboardButton(
                    "🌙 Day 1 Night Games Summary",
                    callback_data=f"summary_day1_night_{alliance}"))
            keyboard.row(
                InlineKeyboardButton(
                    "🗺️ Day 2 Treasure Hunt Summary",
                    callback_data=f"summary_day2_treasure_{alliance}"))
            keyboard.row(
                InlineKeyboardButton(
                    "💦 Day 3 Wet Games Summary",
                    callback_data=f"summary_day3_wet_{alliance}"))
            keyboard.row(
                InlineKeyboardButton("🔙 Back", callback_data="show_routing"))

            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                f"📊 {alliance} Alliance Summary\n\nChoose a day to view all groups:",
                reply_markup=keyboard,
            )
        else:
            # Show individual group schedule
            keyboard = self.build_day_selection_keyboard(alliance,
                                                         suballiance,
                                                         show_back=True)

            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                f"🗺️ Routing for {suballiance} ({alliance})\n\nChoose a day:",
                reply_markup=keyboard,
            )

    def _handle_day_callback(self, call, data: str):
        """Handle day selection callback."""
        parts = data.split("_")
        day_key = f"{parts[0]}_{parts[1]}"
        alliance = parts[2]
        suballiance = parts[3]
        self._handle_game_details_callback(call, day_key, alliance,
                                           suballiance)

    def _handle_status_update(self, call, data: str):
        """Handle status update callback."""
        _, alliance, suballiance, game, new_status, day_key = data.split(
            "|", 5)
        self.sheets.update_game_status(alliance, suballiance, game, new_status)

        try:
            self.bot.answer_callback_query(
                call.id, f"✅ Status updated to '{new_status}'")
        except Exception:
            pass

        self._handle_game_details_callback(call, day_key, alliance,
                                           suballiance)

    def _handle_game_selection(self, call, data: str):
        """Handle game selection callback."""
        _, alliance, suballiance, game, day_key = data.split("|", 4)
        self._handle_game_status_selection(call, alliance, suballiance, game,
                                           day_key)

    def _handle_alliance_summary_callback(self, call, day_key: str,
                                          alliance: str):
        """Handle alliance summary callback using optimized batch processing."""
        try:
            logger.info(
                f"Generating alliance summary for {alliance} on {day_key} using batch processing"
            )

            # Use the new batch processing method instead of individual calls
            summary_data = self.sheets.get_alliance_summary_batch(
                alliance, day_key)

            if not summary_data:
                self.safe_edit_message(
                    call.message.chat.id, call.message.message_id,
                    f"❌ No data found for {alliance} alliance on {day_key}.")
                return

            # Build day label
            day_label = DAY_NAMES.get(day_key, "Unknown Day")
            if day_key == "day2_treasure":
                day_label = self.get_treasure_hunt_display_name(alliance)

            h = html_escape
            response = f"📊 {h(alliance)} Alliance - {h(day_label)} Summary\n\n"

            # Group games by time slot for better organization
            time_slot_games = {}

            for group, games in summary_data.items():
                for game in games:
                    start_time = game.get("start_time", "TBD")
                    end_time = game.get("end_time", "TBD")
                    time_slot = f"{start_time} - {end_time}"

                    if time_slot not in time_slot_games:
                        time_slot_games[time_slot] = []

                    time_slot_games[time_slot].append({
                        "group":
                        group,
                        "game":
                        game["game"],
                        "location":
                        game["location"],
                        "status":
                        game["status"],
                        "hp":
                        game["hp"]
                    })

            # Sort time slots chronologically
            sorted_times = sorted(time_slot_games.keys(), key=self._parse_time_slot)
            for time_slot in sorted_times:
                games = time_slot_games[time_slot]
                # Sort groups by number using natural sorting
                games.sort(key=lambda g: self._natural_sort_key(g["group"]))

                response += f"<b>{h(time_slot)}</b>\n"
                for game in games:
                    status_icon = STATUS_ICONS.get(game["status"], "⚪")
                    hp_display = (f" ({game['hp']}pts)"
                                  if game["status"] == "Completed"
                                  and game["hp"] > 0 else "")

                    response += (
                        f"<b>{h(game['group'])}</b> - {h(game['game'])} @ "
                        f"{h(game['location'])}{hp_display} {status_icon}\n")
                response += "\n"

            # Add cache info for debugging
            cache_stats = self.sheets.get_cache_stats()
            response += f"<i>📊 Loaded using cached data (Results: {cache_stats['results_cached']}, Day sheets: {cache_stats['day_sheets_cached']})</i>"

            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data=f"summary_{day_key}_{alliance}"))
            keyboard.row(
                InlineKeyboardButton("🔙 Back", callback_data="show_routing"))

            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                response,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            logger.info(
                f"Successfully generated alliance summary for {alliance} using batch processing"
            )

        except Exception as e:
            logger.error(f"Error in batch alliance summary callback: {e}")
            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                f"❌ Error loading alliance summary.\n\nError: {str(e)}\n"
                f"Alliance: {alliance}\nDay: {day_key}",
            )

    def _handle_game_details_callback(self, call, day_key: str, alliance: str,
                                      suballiance: str):
        """Show detailed schedule for a single suballiance."""
        try:
            routing_data = self.sheets.get_schedule_for_suballiance(
                alliance, suballiance, day_key)
            if not routing_data:
                debug_text = (
                    "❌ No schedule found for this selection.\n\n"
                    f"DEBUG INFO:\n- Alliance: '{alliance}'\n- Suballiance: '{suballiance}'\n"
                    f"- Day: '{day_key}'\n- Sheet: '{self.sheets.sheet_day_mapping.get(day_key, 'UNKNOWN')}'\n\n"
                    "Please check:\n1. Suballiance exists in the selected day's sheet\n"
                    "2. Alliance/Group names match exactly\n3. Use Test Connection to verify access."
                )
                self.safe_edit_message(call.message.chat.id,
                                       call.message.message_id, debug_text)
                return

            # Build day label
            day_label = DAY_NAMES.get(day_key, "Unknown Day")
            if day_key == "day2_treasure":
                day_label = self.get_treasure_hunt_display_name(alliance)

            # Sort routing_data by start_time to ensure chronological order
            routing_data.sort(key=lambda x: self._parse_time(x.get("start_time", "00:00")))

            # Build response
            h = html_escape
            response = f"🗓️ {h(day_label)} Schedule for {h(suballiance)}\n\n"

            for entry in routing_data:
                status_text = STATUS_LABELS.get(entry["status"],
                                                entry["status"])
                game = h(str(entry["game"]))
                location = h(str(entry["location"]))
                start_time = h(str(entry["start_time"]))
                end_time = h(str(entry["end_time"]))
                hp = entry.get("hp", 0)

                # Show HP points if game is completed
                hp_display = f" ({hp}pts)" if entry[
                    "status"] == "Completed" and hp > 0 else ""

                response += (f"<b>{start_time} - {end_time}</b>\n"
                             f"📱 {game} @ {location}{hp_display}\n"
                             f"{h(status_text)}\n\n")

            # Build keyboard with game buttons (keep same order as sorted display)
            keyboard = InlineKeyboardMarkup()
            for entry in routing_data:
                game_name = str(entry["game"])
                current_status = entry["status"]
                status_icon = STATUS_ICONS.get(current_status, "⚪")

                display_name = (game_name[:25] +
                                "..." if len(game_name) > 25 else game_name)

                keyboard.add(
                    InlineKeyboardButton(
                        f"{status_icon} {display_name}",
                        callback_data=
                        f"game|{alliance}|{suballiance}|{game_name}|{day_key}",
                    ))

            keyboard.row(
                InlineKeyboardButton("🔙 Back", callback_data="show_routing"))

            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                response,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception as e:
            logger.error(f"Error in _handle_game_details_callback: {e}")
            self.safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                f"❌ Error loading game details.\n\nError details: {str(e)}\n\n"
                f"Parameters:\n- day_key: {day_key}\n- alliance: {alliance}\n"
                f"- suballiance: {suballiance}",
            )

    def _handle_game_status_selection(self, call, alliance: str,
                                      suballiance: str, game: str,
                                      day_key: str):
        """Show status selection options for a specific game."""
        try:
            routing_data = self.sheets.get_schedule_for_suballiance(
                alliance, suballiance, day_key)
            game_info = None

            for entry in routing_data:
                if str(entry["game"]) == game:
                    game_info = entry
                    break

            if not game_info:
                self.bot.answer_callback_query(call.id, "❌ Game not found")
                return

            # Extract game details
            clean_game = str(game_info["game"])
            clean_location = str(game_info["location"])
            start_time = str(game_info["start_time"])
            end_time = str(game_info["end_time"])
            current_status = game_info["status"]
            current_hp = game_info.get("hp", 0)

            # Build response
            response = (
                f"🎮 {clean_game}\n\n"
                f"📍 Location: {clean_location}\n"
                f"⏰ Time: {start_time} - {end_time}\n"
                f"📊 Current Status: {STATUS_LABELS.get(current_status, current_status)}\n"
            )

            if current_status == "Completed" and current_hp > 0:
                response += f"🏆 Points Earned: {current_hp}\n"

            response += "\nSelect new status:"

            # Build status selection keyboard
            keyboard = InlineKeyboardMarkup()
            for status in [
                    "Default", "Next Station", "In Progress", "Completed"
            ]:
                status_label = STATUS_LABELS[status]
                is_current = "✓ " if status == current_status else ""

                keyboard.add(
                    InlineKeyboardButton(
                        f"{is_current}{status_label}",
                        callback_data=
                        f"status|{alliance}|{suballiance}|{game}|{status}|{day_key}",
                    ))

            keyboard.row(
                InlineKeyboardButton(
                    "🔙 Back to Schedule",
                    callback_data=f"{day_key}_{alliance}_{suballiance}"))

            self.safe_edit_message(call.message.chat.id,
                                   call.message.message_id,
                                   response,
                                   reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error in _handle_game_status_selection: {e}")
            self.bot.answer_callback_query(call.id,
                                           "❌ Error loading game details")