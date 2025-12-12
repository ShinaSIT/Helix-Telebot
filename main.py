import logging
import time
import os
import fcntl
import sys
import signal
from threading import Thread
import telebot
from telebot.apihelper import ApiTelegramException
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import Config
from firebase_manager import FirebaseManager
from bot_handlers import BotHandlers
from user_manager import UserManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'),
              logging.StreamHandler()])
logger = logging.getLogger(__name__)


class EventBot:

    def __init__(self):
        """Initialize the Event Management Bot"""
        try:
            self.config = Config()
            self.firebase_manager = FirebaseManager()
            self.user_manager = UserManager(self.firebase_manager)
            self.running = True
            self.lock_file = None

            if not self.config.BOT_TOKEN:
                raise ValueError("BOT_TOKEN is required")
            self.bot = telebot.TeleBot(self.config.BOT_TOKEN)
            self.bot_handlers = BotHandlers(self.bot, self.user_manager,
                                            self.firebase_manager)

            self._register_handlers()
            self._setup_signal_handlers()

            # Test Firebase connection on startup
            if not self._test_connections():
                logger.warning("Some connections failed during startup, but continuing...")

            logger.info("Bot initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise

    def _test_connections(self) -> bool:
        """Test all critical connections on startup"""
        try:
            logger.info("Testing Firebase connection...")
            firebase_ok = self.firebase_manager.test_connection()

            if firebase_ok:
                logger.info("✅ Firebase connection successful")
            else:
                logger.error("❌ Firebase connection failed")

            return firebase_ok

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(
                f"Received signal {signum}, shutting down gracefully...")
            self.running = False
            self._cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _acquire_lock(self):
        """Acquire a file lock to prevent multiple instances"""
        lock_file_path = '/tmp/event_bot.lock'
        try:
            # Remove any existing lock file
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)
                logger.info("Removed existing lock file")

            # Create new lock file
            self.lock_file = open(lock_file_path, 'w')
            fcntl.lockf(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            logger.info(f"Lock acquired with PID {os.getpid()}")
            return True

        except (IOError, OSError) as e:
            logger.error(f"Failed to acquire lock: {e}")
            if self.lock_file:
                self.lock_file.close()
            return False

    def _cleanup(self):
        """Clean up resources"""
        if self.lock_file:
            try:
                fcntl.lockf(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
                logger.info("Lock released")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")

    def _clear_webhook(self):
        """Clear any existing webhook to ensure polling works"""
        try:
            # Use delete_webhook which is more thorough
            result = self.bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"Webhook cleared successfully: {result}")
            time.sleep(3)  # Give Telegram more time to process
        except Exception as e:
            logger.warning(f"Could not clear webhook: {e}")
            # Fallback to remove_webhook
            try:
                self.bot.remove_webhook()
                logger.info("Fallback webhook removal successful")
                time.sleep(2)
            except Exception as e2:
                logger.warning(f"Fallback webhook removal also failed: {e2}")

    def _register_handlers(self):
        """Register all bot command and message handlers"""
        b = self.bot_handlers

        # Commands
        self.bot.message_handler(commands=['start'])(b.handle_start)

        # Reply‑keyboard (menu) buttons - Routing & Test
        self.bot.message_handler(func=lambda m: m.text == "📍 Routing")(b.handle_menu_routing)
        self.bot.message_handler(func=lambda m: m.text == "🔧 Test Connection")(b.handle_menu_test)

        # HP System buttons
        self.bot.message_handler(func=lambda m: m.text == "💚 HP Dashboard")(b.handle_menu_hp_dashboard)
        self.bot.message_handler(func=lambda m: m.text == "💚 Suballiance HP")(b.handle_menu_my_hp)
        self.bot.message_handler(func=lambda m: m.text == "🎮 GM Interface")(b.handle_menu_gm_interface)

        # Cache stats handler
        self.bot.message_handler(func=lambda m: m.text == "📊 Cache Stats")(b.handle_menu_cache_stats)

        # Callbacks from inline keyboards
        self.bot.callback_query_handler(func=lambda call: True)(b.handle_callback_query)

    def keep_alive(self):

        class HealthHandler(BaseHTTPRequestHandler):

            def do_GET(self):
                try:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()

                    # Enhanced health check response
                    status_info = f"""
                    <!DOCTYPE html>
                    <html>
                    <head><title>Event Management Bot</title></head>
                    <body>
                        <h1>Event Management Bot is Running!</h1>
                        <p>Status: ✅ Active</p>
                        <p>PID: {os.getpid()}</p>
                        <p>Path: {self.path}</p>
                        <p>Bot initialized and polling active</p>
                    </body>
                    </html>
                    """
                    self.wfile.write(status_info.encode())
                    logger.debug(f"Health check served for path: {self.path}")
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(f"Internal Server Error: {str(e)}".encode())
                    except:
                        pass

            def do_HEAD(self):
                # Handle HEAD requests for health checks
                try:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                except Exception as e:
                    logger.error(f"HEAD request error: {e}")

            def log_message(self, format, *args):
                # Suppress default logging but log important requests
                message = format % args
                if any(keyword in message for keyword in ['GET /', 'HEAD /', 'health', 'status']):
                    logger.debug(f"HTTP: {message}")

        port = int(os.getenv("PORT", "5000"))
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                server = HTTPServer(('0.0.0.0', port), HealthHandler)
                logger.info(f"✅ Health check server started on 0.0.0.0:{port}")
                server.serve_forever()
                break
            except OSError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Health server start attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Health server failed to start after {max_retries} attempts: {e}")

    def run(self):
        # Acquire lock 
        if not self._acquire_lock():
            logger.error("Cannot start bot - failed to acquire lock")
            return False

        try:
            # Clear webhook multiple times to be sure
            for i in range(5):  # Increase attempts
                logger.info(f"Clearing webhook attempt {i+1}")
                self._clear_webhook()
                time.sleep(2)  # Longer delay between attempts

            # Always start the health server
            Thread(target=self.keep_alive, daemon=True).start()

            # Wait longer before starting polling to ensure no conflicts
            logger.info("Waiting 10 seconds before starting polling to avoid conflicts...")
            time.sleep(10)

            logger.info("🚀 Starting bot polling...")
            consecutive_409_errors = 0
            max_consecutive_409 = 3  # Increase threshold to be more patient

            while self.running:
                try:
                    logger.info("Starting polling session...")
                    self.bot.polling(none_stop=True, interval=1, timeout=60)
                    consecutive_409_errors = 0  # Reset counter on successful polling

                except ApiTelegramException as e:
                    if e.error_code == 409:
                        consecutive_409_errors += 1
                        logger.error(
                            f"🔥 409 Conflict error #{consecutive_409_errors}: {e}"
                        )

                        if consecutive_409_errors >= max_consecutive_409:
                            logger.error("🔥 TOO MANY 409 ERRORS - Clearing webhook and resetting")
                            
                            # Clear webhook aggressively
                            for i in range(5):
                                self._clear_webhook()
                                time.sleep(2)

                            consecutive_409_errors = 0  # Reset and try again
                            time.sleep(10)  # Longer wait
                            continue

                        # Shorter backoff
                        backoff_time = 5 + (consecutive_409_errors * 2)
                        logger.info(f"Backing off for {backoff_time} seconds...")
                        time.sleep(backoff_time)

                        # Clear webhook again
                        self._clear_webhook()
                    else:
                        logger.error(f"Telegram API error {e.error_code}: {e}")
                        time.sleep(10)

                except Exception as e:
                    logger.error(f"Bot polling error: {e}")
                    consecutive_409_errors = 0
                    time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            self.running = False
            self._cleanup()

        return True


def main():
    """Main entry point"""
    try:
        # Log startup information
        logger.info("=" * 50)
        logger.info("🚀 Starting Event Management Bot")
        logger.info("=" * 50)

        bot = EventBot()
        success = bot.run()

        if not success:
            logger.error("Bot failed to start properly")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()