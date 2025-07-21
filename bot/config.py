import os
from datetime import time
import pytz
from cachetools import TTLCache
from dotenv import load_dotenv

load_dotenv()

def _parse_admin_ids(raw_ids: str | None) -> set[int]:
    if not raw_ids:
        return set()
    try:
        return {int(admin_id.strip()) for admin_id in raw_ids.split(',')}
    except ValueError:
        print("Warning: ADMIN_IDS environment variable contains non-integer values.")
        return set()

# --- Core Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
HIDDIFY_DOMAIN_RAW = os.getenv("HIDDIFY_DOMAIN", "")
HIDDIFY_DOMAIN = HIDDIFY_DOMAIN_RAW.rstrip("/") if HIDDIFY_DOMAIN_RAW else ""
ADMIN_PROXY_PATH_RAW = os.getenv("ADMIN_PROXY_PATH", "")
ADMIN_PROXY_PATH = ADMIN_PROXY_PATH_RAW.strip("/") if ADMIN_PROXY_PATH_RAW else ""
ADMIN_UUID = os.getenv("ADMIN_UUID")
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS")) or {265455450}

MARZBAN_API_BASE_URL = os.getenv("MARZBAN_API_BASE_URL", "https://panel2.fox1.eu.org:8000")
MARZBAN_API_USERNAME = os.getenv("MARZBAN_API_USERNAME")
MARZBAN_API_PASSWORD = os.getenv("MARZBAN_API_PASSWORD")

# --- Paths & Time ---
DATABASE_PATH = "bot_data.db"
TEHRAN_TZ = pytz.timezone("Asia/Tehran")
DAILY_REPORT_TIME = time(23, 59)
CLEANUP_TIME = time(23, 59)

ADMIN_SUPPORT_CONTACT = os.getenv("ADMIN_SUPPORT_CONTACT", "@Nzrmohammad")

PAGE_SIZE = 35

BIRTHDAY_GIFT_GB = 15  # حجم هدیه (گیگابایت)
BIRTHDAY_GIFT_DAYS = 15 # تعداد روز هدیه

TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024

CUSTOM_SUB_LINK_BASE_URL = "https://drive.google.com/uc?export=download&id="

# --- تعریف یک کش با زمان انقضای ۶۰ ثانیه ---
# maxsize=2 یعنی حداکثر ۲ نتیجه متفاوت (معمولاً ۱ نتیجه get_all_users) را نگه می‌دارد
api_cache = TTLCache(maxsize=2, ttl=60)

DAILY_USAGE_ALERT_THRESHOLD_GB = 5
WARNING_USAGE_THRESHOLD = 85 # آستانه هشدار مصرف به درصد
NOTIFY_ADMIN_ON_USAGE = True # فعال/غیرفعال کردن این قابلیت

USAGE_WARNING_CHECK_HOURS = 4    # فاصله زمانی چک کردن هشدار مصرف (به ساعت)
ONLINE_REPORT_UPDATE_HOURS = 3 # فاصله زمانی آپدیت گزارش کاربران آنلاین (به ساعت)

WARNING_90_PERCENT = 90
WARNING_DAYS_BEFORE_EXPIRY = 2

# --- API Settings ---
API_TIMEOUT = 15
API_RETRY_COUNT = 3

# --- Emojis & Visuals ---
EMOJIS = {
    "fire": "🔥", "chart": "📊", "warning": "⚠️", "error": "❌",
    "success": "✅", "info": "ℹ️", "key": "🔑", "bell": "🔔",
    "time": "⏰", "calendar": "📅", "money": "💰", "lightning": "⚡",
    "star": "⭐", "rocket": "🚀", "gear": "⚙️", "book": "📖",
    "home": "🏠", "user": "👤", "globe": "🌍", "wifi": "📡",
    "download": "📥", "upload": "📤", "database": "💾",
    "shield": "🛡️", "crown": "👑", 'trophy': '🏆',
    'database': '🗂️', 'back': '🔙'
}

PROGRESS_COLORS = {
    "safe": "🟢", "warning": "🟡", "danger": "🟠", "critical": "🔴"
}

# --- Logging ---
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
