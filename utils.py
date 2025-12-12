"""
Utility functions for the Telegram Event Management Bot
Contains helper functions for keyboard creation, command parsing, and other utilities
"""

import logging
from typing import List, Dict, Any, Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


def create_role_keyboard(roles: List[str]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    alliance_roles = [role for role in roles if role.startswith('Alliance')]
    for role in alliance_roles:
        keyboard.row(
            InlineKeyboardButton(f"⚔️ {role}", callback_data=f"role_{role}"))
    admin_roles = [role for role in roles if role in ['GM', 'EXCO']]
    if admin_roles:
        admin_buttons = []
        for role in admin_roles:
            icon = "👑" if role == "GM" else "🏛️"
            admin_buttons.append(
                InlineKeyboardButton(f"{icon} {role}",
                                     callback_data=f"role_{role}"))
        keyboard.row(*admin_buttons)
    return keyboard


def create_alliance_keyboard(prefix: str) -> InlineKeyboardMarkup:
    alliances = ['Gaia', 'Hydro', 'Ignis', 'Cirrus']
    keyboard = InlineKeyboardMarkup()
    for alliance in alliances:
        keyboard.row(
            InlineKeyboardButton(f"🏛️ {alliance}",
                                 callback_data=f"{prefix}_{alliance}"))
    keyboard.row(InlineKeyboardButton("🔙 Back", callback_data="show_routing"))
    return keyboard


def create_suballiance_keyboard(
    suballiances,
    alliance: str,
    prefix: str,
    include_all: bool = False,
    show_back: bool = True,     # <- new flag
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)

    if include_all:
        kb.add(InlineKeyboardButton("📊 ALL Groups Summary",
                                    callback_data=f"{prefix}_{alliance}_ALL"))

    # lay out suballiances 3 per row
    for i in range(0, len(suballiances), 3):
        row = [
            InlineKeyboardButton(f"👥 {sa}",
                                 callback_data=f"{prefix}_{alliance}_{sa}")
            for sa in suballiances[i:i+3]
        ]
        kb.row(*row)

    # Back only if requested
    if show_back:
        kb.row(InlineKeyboardButton("🔙 Back", callback_data="show_routing"))

    return kb


def parse_command_args(command_text: str) -> List[str]:
    try:
        parts = command_text.strip().split()
        return parts[1:] if len(parts) > 1 else []
    except Exception as e:
        logger.error(f"Error parsing command args: {e}")
        return []


def is_admin_command(command: str) -> bool:
    admin_commands = ['setrole', 'users', 'gm', 'exco']
    return command.lower() in admin_commands


def format_user_info(user_data: Dict[str, Any],
                     include_id: bool = False) -> str:
    try:
        info = f"**{user_data['name']}**\n"
        info += f"Role: {user_data['role']}\n"
        info += f"HP: {user_data['hp']}\n"
        if include_id:
            info += f"ID: {user_data['telegram_id']}\n"
        if user_data.get('username'):
            info += f"Username: @{user_data['username']}\n"
        return info
    except Exception as e:
        logger.error(f"Error formatting user info: {e}")
        return "Error formatting user information"


def create_hp_indicator(hp: int, max_hp: int = 100) -> str:
    percentage = (hp / max_hp) * 100
    if percentage > 80:
        return "💚"
    elif percentage > 60:
        return "💛"
    elif percentage > 40:
        return "🧡"
    elif percentage > 20:
        return "❤️"
    else:
        return "🖤"


def validate_telegram_id(telegram_id_str: str) -> Optional[int]:
    try:
        telegram_id = int(telegram_id_str)
        return telegram_id if telegram_id > 0 else None
    except ValueError:
        return None


def create_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("👥 All Users", callback_data="admin_all_users"),
        InlineKeyboardButton("⚔️ Alliances", callback_data="admin_alliances"))
    keyboard.row(
        InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        InlineKeyboardButton("🏥 Low HP", callback_data="admin_low_hp"))
    keyboard.row(
        InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"))
    return keyboard


def truncate_text(text: str, max_length: int = 4000) -> str:
    return text if len(text) <= max_length else text[:max_length - 3] + "..."


def log_user_action(user_id: int, action: str, details: str = ""):
    logger.info(f"User {user_id} performed action: {action} - {details}")


def generate_user_report(users: List[Dict[str, Any]]) -> str:
    if not users:
        return "No users found."
    total_users = len(users)
    roles_count = {}
    total_hp = 0
    low_hp_users = 0
    for user in users:
        role = user.get('role', 'Unknown')
        roles_count[role] = roles_count.get(role, 0) + 1
        hp = user.get('hp', 0)
        total_hp += hp
        if hp < 30:
            low_hp_users += 1
    avg_hp = total_hp / total_users if total_users > 0 else 0
    report = f"""
📊 **User Report**

**Total Users:** {total_users}
**Average HP:** {avg_hp:.1f}
**Low HP Users:** {low_hp_users}

**Role Distribution:**
"""
    for role, count in roles_count.items():
        report += f"• {role}: {count}\n"
    return report


def create_confirmation_keyboard(action: str,
                                 data: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Confirm",
                             callback_data=f"confirm_{action}_{data}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard


def sanitize_input(text: str) -> str:
    dangerous_chars = ['<', '>', '"', "'", '&', '`']
    sanitized = text
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    return sanitized.strip()


def get_user_display_name(user_data: Dict[str, Any]) -> str:
    name = user_data.get('name', '')
    username = user_data.get('username', '')
    return name or (f"@{username}" if username else
                    f"User {user_data.get('telegram_id', 'Unknown')}")


def debug_callback_data(callback_data: str) -> Dict[str, str]:
    """
    DEBUG HELPER: Parse callback data and show what each part represents
    """
    parts = callback_data.split('_')
    debug_info = {
        'raw_data': callback_data,
        'parts': parts,
        'part_count': len(parts)
    }

    if callback_data.startswith('routing_sub_'):
        if len(parts) >= 4:
            debug_info.update({
                'prefix': parts[0] + '_' + parts[1],  # routing_sub
                'alliance': parts[2],
                'suballiance': parts[3]
            })
        else:
            debug_info[
                'error'] = f"Expected 4 parts for routing_sub, got {len(parts)}"

    logger.info(f"DEBUG callback data: {debug_info}")
    return debug_info
