# file: webapp/services.py

from datetime import datetime, timedelta
from bot.combined_handler import get_combined_user_info
from bot.database import db
from bot.utils import format_shamsi_tehran
from .utils import days_until_next_birthday, format_shamsi_from_gregorian_days
import logging
import uuid

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
    
    # --- محاسبات جدید برای داشبورد ---
    # ۱. محاسبه مجموع مصرف روزانه (این بخش خطا را رفع می‌کند)
    h_daily = breakdown.get('hiddify', {}).get('daily_usage_GB', 0)
    m_daily = breakdown.get('marzban', {}).get('daily_usage_GB', 0)
    processed_info['total_daily_usage_GB'] = h_daily + m_daily

    # ۲. محاسبه درصد نوار زمان باقی‌مانده (برای نمایش ۳۰ روز آینده)
    days_left = info.get('expire')
    if days_left is not None and days_left > 0:
        time_progress_percent = min((days_left / 30) * 100, 100)
    else:
        # اگر زمان تمام شده یا نامحدود بود، درصد صفر است
        time_progress_percent = 0
    processed_info['time_progress_percent'] = time_progress_percent
    # --- پایان محاسبات جدید ---

    processed_info['expire_shamsi'] = format_shamsi_from_gregorian_days(info.get('expire'))

    # دریافت اطلاعات تکمیلی از دیتابیس ربات
    user_telegram_id = db.get_user_id_by_uuid(uuid)
    if user_telegram_id:
        db_user = db.user(user_telegram_id)
        if db_user and db_user.get('birthday'):
            processed_info['days_until_birthday'] = days_until_next_birthday(db_user['birthday'])
        
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if uuid_id:
            payments = db.get_user_payment_history(uuid_id)
            processed_info['payment_history'] = {
                'count': len(payments),
                'last_payment_date': format_shamsi_tehran(payments[0]['payment_date']) if payments else None
            }
            
    return processed_info

def generate_user_subscription_configs(user_main_uuid: str) -> list[str]:
    """
    برای یک کاربر، لیست کانفیگ‌های نهایی را بر اساس الگوهای فعال ادمین تولید می‌کند.
    """
    # ۱. اطلاعات کاربر اصلی را پیدا کن
    user_record = db.get_user_uuid_record(user_main_uuid)
    if not user_record:
        logger.warning(f"Subscription request for non-existent or inactive UUID: {user_main_uuid}")
        return []

    user_uuid_id = user_record['id']
    user_name = user_record.get('name', 'کاربر')

    # ۲. تمام الگوهای فعال را از دیتابیس بگیر
    active_templates = db.get_active_config_templates()
    final_configs = []

    for template in active_templates:
        # ۳. برای هر الگو، چک کن آیا قبلا برای این کاربر UUID ساخته شده؟
        config_record = db.get_user_config(user_uuid_id, template['id'])

        if config_record:
            # اگر ساخته شده بود، از همان استفاده کن
            generated_uuid = config_record['generated_uuid']
        else:
            # اگر نه، یک UUID جدید بساز و در دیتابیس ذخیره کن
            generated_uuid = str(uuid.uuid4())
            db.add_user_config(user_uuid_id, template['id'], generated_uuid)

        # ۴. متغیرها را در رشته الگو جایگذاری کن
        config_str = template['template_str']
        config_str = config_str.replace("{new_uuid}", generated_uuid)
        config_str = config_str.replace("{name}", user_name)
        
        final_configs.append(config_str)

    return final_configs