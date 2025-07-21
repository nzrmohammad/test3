from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .hiddify_api_handler import hiddify_handler
from .marzban_api_handler import marzban_handler
from .database import db
from .utils import validate_uuid
import logging
import pytz

logger = logging.getLogger(__name__)

def get_combined_user_info(identifier: str) -> Optional[Dict[str, Any]]:
    is_uuid = validate_uuid(identifier)
    h_info, m_info = None, None

    if is_uuid:
        h_info = hiddify_handler.user_info(identifier)
        m_info = marzban_handler.get_user_info(identifier)
    else:
        m_info = marzban_handler.get_user_by_username(identifier)
        if m_info and m_info.get('uuid'):
            h_info = hiddify_handler.user_info(m_info['uuid'])
            
    if not h_info and not m_info: return None

    base_info = (h_info or m_info).copy()
    
    base_info['breakdown'] = {
        'hiddify': h_info if h_info else {},
        'marzban': m_info if m_info else {}
    }
    
    h_limit = h_info.get('usage_limit_GB', 0) if h_info else 0
    m_limit = m_info.get('usage_limit_GB', 0) if m_info else 0
    total_limit = h_limit + m_limit
    
    h_usage = h_info.get('current_usage_GB', 0) if h_info else 0
    m_usage = m_info.get('current_usage_GB', 0) if m_info else 0
    total_usage = h_usage + m_usage
    
    base_info['usage_limit_GB'] = total_limit
    base_info['current_usage_GB'] = total_usage
    base_info['remaining_GB'] = max(0, total_limit - total_usage)
    base_info['usage_percentage'] = (total_usage / total_limit * 100) if total_limit > 0 else 0
    
    base_info['name'] = (h_info or m_info).get('name')
    h_online = h_info.get('last_online') if h_info else None
    m_online = m_info.get('last_online') if m_info else None
    
    # **تغییر اصلی اول: محاسبه مصرف روزانه در همین تابع**
    uuid = base_info.get('uuid')
    if uuid:
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if uuid_id:
            daily_usage_dict = db.get_usage_since_midnight(uuid_id)
            # افزودن مجموع مصرف روزانه به اطلاعات اصلی
            base_info['daily_usage_GB'] = sum(daily_usage_dict.values())
            # افزودن جزئیات مصرف روزانه به هر پنل
            if base_info.get('breakdown', {}).get('hiddify'):
                base_info['breakdown']['hiddify']['daily_usage'] = daily_usage_dict.get('hiddify', 0.0)
            if base_info.get('breakdown', {}).get('marzban'):
                base_info['breakdown']['marzban']['daily_usage'] = daily_usage_dict.get('marzban', 0.0)

    # مقایسه امن تاریخ‌ها برای پیدا کردن جدیدترین زمان آنلاین بودن
    latest_online = None
    if h_online and m_online:
        h_online_utc = h_online.astimezone(pytz.utc)
        m_online_utc = m_online.astimezone(pytz.utc)
        latest_online = max(h_online_utc, m_online_utc)
    else:
        latest_online = h_online or m_online

    base_info['last_online'] = latest_online

    return base_info

