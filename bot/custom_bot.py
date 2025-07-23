import logging
import sys
import signal
import time
from datetime import datetime
from telebot import TeleBot

from .config import LOG_LEVEL, ADMIN_IDS, BOT_TOKEN
from .database import db
from .scheduler import SchedulerManager
from .user_handlers import register_user_handlers
from .admin_router import register_admin_handlers
from .callback_router import register_callback_router
from .utils import initialize_utils

def setup_bot_logging():
    """یک تابع جداگانه برای تنظیم لاگ‌های ربات جهت جلوگیری از تداخل با Gunicorn"""
    class UserIdFilter(logging.Filter):
        """A filter to add a default user_id to records that don't have one."""
        def filter(self, record):
            if not hasattr(record, 'user_id'):
                record.user_id = 'SYSTEM'
            return True

    # --- Unified Log Format ---
    LOG_FORMAT = "%(asctime)s — %(name)s — %(levelname)s — [User:%(user_id)s] — %(message)s"

    # Get the root logger
    root_logger = logging.getLogger()
    
    # فقط اگر از قبل handler وجود نداشت، تنظیمات را اعمال می‌کنیم
    if not root_logger.hasHandlers():
        root_logger.setLevel(LOG_LEVEL)

        # Create a single formatter and a single filter
        log_formatter = logging.Formatter(LOG_FORMAT)
        user_id_filter = UserIdFilter()

        # 1. Handler for bot.log (INFO and above)
        info_handler = logging.FileHandler("bot.log", encoding="utf-8")
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(log_formatter)
        info_handler.addFilter(user_id_filter)

        # 2. Handler for error.log (ERROR and above)
        error_handler = logging.FileHandler("error.log", encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_formatter)
        error_handler.addFilter(user_id_filter)

        # 3. Handler for console output
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(log_formatter)
        stream_handler.addFilter(user_id_filter)

        # Add all handlers to the root logger
        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(stream_handler)


# ==================== بخش اصلی ربات ====================

# Logger for this module
logger = logging.getLogger(__name__)

# Create the single bot instance
bot = TeleBot(BOT_TOKEN, parse_mode=None)
initialize_utils(bot)
scheduler = SchedulerManager(bot)

def _notify_admins_start() -> None:
    """Notifies admins when the bot restarts."""
    text = "🚀 ربات با موفقیت فعال شد"
    for aid in ADMIN_IDS:
        try:
            bot.send_message(aid, text, parse_mode=None)
        except Exception as e:
            logger.warning(f"Could not send start notification to admin {aid}: {e}")

class HiddifyBot:
    """Bot lifecycle manager"""
    def __init__(self) -> None:
        self.bot = bot
        self.running = False
        self.started_at: datetime | None = None
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

    def _on_signal(self, signum, _frame):
        logger.info(f"Received signal {signum} -> shutting down...")
        self.shutdown()
        sys.exit(0)

    def start(self) -> None:
        if self.running:
            logger.warning("Bot already running")
            return
        try:
            logger.info("Registering handlers...")

            register_user_handlers(self.bot)
            register_admin_handlers(self.bot)
            register_callback_router(self.bot)
            logger.info("✅ Handlers registered")

            logger.info("Testing Database connectivity...")
            db.user(0)  # Test DB connection
            logger.info("✅ SQLite ready")

            scheduler.start()
            logger.info("✅ Scheduler thread started")

            _notify_admins_start()

            self.running = True
            self.started_at = datetime.now()

            logger.info("🚀 Polling...")
            while self.running:
                try:
                    self.bot.infinity_polling(timeout=20, skip_pending=True)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Bot polling failed: {e}", exc_info=True)
                    logger.info("Restarting polling in 15 seconds...")
                    time.sleep(15)

        except Exception as exc:
            logger.exception(f"Start-up failed: {exc}")
            self.shutdown()
            raise

    def shutdown(self) -> None:
        if not self.running: return
        logger.info("Graceful shutdown...")
        self.running = False
        try:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
            self.bot.stop_polling()
            logger.info("Telegram polling stopped")
            if self.started_at:
                uptime = datetime.now() - self.started_at
                logger.info(f"Uptime: {uptime}")
        finally:
            self.running = False
            logger.info("Shutdown complete")