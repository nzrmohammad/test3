# file: webapp/services.py

from datetime import datetime, timedelta
from bot.combined_handler import get_combined_user_info
from bot.database import db
from bot.utils import format_shamsi_tehran
from .utils import days_until_next_birthday, format_shamsi_from_gregorian_days
import logging

logger = logging.getLogger(__name__)

def get_processed_user_data(uuid: str) -> dict | None:
    """
    تمام اطلاعات کاربر را از منابع مختلف گرفته، پردازش کرده و به صورت یکجا برمی‌گرداند.
    """
    info = get_combined_user_info(uuid)
    if not info:
        return None

    # پردازش اطلاعات جزئی سرورها
    breakdown = info.get('breakdown', {})
    if 'hiddify' in breakdown and breakdown.get('hiddify'):
        h_info = breakdown['hiddify']
        h_info['last_online_shamsi'] = format_shamsi_tehran(h_info.get('last_online'))
        h_info['daily_usage_formatted'] = f"{h_info.get('daily_usage_GB', 0):.2f} GB"

    if 'marzban' in breakdown and breakdown.get('marzban'):
        m_info = breakdown['marzban']
        m_info['last_online_shamsi'] = format_shamsi_tehran(m_info.get('last_online'))
        m_info['daily_usage_formatted'] = f"{m_info.get('daily_usage_GB', 0):.2f} GB"

    processed_info = info.copy()

    # --- FIX: اضافه کردن تاریخ انقضای شمسی خوانا ---
    processed_info['expire_shamsi'] = format_shamsi_from_gregorian_days(info.get('expire'))

    # دریافت اطلاعات تکمیلی از دیتابیس ربات
    user_telegram_id = db.get_user_id_by_uuid(uuid)
    if user_telegram_id:
        db_user = db.user(user_telegram_id)
        if db_user and db_user.get('birthday'):
            # اطمینان از اینکه تاریخ تولد به درستی پاس داده می‌شود
            processed_info['days_until_birthday'] = days_until_next_birthday(db_user['birthday'])
        
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if uuid_id:
            payments = db.get_user_payment_history(uuid_id)
            processed_info['payment_history'] = {
                'count': len(payments),
                'last_payment_date': format_shamsi_tehran(payments[0]['payment_date']) if payments else None
            }
            
    return processed_info