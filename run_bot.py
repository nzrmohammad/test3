# run_bot.py
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# حالا می‌توانیم از داخل پوشه bot ایمپورت کنیم
from bot.custom_bot import HiddifyBot, setup_bot_logging # <-- تابع جدید را ایمپورت می‌کنیم

if __name__ == "__main__":
    # قبل از هر کاری، تنظیمات لاگ را فقط برای ربات اعمال می‌کنیم
    setup_bot_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting bot instance...")

    bot_instance = HiddifyBot()
    try:
        bot_instance.start()
    except Exception as e:
        logger.critical(f"Bot failed to start from run_bot.py: {e}", exc_info=True)
