from datetime import datetime, timedelta
import pytz
from bot.database import db
from bot.hiddify_api_handler import hiddify_handler
from bot.marzban_api_handler import marzban_handler
from bot.combined_handler import get_all_users_combined, get_combined_user_info
from bot.utils import to_shamsi, format_relative_time, format_usage, days_until_next_birthday
import logging

logger = logging.getLogger(__name__)

# ===================================================================
# == توابع کمکی برای داشبورد ==
# ===================================================================

def _check_system_health():
    """وضعیت سلامت سرویس‌های خارجی را با مدیریت خطا بررسی می‌کند."""
    health = {}
    for name, handler in [('hiddify', hiddify_handler), ('marzban', marzban_handler), ('database', db)]:
        try:
            # --- تغییر: اطمینان از اینکه خروجی همیشه یک دیکشنری است ---
            result = handler.check_connection()
            if isinstance(result, bool):
                health[name] = {'ok': result}
            else:
                health[name] = result
        except Exception as e:
            logger.error(f"An exception occurred while checking connection for '{name}': {e}", exc_info=True)
            health[name] = {'ok': False, 'error': str(e)}
    return health


def _process_user_data(all_users_data):
    """
    داده‌های کاربران را پردازش کرده و آمار و لیست‌های مورد نیاز برای داشبورد را استخراج می‌کند.
    این نسخه بهبود یافته، کاربران روی هر دو پنل را نیز تفکیک می‌کند.
    """
    stats = {
        "total_users": len(all_users_data), "active_users": 0, "online_users": 0,
        "expiring_soon_count": 0, "total_usage_today_gb": 0, "new_users_today": 0,
        "hiddify_only_active": 0, "marzban_only_active": 0, "both_panels_active": 0
    }
    expiring_soon_users, online_users_hiddify, online_users_marzban = [], [], []
    db_users_map = {u['uuid']: u for u in db.get_all_user_uuids()}
    now_utc = datetime.now(pytz.utc)

    for user in all_users_data:
        daily_usage = db.get_usage_since_midnight_by_uuid(user.get('uuid', ''))
        user['daily_usage_gb'] = sum(daily_usage.values())
        stats['total_usage_today_gb'] += user['daily_usage_gb']

        is_on_hiddify = 'hiddify' in user.get('breakdown', {})
        is_on_marzban = 'marzban' in user.get('breakdown', {})

        if user.get('is_active'):
            stats['active_users'] += 1
            if is_on_hiddify and not is_on_marzban:
                stats['hiddify_only_active'] += 1
            elif is_on_marzban and not is_on_hiddify:
                stats['marzban_only_active'] += 1
            elif is_on_hiddify and is_on_marzban:
                stats['both_panels_active'] += 1

        is_online_in_any_panel = False
        for panel_name, online_list in [('hiddify', online_users_hiddify), ('marzban', online_users_marzban)]:
            panel_info = user.get('breakdown', {}).get(panel_name, {})
            if panel_info:
                last_online = panel_info.get('last_online')
                if last_online and isinstance(last_online, datetime):
                    last_online_aware = last_online if last_online.tzinfo else pytz.utc.localize(last_online)
                    if (now_utc - last_online_aware).total_seconds() < 180:
                        if not any(u['uuid'] == user['uuid'] for u in online_list):
                            online_list.append(user)
                        is_online_in_any_panel = True

        if is_online_in_any_panel:
            stats['online_users'] += 1

        expire_days = user.get('expire')
        if expire_days is not None and 0 <= expire_days <= 7:
            stats['expiring_soon_count'] += 1
            expiring_soon_users.append(user)

        db_user = db_users_map.get(user.get('uuid'))
        if db_user and db_user.get('created_at'):
            created_at_dt = db_user['created_at']
            if created_at_dt.tzinfo is None: created_at_dt = pytz.utc.localize(created_at_dt)
            if (now_utc - created_at_dt).days < 1: stats['new_users_today'] += 1
            user['created_at'] = created_at_dt

    return stats, expiring_soon_users, online_users_hiddify, online_users_marzban

# ===================================================================
# == تابع اصلی سرویس داشبورد ==
# ===================================================================

