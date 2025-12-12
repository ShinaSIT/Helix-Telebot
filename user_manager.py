"""
User management module for the Telegram Event Management Bot
Handles user registration, role management, and user operations
"""

import logging
from typing import Dict, List, Optional, Any
from config import Config

logger = logging.getLogger(__name__)

class UserManager:
    """Manages user registration, roles, and operations"""
    
    def __init__(self, firebase_manager):
        """
        Initialize UserManager
        
        Args:
            firebase_manager: FirebaseManager instance
        """
        self.firebase = firebase_manager
        self.config = Config()
        self.registration_states = {}  # Store temporary registration data

    def is_user_registered(self, telegram_id: int) -> bool:
        """
        Check if user is registered
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            bool: True if registered, False otherwise
        """
        return self.firebase.user_exists(telegram_id)

    def get_user_data(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user data
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User data dictionary or None
        """
        return self.firebase.get_user(telegram_id)

    def start_registration(self, telegram_id: int, username: str = None, first_name: str = None) -> Dict[str, str]:
        """
        Start user registration process
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            
        Returns:
            Dictionary with registration state and message
        """
        if self.is_user_registered(telegram_id):
            user_data = self.get_user_data(telegram_id)
            return {
                'status': 'already_registered',
                'message': f"You are already registered as {user_data.get('name', 'Unknown')} with role {user_data.get('role', 'Unknown')}!"
            }

        # Initialize registration state
        self.registration_states[telegram_id] = {
            'step': 'name',
            'telegram_id': telegram_id,
            'username': username if username is not None else '',
            'first_name': first_name if first_name is not None else ''
        }

        return {
            'status': 'name_required',
            'message': "Welcome to the Event Management System! 🎮\n\nPlease enter your full name for registration:"
        }

    def process_registration_step(self, telegram_id: int, message_text: str) -> Dict[str, Any]:
        """
        Process a step in the registration flow
        
        Args:
            telegram_id: Telegram user ID
            message_text: User's message
            
        Returns:
            Dictionary with next step information
        """
        if telegram_id not in self.registration_states:
            return {
                'status': 'error',
                'message': "Registration not started. Please use /start command."
            }

        state = self.registration_states[telegram_id]
        
        if state['step'] == 'name':
            return self._process_name_step(telegram_id, message_text)
        elif state['step'] == 'role':
            return self._process_role_step(telegram_id, message_text)
        else:
            return {
                'status': 'error',
                'message': "Invalid registration step. Please start over with /start."
            }

    def _process_name_step(self, telegram_id: int, name: str) -> Dict[str, Any]:
        """Process name input step"""
        if not name or len(name.strip()) < 2:
            return {
                'status': 'name_invalid',
                'message': "Please enter a valid name (at least 2 characters):"
            }

        # Store name and move to role selection
        self.registration_states[telegram_id]['name'] = name.strip()
        self.registration_states[telegram_id]['step'] = 'role'

        return {
            'status': 'role_selection',
            'message': f"Thank you, {name}! 👋\n\nNow please select your role:",
            'show_role_keyboard': True
        }

    def _process_role_step(self, telegram_id: int, role: str) -> Dict[str, Any]:
        """Process role selection step"""
        if not self.config.is_valid_role(role):
            return {
                'status': 'role_invalid',
                'message': "Please select a valid role from the options below:",
                'show_role_keyboard': True
            }

        # Complete registration
        state = self.registration_states[telegram_id]
        
        user_data = {
            'telegram_id': telegram_id,
            'username': state['username'],
            'name': state['name'],
            'role': role,
            'hp': self.config.DEFAULT_HP,
            'is_active': True
        }

        if self.firebase.create_user(user_data):
            # Clean up registration state
            del self.registration_states[telegram_id]
            
            # Log registration event
            self.firebase.log_event({
                'type': 'user_registration',
                'telegram_id': telegram_id,
                'name': user_data['name'],
                'role': role
            })

            return {
                'status': 'registration_complete',
                'message': f"✅ Registration complete!\n\n"
                          f"Name: {user_data['name']}\n"
                          f"Role: {role}\n"
                          f"HP: {user_data['hp']}\n\n"
                          f"Welcome to the event! Use /help to see available commands."
            }
        else:
            return {
                'status': 'error',
                'message': "❌ Registration failed due to database error. Please try again."
            }

    def update_user_role(self, admin_telegram_id: int, target_telegram_id: int, new_role: str) -> Dict[str, str]:
        """
        Update a user's role (admin only)
        
        Args:
            admin_telegram_id: Admin's Telegram ID
            target_telegram_id: Target user's Telegram ID
            new_role: New role to assign
            
        Returns:
            Dictionary with operation result
        """
        # Check if admin has permission
        admin_data = self.get_user_data(admin_telegram_id)
        if not admin_data or not self.config.is_admin_role(admin_data['role']):
            return {
                'status': 'error',
                'message': "❌ You don't have permission to change user roles."
            }

        # Validate new role
        if not self.config.is_valid_role(new_role):
            return {
                'status': 'error',
                'message': f"❌ Invalid role. Valid roles: {', '.join(self.config.VALID_ROLES)}"
            }

        # Check if target user exists
        target_data = self.get_user_data(target_telegram_id)
        if not target_data:
            return {
                'status': 'error',
                'message': "❌ Target user not found."
            }

        # Update role
        if self.firebase.update_user(target_telegram_id, {'role': new_role}):
            # Log the role change
            self.firebase.log_event({
                'type': 'role_change',
                'admin_id': admin_telegram_id,
                'target_id': target_telegram_id,
                'old_role': target_data['role'],
                'new_role': new_role
            })

            return {
                'status': 'success',
                'message': f"✅ Role updated successfully!\n"
                          f"User: {target_data['name']}\n"
                          f"Old Role: {target_data['role']}\n"
                          f"New Role: {new_role}"
            }
        else:
            return {
                'status': 'error',
                'message': "❌ Failed to update role due to database error."
            }

    def update_user_hp(self, telegram_id: int, new_hp: int) -> Dict[str, str]:
        """
        Update a user's HP
        
        Args:
            telegram_id: User's Telegram ID
            new_hp: New HP value
            
        Returns:
            Dictionary with operation result
        """
        # Validate HP value
        if new_hp < 0 or new_hp > self.config.MAX_HP:
            return {
                'status': 'error',
                'message': f"❌ HP must be between 0 and {self.config.MAX_HP}."
            }

        user_data = self.get_user_data(telegram_id)
        if not user_data:
            return {
                'status': 'error',
                'message': "❌ User not found. Please register first with /start."
            }

        if self.firebase.update_hp(telegram_id, new_hp):
            # Log HP change
            self.firebase.log_event({
                'type': 'hp_change',
                'telegram_id': telegram_id,
                'old_hp': user_data['hp'],
                'new_hp': new_hp
            })

            return {
                'status': 'success',
                'message': f"✅ HP updated successfully!\n"
                          f"Previous HP: {user_data['hp']}\n"
                          f"New HP: {new_hp}"
            }
        else:
            return {
                'status': 'error',
                'message': "❌ Failed to update HP due to database error."
            }

    def get_user_profile(self, telegram_id: int) -> Dict[str, str]:
        """
        Get user profile information
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            Dictionary with profile information
        """
        user_data = self.get_user_data(telegram_id)
        if not user_data:
            return {
                'status': 'not_registered',
                'message': "❌ You are not registered. Please use /start to register."
            }

        hp_bar = self._create_hp_bar(user_data['hp'])
        
        return {
            'status': 'success',
            'message': f"👤 **Your Profile**\n\n"
                      f"**Name:** {user_data['name']}\n"
                      f"**Role:** {user_data['role']}\n"
                      f"**HP:** {user_data['hp']}/{self.config.MAX_HP}\n"
                      f"{hp_bar}\n"
                      f"**Username:** @{user_data['username']}\n"
                      f"**Status:** {'Active' if user_data.get('is_active', True) else 'Inactive'}"
        }

    def get_users_list(self, requester_telegram_id: int, role_filter: Optional[str] = None) -> Dict[str, str]:
        """
        Get list of users (admin only)
        
        Args:
            requester_telegram_id: Requester's Telegram ID
            role_filter: Optional role filter
            
        Returns:
            Dictionary with users list
        """
        # Check permissions
        requester_data = self.get_user_data(requester_telegram_id)
        if not requester_data or not self.config.is_admin_role(requester_data['role']):
            return {
                'status': 'error',
                'message': "❌ You don't have permission to view user lists."
            }

        # Get users
        if role_filter:
            users = self.firebase.get_users_by_role(role_filter)
        else:
            users = self.firebase.get_all_users()

        if not users:
            return {
                'status': 'success',
                'message': f"📝 No users found{f' with role {role_filter}' if role_filter else ''}."
            }

        # Format user list
        message = f"📝 **User List{f' - {role_filter}' if role_filter else ''}**\n\n"
        
        # Group users by role
        users_by_role = {}
        for user in users:
            role = user['role']
            if role not in users_by_role:
                users_by_role[role] = []
            users_by_role[role].append(user)

        for role in self.config.VALID_ROLES:
            if role in users_by_role:
                message += f"**{role}:**\n"
                for user in users_by_role[role]:
                    hp_status = "💚" if user['hp'] > 70 else "💛" if user['hp'] > 30 else "❤️"
                    message += f"• {user['name']} - HP: {user['hp']} {hp_status}\n"
                message += "\n"

        return {
            'status': 'success',
            'message': message
        }

    def _create_hp_bar(self, hp: int) -> str:
        """
        Create a visual HP bar
        
        Args:
            hp: Current HP value
            
        Returns:
            String representation of HP bar
        """
        bar_length = 10
        filled_length = int(bar_length * hp / self.config.MAX_HP)
        
        if hp > 70:
            bar_char = "🟢"
        elif hp > 30:
            bar_char = "🟡"
        else:
            bar_char = "🔴"
        
        empty_char = "⚪"
        
        bar = bar_char * filled_length + empty_char * (bar_length - filled_length)
        return f"`{bar}`"

    def clear_registration_state(self, telegram_id: int):
        """Clear registration state for a user"""
        if telegram_id in self.registration_states:
            del self.registration_states[telegram_id]
