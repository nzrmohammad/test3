# file: bot/utils.py

import re
import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import Union, Optional
import pytz
import jdatetime
from .config import PROGRESS_COLORS

logger = logging.getLogger(__name__)
bot = None

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")

def initialize_utils(b_instance):
    global bot
    bot = b_instance

# ==============================================================================
# تابع اصلاح شده و هوشمند
# ==============================================================================
def load_service_plans():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        json_path = os.path.join(script_dir, 'plans.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"CRITICAL ERROR: 'plans.json' could not be found at the expected path: {json_path}")
        return []
    except Exception as e:
        logger.error(f"CRITICAL ERROR: Failed to load or parse 'plans.json'. Error: {e}")
        return []
# ==============================================================================

def validate_uuid(uuid_str: str) -> bool:
    return bool(_UUID_RE.match(uuid_str.strip())) if uuid_str else False

def _safe_edit(chat_id: int, msg_id: int, text: str, **kwargs):
    if not bot: return
    try:
        kwargs.setdefault('parse_mode', 'MarkdownV2')
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=msg_id, **kwargs)
    except Exception as e:
        logger.error(f"Safe edit failed: {e}. Text was: \n---\n{text}\n---")

def escape_markdown(text: Union[str, int, float]) -> str:
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_relative_time(dt: Optional[datetime]) -> str:
    # ... (بقیه توابع بدون تغییر باقی می‌مانند)
    if not dt: return "Unknown"
    now = datetime.now(pytz.utc)
    if dt.tzinfo is None: dt = pytz.utc.localize(dt)
    diff = now - dt.astimezone(pytz.utc)
    days, seconds = diff.days, diff.seconds

    if days > 365: return f"{days // 365} year(s) ago"
    if days > 30: return f"{days // 30} month(s) ago"
    if days > 0: return f"{days} day(s) ago"
    if seconds > 3600: return f"{seconds // 3600} hour(s) ago"
    if seconds > 60: return f"{seconds // 60} minute(s) ago"
    return "just now"

def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def create_progress_bar(percent: float, length: int = 15) -> str:
    percent = max(0, min(100, percent))
    filled_count = int(percent / 100 * length)
    
    filled_bar = '█' * filled_count
    empty_bar = '░' * (length - filled_count)
    
    escaped_percent_str = escape_markdown(f"{percent:.1f}%")
    
    return f"`{filled_bar}{empty_bar} {escaped_percent_str}`"

def format_daily_usage(gb: float) -> str:
    if gb < 0: return "0 MB"
    if gb < 1: return f"{gb * 1024:.0f} MB"
    return f"{gb:.2f} GB"

def load_custom_links():
    try:
        with open('custom_sub_links.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception: return {}

def format_shamsi_tehran(dt_obj: Optional[datetime]) -> str:
    if not isinstance(dt_obj, datetime):
        return "هرگز"

    tehran_tz = pytz.timezone("Asia/Tehran")
    try:
        if dt_obj.tzinfo is None:
            dt_obj = pytz.utc.localize(dt_obj)
        tehran_dt = dt_obj.astimezone(tehran_tz)
        j_date = jdatetime.datetime.fromgregorian(datetime=tehran_dt)
        return j_date.strftime('%Y/%m/%d %H:%M:%S')
    except Exception:
        return "تاریخ نامعتبر"


def parse_volume_string(volume_str: str) -> int:
    if not isinstance(volume_str, str):
        return 0
    numbers = re.findall(r'\d+', volume_str)
    if numbers:
        return int(numbers[0])
    return 0

def gregorian_to_shamsi_str(gregorian_date: Optional[Union[datetime, date]]) -> str:
    if not gregorian_date:
        return "نامشخص"

    if isinstance(gregorian_date, date) and not isinstance(gregorian_date, datetime):
        gregorian_date = datetime.combine(gregorian_date, datetime.min.time())

    if not isinstance(gregorian_date, datetime):
        return "نامشخص"
        
    try:
        j_date = jdatetime.datetime.fromgregorian(datetime=gregorian_date)
        return j_date.strftime('%Y/%m/%d')
    except (ValueError, TypeError):
        return "نامشخص"

def days_until_next_birthday(birthday: Optional[date]) -> Optional[int]:
    if not birthday:
        return None
    
    today = date.today()
    # Handle both datetime.date and datetime.datetime objects from database
    if isinstance(birthday, datetime):
        birthday = birthday.date()
        
    next_birthday = birthday.replace(year=today.year)
    
    if next_birthday < today:
        next_birthday = next_birthday.replace(year=today.year + 1)
        
    return (next_birthday - today).days