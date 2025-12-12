"""
Configuration management for the Telegram Event Management Bot
Handles environment variables and bot settings
"""

import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration class for bot settings"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        # Telegram Bot Token
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        # Strip any whitespace from the token
        self.BOT_TOKEN = self.BOT_TOKEN.strip()
        
        # Validate token format
        if ':' not in self.BOT_TOKEN or len(self.BOT_TOKEN.split(':')) != 2:
            raise ValueError("Invalid BOT_TOKEN format. Expected format: 'bot_id:token'")
        
        # Firebase Configuration
        self.FIREBASE_CREDENTIALS = os.getenv('FIREBASE_CREDENTIALS')
        if not self.FIREBASE_CREDENTIALS:
            logger.warning("FIREBASE_CREDENTIALS not found, will try service account key file")
        
        self.FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL', '')
        
        # Bot Settings
        self.MAX_HP = int(os.getenv('MAX_HP', '100'))
        self.DEFAULT_HP = int(os.getenv('DEFAULT_HP', '100'))
        
        # Valid roles
        self.VALID_ROLES = [
            'Alliance 1', 'Alliance 2', 'Alliance 3', 'Alliance 4',
            'GM', 'EXCO'
        ]
        
        # Admin roles (can manage other users)
        self.ADMIN_ROLES = ['GM', 'EXCO']
        
        # Alliance roles
        self.ALLIANCE_ROLES = ['Alliance 1', 'Alliance 2', 'Alliance 3', 'Alliance 4']
        
        logger.info("Configuration loaded successfully")
    
    def is_admin_role(self, role):
        """Check if a role is an admin role"""
        return role in self.ADMIN_ROLES
    
    def is_alliance_role(self, role):
        """Check if a role is an alliance role"""
        return role in self.ALLIANCE_ROLES
    
    def is_valid_role(self, role):
        """Check if a role is valid"""
        return role in self.VALID_ROLES
