# Telegram Event Management Bot

## Overview

This is a Telegram bot designed for event management with role-based user system. The bot handles user registration, role assignments, and includes an alliance-based structure with admin controls. It uses Firebase Firestore for data persistence and implements a comprehensive user management system.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a modular architecture with clear separation of concerns:

- **Bot Layer**: Handles Telegram API interactions and message processing
- **Business Logic Layer**: Manages user operations, role assignments, and event logic
- **Data Layer**: Firebase Firestore with alliance-based collections for role-based access
- **Configuration Layer**: Environment-based configuration management
- **Health Server**: HTTP server for deployment health checks on port 5000

### Updated Architecture (August 2025)
- **Alliance-Based Authorization**: Users are stored in separate Firebase collections per alliance (Gaia, Terra, Aqua, Ignis)
- **Role-Based Access Control**: Authorization is checked via username in alliance collections
- **Dynamic Menu System**: Authorized users get routing menus, unauthorized users get access denied messages
- **Deployment Health Checks**: Added comprehensive health server for Cloud Run deployment with `/`, `/health`, and `/status` endpoints

## Key Components

### Core Modules

1. **main.py**: Entry point and bot orchestration
   - Initializes all components and starts the bot
   - Handles application lifecycle and error recovery

2. **bot_handlers.py**: Message and command handlers
   - Processes all user interactions
   - Implements command routing and response generation

3. **user_manager.py**: User registration and role management
   - Handles user registration flow
   - Manages role assignments and permissions
   - Maintains registration state during multi-step processes

4. **firebase_manager.py**: Database operations
   - Manages Firebase Firestore connections
   - Handles all CRUD operations for users and events
   - Provides data persistence layer

5. **config.py**: Configuration management
   - Loads environment variables
   - Defines role hierarchies and permissions
   - Manages bot settings and constants

6. **utils.py**: Helper functions
   - Creates inline keyboards for user interactions
   - Parses command arguments
   - Provides common utility functions

### Role System

The bot implements a hierarchical role system:

- **Alliance Roles**: Alliance 1-4 (regular users)
- **Admin Roles**: GM (Game Master) and EXCO (Executive Committee)
- Role-based permissions control access to admin commands

### User Registration Flow

Multi-step registration process:
1. User starts registration with /start command
2. System validates user information
3. Role selection through inline keyboard
4. Data persistence to Firebase

## Data Flow

1. **User Input**: Telegram messages/commands received by bot
2. **Handler Processing**: BotHandlers routes commands to appropriate methods
3. **Business Logic**: UserManager processes user operations
4. **Data Operations**: FirebaseManager handles database interactions
5. **Response**: Bot sends formatted responses back to users

## External Dependencies

### Firebase Integration
- **Purpose**: Primary database for user and event data
- **Configuration**: Supports both environment variable credentials and service account files
- **Collections**: Users and events stored in separate Firestore collections

### Telegram Bot API
- **Library**: pyTeleBot for Telegram interactions
- **Features**: Inline keyboards, message handling, callback processing

### Environment Variables
- `BOT_TOKEN`: Telegram bot authentication token
- `FIREBASE_CREDENTIALS`: JSON credentials for Firebase access
- `FIREBASE_DATABASE_URL`: Firebase project URL
- `MAX_HP` / `DEFAULT_HP`: Game mechanics settings

## Deployment Strategy

The application is designed for deployment on platforms that support:

- Python 3.x runtime
- Environment variable configuration
- Persistent logging to files
- Long-running processes (bot polling)

### Configuration Requirements
- Firebase service account with Firestore access
- Telegram bot token from BotFather
- Proper environment variable setup

### Logging Strategy
- File-based logging (bot.log)
- Console output for development
- Error tracking across all modules
- Structured logging with timestamps and levels

The architecture emphasizes modularity, making it easy to extend with new features like event management, HP systems, or additional admin commands while maintaining clean separation between Telegram interactions, business logic, and data persistence.

## Deployment Configuration (August 2025)

### Recent Fixes Applied (August 2025)
- **Health Server**: Now starts automatically without conditional environment variables
- **HTTP Endpoints**: All routes (`/`, `/health`, `/status`) return 200 status codes
- **Error Handling**: Comprehensive error handling with fallback responses
- **Port Binding**: Properly configured for `0.0.0.0:5000` deployment
- **Request Support**: Handles both GET and HEAD requests for health checks
- **Logging**: Enhanced deployment logging with environment and port information
- **Process Management**: Removed aggressive process killing logic that interfered with deployment
- **Webhook Management**: Enhanced with `delete_webhook(drop_pending_updates=True)` and improved retry logic
- **Code Structure**: Fixed indentation errors and cleaned up unused imports
- **Deployment Stability**: Resolved 409 conflict errors through better bot lifecycle management

### Deployment Requirements
- Python 3.11+ environment
- Required dependencies: `firebase-admin`, `pyTelegramBotAPI`, `python-dotenv`, `pytz`
- Environment variables: `BOT_TOKEN`, `PORT` (defaults to 5000)
- Health check endpoints respond on port 5000 for Cloud Run compatibility