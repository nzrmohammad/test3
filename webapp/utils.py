# file: webapp/utils.py

from datetime import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

def days_until_next_birthday(birth_date_str: str | None) -> int | None:
    """تعداد روزهای باقی‌مانده تا تولد بعدی را محاسبه می‌کند."""
    if not birth_date_str:
        return None
    try:
        today = datetime.now()
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d')
        next_birthday = birth_date.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)
        return (next_birthday - today).days
    except (ValueError, TypeError):
        return None

def load_json_file(file_name: str) -> dict | list:
    """یک فایل JSON را از پوشه bot با مسیردهی امن بارگذاری می‌کند."""
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