from datetime import datetime, timedelta
from bot.combined_handler import get_combined_user_info
from bot.database import db
from bot.utils import format_daily_usage
from .utils import format_shamsi_tehran, format_relative_time, format_shamsi_from_gregorian_days
import logging

logger = logging.getLogger(__name__)

def get_processed_user_data(uuid: str) -> dict | None:
    info = get_combined_user_info(uuid)
    if not info:
        return None

    processed_info = info.copy()
    breakdown = info.get('breakdown', {})
    
    processed_info['on_hiddify'] = 'hiddify' in breakdown and bool(breakdown.get('hiddify'))
    processed_info['on_marzban'] = 'marzban' in breakdown and bool(breakdown.get('marzban'))

    # استفاده از تابع جدید برای زمان نسبی
    processed_info['last_online_relative'] = format_relative_time(info.get('last_online'))
    
    # پردازش جزئیات هر پنل
    if processed_info['on_hiddify']:
        h_info = breakdown['hiddify']
        h_info['last_online_shamsi'] = format_shamsi_tehran(h_info.get('last_online'))
        daily_usage_h = info.get('breakdown', {}).get('hiddify', {}).get('daily_usage', 0.0)
        h_info['daily_usage_formatted'] = format_daily_usage(daily_usage_h)

    if processed_info['on_marzban']:
        m_info = breakdown['marzban']
        m_info['last_online_shamsi'] = format_shamsi_tehran(m_info.get('last_online'))
        daily_usage_m = info.get('breakdown', {}).get('marzban', {}).get('daily_usage', 0.0)
        m_info['daily_usage_formatted'] = format_daily_usage(daily_usage_m)

    # استفاده از تابع جدید برای تاریخ انقضا
    processed_info['expire_shamsi'] = format_shamsi_from_gregorian_days(info.get('expire'))

    # دریافت created_at از دیتابیس برای مرتب‌سازی کاربران جدید (اختیاری ولی مفید)
    user_record = db.get_user_uuid_record(uuid)
    if user_record:
        processed_info['created_at'] = user_record.get('created_at')

    return processed_info

def generate_user_subscription_configs(user_main_uuid: str) -> list[str]:
    """
    برای یک کاربر، لیست کانفیگ‌های نهایی را بر اساس الگوهای فعال ادمین تولید می‌کند.
    **اصلاح شده:** به جای ساخت UUID جدید، از UUID اصلی کاربر استفاده می‌کند.
    """
    # ۱. اطلاعات کاربر اصلی را پیدا کن (برای گرفتن نام)
    user_record = db.get_user_uuid_record(user_main_uuid)
    user_name = user_record.get('name', 'کاربر') if user_record else 'کاربر'

    # ۲. تمام الگوهای فعال را از دیتابیس بگیر
    active_templates = db.get_active_config_templates()
    final_configs = []

    for template in active_templates:
        # ۳. متغیرها را در رشته الگو جایگذاری کن
        config_str = template['template_str']
        # **تغییر اصلی:** به جای new_uuid از user_main_uuid استفاده می‌شود
        config_str = config_str.replace("{new_uuid}", user_main_uuid) 
        config_str = config_str.replace("{name}", user_name)
        
        final_configs.append(config_str)

    return final_configs