def get_dashboard_data():
    """
    تابع اصلی که داده‌های داشبورد را با فراخوانی توابع کمکی تولید می‌کند.
    این نسخه نهایی شامل تمام بهبودهای پیشنهادی است.
    """
    system_health = _check_system_health()
    
    # تعریف empty_stats در ابتدای تابع برای جلوگیری از مشکل scope
    empty_stats = {
        "total_users": 0, 
        "active_users": 0, 
        "expiring_soon_count": 0, 
        "online_users": 0, 
        "total_usage_today": "0 GB", 
        "new_users_today": 0
    }

    try:
        all_users_data = get_all_users_combined()
    except Exception as e:
        logger.error(f"Failed to get combined user data: {e}", exc_info=True)
        all_users_data = []

    try:
        # فراخوانی تابع جدید برای دریافت آمار مصرف روزانه
        daily_usage_summary = db.get_daily_usage_summary(days=7)
    except Exception as e:
        logger.error(f"Failed to get daily usage summary: {e}", exc_info=True)
        daily_usage_summary = []

    # اگر هیچ کاربری وجود نداشته باشد، یک پاسخ اولیه و خالی برگردان
    if not all_users_data:
        # ساخت داده پیش‌فرض برای نمودار مصرف ۷ روز اخیر
        usage_chart_data = {
            "labels": [to_shamsi(datetime.now() - timedelta(days=i), include_time=False) for i in range(6, -1, -1)],
            "data": [0] * 7
        }
        
        # تعریف top_consumers_today قبل از استفاده
        top_consumers_today = []
        top_consumers_chart_data = {
            "labels": [user['name'] for user in top_consumers_today],
            "data": [round(user.get('daily_usage_gb', 0), 2) for user in top_consumers_today]
        }

        return {
            "stats": empty_stats, 
            "recent_users": [], 
            "expiring_soon_users": [], 
            "top_consumers_today": top_consumers_today,
            "online_users_hiddify": [], 
            "online_users_marzban": [],
            "panel_distribution_data": {
                "labels": ["فقط آلمان 🇩🇪", "فقط فرانسه 🇫🇷", "هر دو پنل (مشترک)"], 
                "series": [0, 0, 0]
            },
            "system_health": system_health,
            "usage_chart_data": usage_chart_data,
            "top_consumers_chart_data": top_consumers_chart_data
        }

    # پردازش داده‌های کاربران موجود
    stats, expiring_soon_users, online_users_hiddify, online_users_marzban = _process_user_data(all_users_data)

    # تبدیل آمار مصرف روزانه به فرمت قابل نمایش
    stats['total_usage_today'] = f"{stats['total_usage_today_gb']:.2f} GB"
    
    # دریافت ۵ کاربر اخیر
    recent_users = sorted(
        [u for u in all_users_data if 'created_at' in u], 
        key=lambda u: u['created_at'], 
        reverse=True
    )[:5]
    
    # دریافت ۵ کاربر پرمصرف امروز
    top_consumers_today = sorted(
        [u for u in all_users_data if u.get('daily_usage_gb', 0) > 0], 
        key=lambda u: u.get('daily_usage_gb', 0), 
        reverse=True
    )[:5]
    
    # ساختار داده برای نمودار دایره‌ای (با سه بخش)
    panel_distribution_data = {
        "labels": ["فقط آلمان 🇩🇪", "فقط فرانسه 🇫🇷", "هر دو پنل (مشترک)"],
        "series": [
            stats.get('hiddify_only_active', 0), 
            stats.get('marzban_only_active', 0),
            stats.get('both_panels_active', 0)
        ]
    }
    
    # ساختار داده برای نمودار مصرف روزانه
    if daily_usage_summary:
        usage_chart_data = {
            "labels": [to_shamsi(datetime.strptime(item['date'], '%Y-%m-%d'), include_time=False) for item in daily_usage_summary],
            "data": [item['total_gb'] for item in daily_usage_summary]
        }
    else: 
        # اگر به هر دلیلی داده‌ای از دیتابیس نیامد، نمودار خالی نمایش داده شود
        usage_chart_data = {
            "labels": [to_shamsi(datetime.now() - timedelta(days=i), include_time=False) for i in range(6, -1, -1)],
            "data": [0] * 7
        }
    
    # ساختار داده برای نمودار پرمصرف‌ترین کاربران
    top_consumers_chart_data = {
        "labels": [user['name'] for user in top_consumers_today],
        "data": [round(user.get('daily_usage_gb', 0), 2) for user in top_consumers_today]
    }

    # برگرداندن تمام داده‌های پردازش شده
    return {
        "stats": stats,  # استفاده از stats واقعی، نه empty_stats
        "recent_users": recent_users, 
        "expiring_soon_users": expiring_soon_users, 
        "top_consumers_today": top_consumers_today,
        "online_users_hiddify": online_users_hiddify, 
        "online_users_marzban": online_users_marzban,
        "panel_distribution_data": panel_distribution_data,
        "system_health": system_health,
        "usage_chart_data": usage_chart_data,
        "top_consumers_chart_data": top_consumers_chart_data
    }