def modify_user_on_all_panels(identifier: str, add_gb: float = 0, add_days: int = 0, target_panel: str = 'both') -> bool:
    """
    Modifies a user on Hiddify, Marzban, or both, handling relative additions.
    This is a new, crucial function to fix editing bugs.
    """
    info = get_combined_user_info(identifier)
    if not info:
        logger.error(f"Cannot modify non-existent user: {identifier}")
        return False

    h_success, m_success = True, True  # Assume success if not targeted

    # --- Hiddify Modification ---
    if target_panel in ['hiddify', 'both'] and 'hiddify' in info.get('breakdown', {}):
        h_info = info['breakdown']['hiddify']
        h_payload = {}
        
        if add_gb != 0:
            current_limit = h_info.get('usage_limit_GB', 0)
            h_payload['usage_limit_GB'] = current_limit + add_gb
        
        if add_days != 0:
            # Hiddify needs an absolute number of days, so we calculate it.
            current_expire = h_info.get('expire', 0)
            # If expired, start from today. Otherwise, add to remaining days.
            base_days = current_expire if current_expire is not None and current_expire > 0 else 0
            h_payload['package_days'] = base_days + add_days

        if h_payload:
            h_success = hiddify_handler.modify_user(h_info['uuid'], h_payload)
        else:
            h_success = True # Nothing to do

    # --- Marzban Modification ---
    if target_panel in ['marzban', 'both'] and 'marzban' in info.get('breakdown', {}):
        m_info = info['breakdown']['marzban']
        # Marzban handler already supports relative additions directly
        m_success = marzban_handler.modify_user(
            username=m_info['name'],
            add_usage_gb=add_gb,
            add_days=add_days
        )

    return h_success and m_success

def delete_user_from_all_panels(identifier: str) -> bool:
    info = get_combined_user_info(identifier)
    if not info: return False
    h_success, m_success = True, True
    h_uuid = info.get('uuid')
    m_username = info.get('name') if 'marzban' in info.get('breakdown', {}) else None
    if h_uuid and 'hiddify' in info.get('breakdown', {}):
        h_success = hiddify_handler.delete_user(h_uuid)
    if m_username and 'marzban' in info.get('breakdown', {}):
        m_success = marzban_handler.delete_user(m_username)
    if h_success and m_success and h_uuid:
        db_id = db.get_uuid_id_by_uuid(h_uuid)
        if db_id:
            db.deactivate_uuid(db_id)
            db.delete_user_snapshots(db_id)
    return h_success and m_success

def get_all_users_combined() -> List[Dict[str, Any]]:
    logger.info("COMBINED_HANDLER: Starting to fetch users from all panels.") # لاگ شروع
    all_users_map = {}
    
    # FIX: Handle None return from API handlers to prevent crashes
    h_users = hiddify_handler.get_all_users() or []
    logger.info("COMBINED_HANDLER: Fetching from Hiddify...") # لاگ هیدیفای
    logger.info(f"COMBINED_HANDLER: Fetched {len(h_users)} users from Hiddify.") # لاگ تعداد
    for user in h_users:
        uuid = user['uuid']
        user['breakdown'] = {'hiddify': user.copy()}
        all_users_map[uuid] = user

    # FIX: Handle None return from API handlers
    logger.info("COMBINED_HANDLER: Fetching from Marzban...") # لاگ مرزبان
    m_users = marzban_handler.get_all_users() or []
    logger.info(f"COMBINED_HANDLER: Fetched {len(m_users)} users from Marzban.") # لاگ تعداد
    for user in m_users:
        uuid = user.get('uuid')
        if uuid and uuid in all_users_map:
            # User exists in Hiddify, add Marzban data to their breakdown
            all_users_map[uuid]['breakdown']['marzban'] = user.copy()
        elif uuid:
            # User only exists in Marzban but has a UUID
            user['breakdown'] = {'marzban': user.copy()}
            all_users_map[uuid] = user
        else:
            # User only exists in Marzban and has no UUID (use username as key)
            user['breakdown'] = {'marzban': user.copy()}
            all_users_map[user['name']] = user
            
    return list(all_users_map.values())

def search_user(query: str) -> List[Dict[str, Any]]:
    query_lower = query.lower()
    results, found_identifiers = [], set()

    all_users = get_all_users_combined()
    for user in all_users:
        identifier = user.get('uuid') or user.get('name')
        if identifier in found_identifiers: continue
        
        match = query_lower in user.get('name', '').lower() or \
                (user.get('uuid') and query_lower in user.get('uuid'))
        
        if match:
            panel = 'hiddify' if 'hiddify' in user.get('breakdown', {}) else 'marzban'
            results.append({**user, 'panel': panel})
            found_identifiers.add(identifier)
    return results