from datetime import datetime, timedelta
import jdatetime
import pytz
import logging
import os,json

logger = logging.getLogger(__name__)

# دیکشنری برای ترجمه نام ماه‌ها به فارسی
PERSIAN_MONTHS = {
    "Farvardin": "فروردین", "Ordibehesht": "اردیبهشت", "Khordad": "خرداد",
    "Tir": "تیر", "Mordad": "مرداد", "Shahrivar": "شهریور",
    "Mehr": "مهر", "Aban": "آبان", "Azar": "آذر",
    "Dey": "دی", "Bahman": "بهمن", "Esfand": "اسفند"
}

def format_relative_time(dt: datetime | None) -> str | None:
    """یک شیء datetime را به زمان نسبی خوانا تبدیل می‌کند (مثلا: ۵ دقیقه پیش)."""
    if not dt or not isinstance(dt, datetime):
        return None
    now = datetime.now(pytz.utc) # <<<< اینجا pyz به pytz تغییر کرد
    dt_utc = dt.astimezone(pytz.utc) # <<<< اینجا pyz به pytz تغییر کرد
    delta = now - dt_utc

    seconds = delta.total_seconds()
    if seconds < 60:
        return "همین الان"
    minutes = int(seconds / 60)
    if minutes < 60:
        return f"{minutes} دقیقه پیش"
    hours = int(minutes / 60)
    if hours < 24:
        return f"{hours} ساعت پیش"
    days = int(hours / 24)
    return f"{days} روز پیش"

def format_shamsi_tehran(dt: datetime | None) -> str | None:
    """یک شیء datetime را به تاریخ و زمان شمسی تهران تبدیل می‌کند."""
    if not dt or not isinstance(dt, datetime):
        return None
    try:
        tehran_tz = pytz.timezone("Asia/Tehran")
        dt_tehran = dt.astimezone(tehran_tz)
        dt_shamsi = jdatetime.datetime.fromgregorian(datetime=dt_tehran)
        return dt_shamsi.strftime("%Y/%m/%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Error formatting shamsi date: {e}")
        return None

def days_until_next_birthday(birthdate_str: str | None) -> int | None:
    """تعداد روزهای باقی‌مانده تا تولد بعدی کاربر را محاسبه می‌کند."""
    if not birthdate_str:
        return None
    try:
        birth_date = datetime.strptime(str(birthdate_str), '%Y-%m-%d').date()
        today = datetime.now().date()
        next_birthday = birth_date.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)
        return (next_birthday - today).days
    except (ValueError, TypeError):
        return None

def format_shamsi_from_gregorian_days(days_left: int | None) -> str:
    """تعداد روزهای باقی‌مانده را به تاریخ شمسی کامل و خوانا تبدیل می‌کند."""
    if days_left is None:
        return "نامحدود"
    if days_left < 0:
        return "منقضی شده"
    try:
        expire_date_gregorian = datetime.now() + timedelta(days=days_left)
        expire_date_shamsi = jdatetime.date.fromgregorian(date=expire_date_gregorian)
        
        # فرمت انگلیسی تاریخ را می‌گیریم (e.g., "25 May 2025")
        formatted_date_en = expire_date_shamsi.strftime("%d %B %Y")
        
        # ماه انگلیسی را با معادل فارسی آن جایگزین می‌کنیم
        for en, fa in PERSIAN_MONTHS.items():
            if en in formatted_date_en:
                return formatted_date_en.replace(en, fa)
        return formatted_date_en
    except Exception:
        return f"{days_left} روز"

def load_json_file(file_name: str) -> dict | list:
    try:
        script_dir = os.path.dirname(__file__)
        file_path = os.path.join(script_dir, '..', 'bot', file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {file_name}")
        return {} if file_name.endswith('.json') else [] # بر اساس نوع فایل، خروجی مناسب برمی‌گرداند
    except Exception as e:
        logger.error(f"Failed to load or parse {file_name}: {e}")
        return {} if file_name.endswith('.json') else []