# ===================================================================
# == سرویس گزارش جامع ==
# ===================================================================
def generate_comprehensive_report_data():
    logger.info("Starting comprehensive report generation...")
    all_users_data = get_all_users_combined()
    daily_usage_map = db.get_all_daily_usage_since_midnight()
    user_panel_info_map = { u.get('uuid'): {'on_hiddify': u.get('on_hiddify', False), 'on_marzban': u.get('on_marzban', False)} for u in all_users_data if u.get('uuid') }
    now_utc = datetime.now(pytz.utc)
    summary = { "total_users": len(all_users_data), "active_users": 0, "total_de": 0, "total_fr": 0, "active_de": 0, "active_fr": 0, "online_users": 0, "usage_de_gb": 0, "usage_fr_gb": 0 }
    online_users, active_last_24h, inactive_1_to_7_days, never_connected, expiring_soon_users = set(), [], [], [], []
    
    for user in all_users_data:
        uuid = user.get('uuid')
        panels = []
        if user.get('on_hiddify'): panels.append('🇩🇪'); summary['total_de'] += 1
        if user.get('on_marzban'): panels.append('🇫🇷'); summary['total_fr'] += 1
        user['panel_display'] = ' '.join(panels) if panels else '?'
        user_daily_usage = daily_usage_map.get(uuid, {'hiddify': 0, 'marzban': 0})
        summary['usage_de_gb'] += user_daily_usage['hiddify']; summary['usage_fr_gb'] += user_daily_usage['marzban']
        if user.get("is_active"):
            summary['active_users'] += 1
            if user.get('on_hiddify'): summary['active_de'] += 1
            if user.get('on_marzban'): summary['active_fr'] += 1
        if user.get('expire') is not None and 0 <= user.get('expire') <= 7: expiring_soon_users.append(user)
        last_online = user.get('last_online')
        if last_online:
            if last_online >= (now_utc - timedelta(minutes=3)): online_users.add(uuid)
            if last_online >= (now_utc - timedelta(hours=24)): user['last_online_relative'] = format_relative_time(last_online); active_last_24h.append(user)
            elif (now_utc - timedelta(days=7)) <= last_online < (now_utc - timedelta(days=1)): user['last_online_relative'] = format_relative_time(last_online); inactive_1_to_7_days.append(user)
        else: never_connected.append(user)

    summary['online_users'] = len(online_users); summary['total_usage'] = f"{(summary['usage_de_gb'] + summary['usage_fr_gb']):.2f} GB"
    top_consumers = sorted([u for u in all_users_data if u.get('usage', {}).get('data_limit_GB', 0) > 0], key=lambda u: u.get('usage', {}).get('total_usage_GB', 0), reverse=True)[:10]
    users_with_payments = db.get_payment_history()
    uuid_by_configname = {u.get('name'): u.get('uuid') for u in all_users_data}
    for p in users_with_payments:
        uuid = uuid_by_configname.get(p['config_name']); panel_info = user_panel_info_map.get(uuid, {}); panels = []
        if panel_info.get('on_hiddify'): panels.append('🇩🇪')
        if panel_info.get('on_marzban'): panels.append('🇫🇷')
        p['panel_display'] = ' '.join(panels) if panels else '?'
    users_with_birthdays = db.get_users_with_birthdays()
    uuid_by_userid = {u['user_id']: u['uuid'] for u in db.get_all_user_uuids()}
    for b in users_with_birthdays:
        uuid = uuid_by_userid.get(b['user_id']); panel_info = user_panel_info_map.get(uuid, {}); panels = []
        if panel_info.get('on_hiddify'): panels.append('🇩🇪')
        if panel_info.get('on_marzban'): panels.append('🇫🇷')
        b['panel_display'] = ' '.join(panels) if panels else '?'
        if b.get('birthday'): 
            print('>> birthday:', b.get('birthday'), type(b.get('birthday')))
            try:
                b['birthday_shamsi'] = to_shamsi(b['birthday'])
                print('>> birthday_shamsi:', b['birthday_shamsi'])
            except Exception as e:
                print('>> ERROR in to_shamsi:', e)
            b['days_remaining'] = days_until_next_birthday(b['birthday'])

    
    return { "summary": summary, "active_last_24h": sorted(active_last_24h, key=lambda u: u.get('last_online'), reverse=True), "inactive_1_to_7_days": sorted(inactive_1_to_7_days, key=lambda u: u.get('last_online'), reverse=True), "never_connected": sorted(never_connected, key=lambda u: u.get('name', '').lower()), "top_consumers": top_consumers, "expiring_soon_users": sorted(expiring_soon_users, key=lambda u: u.get('expire', 999)), "bot_users": db.get_all_bot_users(), "users_with_payments": users_with_payments, "users_with_birthdays": sorted(users_with_birthdays, key=lambda u: u.get('days_remaining', 999)), "today_shamsi": to_shamsi(datetime.now()) }

# ===================================================================
# == سرویس مدیریت کاربران ==
# ===================================================================
def get_paginated_users(args: dict):
    page = args.get('page', 1, type=int); per_page = args.get('per_page', 15, type=int)
    search_query = args.get('search', '', type=str).lower()
    logger.info(f"Fetching paginated users. Page: {page}, Query: '{search_query}'")
    all_users_data = get_all_users_combined()
    for user in all_users_data:
        if user.get('uuid'):
            daily_usage = db.get_usage_since_midnight_by_uuid(user.get('uuid'));
            if user.get('on_hiddify'): user.setdefault('breakdown', {}).setdefault('hiddify', {})['daily_usage_formatted'] = format_usage(daily_usage.get('hiddify', 0))
            if user.get('on_marzban'): user.setdefault('breakdown', {}).setdefault('marzban', {})['daily_usage_formatted'] = format_usage(daily_usage.get('marzban', 0))
        if user.get('expire') is not None and user.get('expire') >= 0: user['expire_shamsi'] = to_shamsi(datetime.now() + timedelta(days=user.get('expire')))
        user['last_online_relative'] = format_relative_time(user.get('last_online'))
    filtered_users = [u for u in all_users_data if search_query in (u.get('name') or '').lower() or search_query in (u.get('uuid') or '').lower()] if search_query else all_users_data
    filtered_users.sort(key=lambda u: (u.get('name') or '').lower())
    total_items = len(filtered_users)
    paginated_users = filtered_users[(page - 1) * per_page : page * per_page]
    return { "users": paginated_users, "pagination": {"page": page, "per_page": per_page, "total_items": total_items, "total_pages": (total_items + per_page - 1) // per_page} }

def create_user_in_panel(data: dict):
    
    panel = data.get('panel')
    logger.info(f"Attempting to create a new user in panel: '{panel}' with data: {data}")

    if panel == 'hiddify': result = hiddify_handler.add_user(data)
    elif panel == 'marzban': result = marzban_handler.add_user(data)
    else:
        logger.warning(f"Invalid panel specified for user creation: '{panel}'")
        raise ValueError('پنل نامعتبر است.')
    if not result or not (result.get('uuid') or result.get('username')):
        error_detail = result.get('detail', 'Unknown error from panel API')
        logger.error(f"Failed to create user in panel '{panel}'. API Response: {error_detail}")
        raise Exception(error_detail)

    logger.info(f"Successfully created user in '{panel}'. Result: {result}")
    return result

def update_user_in_panels(data: dict):
    uuid = data.get('uuid')
    logger.info(f"Attempting to update user with UUID: {uuid}. Update data: {data}")

    if not uuid:
        logger.error("Update failed: UUID was not provided in the request data.") # <<< این خط
        raise ValueError('UUID کاربر برای ویرایش مشخص نشده است.')
    if 'h_usage_limit_GB' in data or 'h_package_days' in data:
        h_payload = { 'usage_limit_GB': data.get('h_usage_limit_GB'), 'package_days': data.get('h_package_days') }
        if data.get('common_name'): h_payload['name'] = data.get('common_name')
        logger.info(f"Updating Hiddify user '{uuid}' with payload: {h_payload}")
        hiddify_handler.modify_user(uuid, h_payload)
    if 'm_usage_limit_GB' in data or 'm_expire_days' in data:
        m_payload = { 'data_limit': int(float(data['m_usage_limit_GB']) * 1024**3) if data.get('m_usage_limit_GB') else None, 'expire': int(timedelta(days=int(data['m_expire_days'])).total_seconds()) if data.get('m_expire_days') else None }
        marzban_username = get_combined_user_info(uuid).get('breakdown',{}).get('marzban',{}).get('username')
        if marzban_username: marzban_handler.modify_user(marzban_username, data=m_payload)
        else:
            logger.warning(f"Could not update Marzban user for UUID {uuid} because Marzban username was not found.")

    elif 'common_name' in data and 'h_usage_limit_GB' not in data:
         hiddify_handler.modify_user(uuid, {'name': data.get('common_name')})

    logger.info(f"Update process finished for user UUID: {uuid}")
    return True

def delete_user_from_panels(uuid: str):
    logger.info(f"Starting deletion process for user with UUID: {uuid}")
    user_info = get_combined_user_info(uuid)
    if not user_info: 
        logger.warning(f"Deletion failed. User with UUID '{uuid}' not found in any panel.")
        raise ValueError('کاربر یافت نشد.')
    if user_info.get('on_hiddify'):
        logger.info(f"Deleting user '{uuid}' from Hiddify panel.")
        hiddify_handler.delete_user(uuid)
    if user_info.get('on_marzban'):
        username = user_info.get('breakdown', {}).get('marzban', {}).get('username')
        if username: marzban_handler.delete_user(username)

    logger.info(f"Deleting user record for UUID '{uuid}' from the local database.")
    db.delete_user_by_uuid(uuid)
    logger.info(f"Deletion process for UUID '{uuid}' completed successfully.")
    return True

# ===================================================================
# == سرویس مدیریت قالب‌ها ==
# ===================================================================
def add_templates_from_text(raw_text: str):
    VALID_PROTOCOLS = ('vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://')
    if not raw_text:
        logger.warning("add_templates_from_text called with empty input text.")
        raise ValueError('کادر ورود کانفیگ‌ها نمی‌تواند خالی باشد.')

    config_list = [line.strip() for line in raw_text.splitlines() if line.strip().startswith(VALID_PROTOCOLS)]
    if not config_list:
        logger.warning("No valid configs found in the provided text.")
        raise ValueError('هیچ کانفیگ معتبری یافت نشد.')

    added_count = db.add_batch_templates(config_list)
    logger.info(f"Successfully added {added_count} new templates to the database.")
    return added_count

def toggle_template(template_id: int):
    logger.info(f"Toggling status for template ID: {template_id}")
    db.toggle_template_status(template_id)
    return True

def update_template(template_id: int, template_str: str):
    logger.info(f"Attempting to update template ID: {template_id}")
    """یک قالب کانفیگ موجود را ویرایش می‌کند."""
    VALID_PROTOCOLS = ('vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://')
    if not template_str or not template_str.strip().startswith(VALID_PROTOCOLS):
        logger.warning(f"Update failed for template {template_id}: Invalid config string provided.") # <<< این خط
        raise ValueError('رشته کانفیگ ارائه شده معتبر نیست.')
    db.update_template(template_id, template_str.strip())
    return True

def delete_template(template_id: int):
    logger.info(f"Deleting template ID: {template_id}")
    db.delete_template(template_id)
    return True