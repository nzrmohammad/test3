from flask import Blueprint, render_template, request, abort, jsonify
from functools import wraps
import logging
from datetime import datetime, timedelta
import pytz
from bot.config import ADMIN_SECRET_KEY
from bot.database import db
from webapp.services import get_processed_user_data
from webapp.utils import format_shamsi_tehran, days_until_next_birthday
from bot.hiddify_api_handler import hiddify_handler
from bot.marzban_api_handler import marzban_handler

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- تابع امنیتی برای تمام روت‌های ادمین ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.args.get('key')
        if not provided_key or provided_key != ADMIN_SECRET_KEY:
            abort(403, "Access Forbidden: Invalid or missing admin key.")
        return f(*args, **kwargs)
    return decorated_function

# --- روت اصلی داشبورد ---
@admin_bp.route('/')
@admin_required
def dashboard():
    try:
        all_uuids_dicts = db.get_all_user_uuids()
        uuids_list = [item['uuid'] for item in all_uuids_dicts]
        all_users_data = [get_processed_user_data(uuid) for uuid in uuids_list if get_processed_user_data(uuid)]
        
        now_utc = datetime.now(pytz.utc)
        
        stats = { 'total_users': len(uuids_list), 'online_users': 0, 'total_usage_today': 0, 'new_users_today': 0, 'active_users': 0, 'expiring_soon_count': 0 }
        expiring_soon_users = []

        for user in all_users_data:
            if user.get('is_active'): stats['active_users'] += 1
            expire_days = user.get('expire')
            if expire_days is not None and 0 <= expire_days <= 7:
                stats['expiring_soon_count'] += 1
                expiring_soon_users.append(user)
            if user.get('last_online') and isinstance(user.get('last_online'), datetime) and user['last_online'].astimezone(pytz.utc) >= (now_utc - timedelta(minutes=3)):
                stats['online_users'] += 1
        
        for uuid_dict in all_uuids_dicts:
            created_at = uuid_dict.get('created_at')
            if created_at and isinstance(created_at, datetime) and created_at.astimezone(pytz.utc) >= (now_utc - timedelta(days=1)):
                stats['new_users_today'] += 1
            daily_usage = db.get_usage_since_midnight_by_uuid(uuid_dict['uuid'])
            stats['total_usage_today'] += daily_usage.get('hiddify', 0) + daily_usage.get('marzban', 0)
        
        stats['total_usage_today'] = f"{stats['total_usage_today']:.2f} GB"

        # داده‌های نمونه برای نمودار
        usage_chart_data = {
            "labels": ["۷ روز پیش", "۶ روز پیش", "۵ روز پیش", "۴ روز پیش", "۳ روز پیش", "دیروز", "امروز"],
            "data": [10.5, 12.0, 15.3, 14.2, 18.5, 20.1, stats['total_usage_today'].split(' ')[0]]
        }
        recent_users = sorted(all_users_data, key=lambda u: u.get('created_at') or datetime.min, reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Failed to load admin stats: {e}", exc_info=True)
        stats = { 'total_users': 'خطا', 'online_users': 'خطا', 'total_usage_today': 'خطا', 'new_users_today': 'خطا', 'active_users': 'خطا', 'expiring_soon_count': 'خطا' }
        usage_chart_data, recent_users, expiring_soon_users = {}, [], []
        
    return render_template('admin_dashboard.html', stats=stats, is_admin=True, usage_chart_data=usage_chart_data, recent_users=recent_users, expiring_soon_users=expiring_soon_users)

# --- روت‌های مدیریت کاربران ---
@admin_bp.route('/users')
@admin_required
def user_management_page():
    """صفحه مدیریت کاربران را رندر می‌کند."""
    return render_template('admin_user_management.html', is_admin=True)

# admin_routes.py

@admin_bp.route('/api/users')
@admin_required
def get_users_api_paginated():
    """API برای دریافت کاربران با پشتیبانی از جستجو، فیلتر و صفحه‌بندی سمت سرور (مقاوم در برابر خطا)."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        search_query = request.args.get('search', '', type=str).lower()
        panel_filter = request.args.get('panel', 'all', type=str)

        # تلاش برای اتصال به دیتابیس به صورت جداگانه بررسی می‌شود
        try:
            all_uuids_dicts = db.get_all_user_uuids()
        except Exception as db_error:
            logger.error(f"DATABASE FAILED: Could not retrieve user list from DB. Error: {db_error}", exc_info=True)
            # اگر مشکل از دیتابیس باشد، پیام خطای مشخص‌تری برمی‌گرداند
            return jsonify({"error": "خطا در اتصال به دیتابیس برای دریافت لیست کاربران."}), 500

        all_users_data = []
        for item in all_uuids_dicts:
            try:
                processed_data = get_processed_user_data(item['uuid'])
                if processed_data:
                    all_users_data.append(processed_data)
            except Exception as e:
                logger.warning(f"Could not process data for user UUID {item.get('uuid')}. Skipping user. Error: {e}")
        
        # بقیه کد برای فیلتر و صفحه‌بندی
        filtered_users = [
            user for user in all_users_data if (
                (search_query in (user.get('name') or '').lower() or search_query in (user.get('uuid') or '').lower()) and
                (panel_filter == 'all' or (panel_filter == 'de' and user.get('on_hiddify')) or (panel_filter == 'fr' and user.get('on_marzban')))
            )
        ]
        filtered_users.sort(key=lambda u: (u.get('name') or '').lower())
        
        total_items = len(filtered_users)
        total_pages = (total_items + per_page - 1) // per_page
        start_index = (page - 1) * per_page
        paginated_users = filtered_users[start_index : start_index + per_page]

        return jsonify({
            "users": paginated_users,
            "pagination": {"page": page, "per_page": per_page, "total_items": total_items, "total_pages": total_pages}
        })
        
    except Exception as e:
        logger.error(f"Critical error in get_users_api_paginated: {e}", exc_info=True)
        return jsonify({"error": "یک خطای کلی و ناشناخته در سرور رخ داد."}), 500

@admin_bp.route('/api/users/create', methods=['POST'])
@admin_required
def create_user_api():
    """API برای ساخت کاربر جدید در پنل مشخص شده."""
    data = request.json
    panel = data.get('panel')
    try:
        if panel == 'hiddify':
            result = hiddify_handler.add_user(data)
            if not result or not result.get('uuid'): raise Exception(result.get('detail', 'خطای نامشخص Hiddify'))
        elif panel == 'marzban':
            result = marzban_handler.add_user(data)
            if not result or not result.get('username'): raise Exception(result.get('detail', 'خطای نامشخص Marzban'))
        else:
            return jsonify({'success': False, 'message': 'پنل نامعتبر است.'}), 400
        return jsonify({'success': True, 'message': 'کاربر با موفقیت ساخته شد.'})
    except Exception as e:
        logger.error(f"Failed to create user on panel {panel}: {e}")
        error_message = "کاربری با این نام وجود دارد." if "UNIQUE" in str(e) or "already exists" in str(e) or "422" in str(e) else str(e)
        return jsonify({'success': False, 'message': f'خطا: {error_message}'}), 500

@admin_bp.route('/api/users/update', methods=['POST'])
@admin_required
def update_user_api():
    """
    API نهایی و هوشمند برای ویرایش مستقل کاربر در تمام پنل‌ها.
    """
    data = request.json
    uuid = data.get('uuid')

    if not uuid:
        return jsonify({'success': False, 'message': 'UUID کاربر مشخص نشده است.'}), 400

    try:
        user_info = get_processed_user_data(uuid)
        if not user_info:
            return jsonify({'success': False, 'message': f'کاربر با UUID {uuid} یافت نشد.'}), 404

        success_messages = []
        error_messages = []

        # --- ویرایش در پنل Hiddify (آلمان) ---
        if user_info.get('on_hiddify'):
            hiddify_payload = {
                'name': data.get('common_name'),
                'usage_limit_GB': data.get('h_usage_limit_GB'),
                'package_days': data.get('h_package_days'),
                'mode': data.get('h_mode')
            }
            # فقط فیلدهایی که مقدار دارند و تغییر کرده‌اند ارسال می‌شوند
            final_h_payload = {k: v for k, v in hiddify_payload.items() if v is not None and v != ""}
            if final_h_payload:
                if hiddify_handler.modify_user(uuid, final_h_payload):
                    success_messages.append("✅ پنل آلمان با موفقیت ویرایش شد.")
                else:
                    error_messages.append("❌ ویرایش در پنل آلمان ناموفق بود.")
        
        # --- ویرایش در پنل Marzban (فرانسه) ---
        if user_info.get('on_marzban'):
            marzban_username = user_info.get('breakdown', {}).get('marzban', {}).get('username')
            if not marzban_username:
                error_messages.append("❌ ویرایش در فرانسه ناموفق بود (نام کاربری مرزبان یافت نشد).")
            else:
                marzban_payload = {}
                # داده‌های مختص مرزبان از فرم استخراج و ترجمه می‌شود
                if data.get('m_usage_limit_GB') is not None and data.get('m_usage_limit_GB') != "":
                    marzban_payload['data_limit'] = int(float(data['m_usage_limit_GB']) * (1024**3))
                
                if data.get('m_expire_days') is not None and data.get('m_expire_days') != "":
                    days = int(data['m_expire_days'])
                    # برای محاسبه تاریخ انقضای جدید، از تاریخ انقضای فعلی مرزبان استفاده می‌شود
                    current_expire_ts = user_info.get('breakdown', {}).get('marzban', {}).get('expire_timestamp', 0) or 0
                    base_time = datetime.fromtimestamp(current_expire_ts) if current_expire_ts and datetime.fromtimestamp(current_expire_ts) > datetime.now() else datetime.now()
                    new_expire_dt = base_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
                    marzban_payload['expire'] = int(new_expire_dt.timestamp())

                if marzban_payload:
                    if marzban_handler.modify_user(marzban_username, marzban_payload):
                        success_messages.append("✅ پنل فرانسه با موفقیت ویرایش شد.")
                    else:
                        error_messages.append("❌ ویرایش در پنل فرانسه ناموفق بود.")

        # --- ارائه گزارش نهایی ---
        final_message = "\n".join(success_messages + error_messages)
        if not error_messages:
            return jsonify({'success': True, 'message': final_message or "تغییری برای اعمال وجود نداشت."})
        else:
            status_code = 200 if success_messages else 500
            return jsonify({'success': False, 'message': final_message}), status_code

    except Exception as e:
        logger.error(f"Critical error during multi-panel update for user {uuid}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'یک خطای کلی در سرور رخ داد: {e}'}), 500

@admin_bp.route('/api/users/delete/<string:uuid>', methods=['DELETE'])
@admin_required
def delete_user_api(uuid):
    """API برای حذف کامل کاربر از تمام پنل‌ها و دیتابیس."""
    try:
        user_info = get_processed_user_data(uuid)
        if not user_info:
            return jsonify({'success': False, 'message': 'کاربر یافت نشد.'}), 404
        if user_info.get('on_hiddify'):
            hiddify_handler.delete_user(uuid)
        if user_info.get('on_marzban'):
            username = user_info.get('breakdown', {}).get('marzban', {}).get('username')
            if username: marzban_handler.delete_user(username)
        db.delete_user_by_uuid(uuid)
        return jsonify({'success': True, 'message': 'کاربر با موفقیت حذف شد.'})
    except Exception as e:
        logger.error(f"Failed to delete user {uuid}: {e}")
        return jsonify({'success': False, 'message': f'خطا در حذف: {e}'}), 500

# --- روت‌های مدیریت الگوهای کانفیگ ---
@admin_bp.route('/templates')
@admin_required
def manage_templates_page():
    templates = db.get_all_config_templates()
    return render_template('admin_templates.html', templates=templates, is_admin=True)

@admin_bp.route('/api/templates', methods=['POST'])
@admin_required
def add_templates_api():
    data = request.json
    raw_text = data.get('templates_str')
    if not raw_text:
        return jsonify({'success': False, 'message': 'کادر ورود کانفیگ‌ها نمی‌تواند خالی باشد.'}), 400
    
    VALID_PROTOCOLS = ('vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://')
    config_list = [line.strip() for line in raw_text.splitlines() if line.strip().startswith(VALID_PROTOCOLS)]

    if not config_list:
        return jsonify({'success': False, 'message': 'هیچ کانفیگ معتبری یافت نشد.'}), 400
    
    try:
        added_count = db.add_batch_templates(config_list)
        return jsonify({'success': True, 'message': f"{added_count} کانفیگ جدید اضافه شد."})
    except Exception as e:
        logger.error(f"API Failed to add batch templates: {e}")
        return jsonify({'success': False, 'message': 'خطا در افزودن کانفیگ‌ها به دیتابیس.'}), 500

@admin_bp.route('/api/templates/toggle/<int:template_id>', methods=['POST'])
@admin_required
def toggle_template_api(template_id):
    try:
        db.toggle_template_status(template_id)
        return jsonify({'success': True, 'message': 'وضعیت کانفیگ تغییر کرد.'})
    except Exception as e:
        logger.error(f"API Failed to toggle template {template_id}: {e}")
        return jsonify({'success': False, 'message': 'خطا در تغییر وضعیت.'}), 500

@admin_bp.route('/api/templates/<int:template_id>', methods=['DELETE'])
@admin_required
def delete_template_api(template_id):
    try:
        db.delete_template(template_id)
        return jsonify({'success': True, 'message': 'کانفیگ حذف شد.'})
    except Exception as e:
        logger.error(f"API Failed to delete template {template_id}: {e}")
        return jsonify({'success': False, 'message': 'خطا در حذف کانفیگ.'}), 500


@admin_bp.route('/reports/comprehensive')
@admin_required
def comprehensive_report_page():
    try:
        # بهینه‌سازی: فراخوانی get_processed_user_data فقط یک بار برای هر کاربر
        all_users_data = []
        for item in db.get_all_user_uuids():
            processed_user = get_processed_user_data(item['uuid'])
            if processed_user:
                all_users_data.append(processed_user)

        # تعریف بازه‌های زمانی
        now_utc = datetime.now(pytz.utc)
        online_deadline = now_utc - timedelta(minutes=3)
        active_24h_deadline = now_utc - timedelta(hours=24)
        inactive_1_day_ago = now_utc - timedelta(days=1)
        inactive_7_days_ago = now_utc - timedelta(days=7)

        # آماده‌سازی لیست‌ها و دیکشنری آمار
        summary = { "total_users": len(all_users_data), "active_users": 0, "total_de": 0, "total_fr": 0, "active_de": 0, "active_fr": 0, "usage_de_gb": 0, "usage_fr_gb": 0 }
        online_users_de, online_users_fr = [], []
        active_last_24h, inactive_1_to_7_days, never_connected = [], [], []
        hiddify_users, marzban_users = [], []

        for user in all_users_data:
            is_on_hiddify = user.get('on_hiddify')
            is_on_marzban = user.get('on_marzban')
            
            if is_on_hiddify:
                summary['total_de'] += 1
                hiddify_users.append(user)
            if is_on_marzban:
                summary['total_fr'] += 1
                marzban_users.append(user)
            
            if user.get("is_active"):
                summary['active_users'] += 1
                if is_on_hiddify: summary['active_de'] += 1
                if is_on_marzban: summary['active_fr'] += 1
            
            daily_usage = db.get_usage_since_midnight_by_uuid(user['uuid'])
            summary['usage_de_gb'] += daily_usage.get('hiddify', 0)
            summary['usage_fr_gb'] += daily_usage.get('marzban', 0)

            last_online = user.get('last_online')
            if last_online and isinstance(last_online, datetime):
                last_online_utc = last_online.astimezone(pytz.utc)
                if last_online_utc >= online_deadline:
                    if is_on_hiddify: online_users_de.append(user)
                    if is_on_marzban: online_users_fr.append(user)
                if last_online_utc >= active_24h_deadline:
                    active_last_24h.append(user)
                elif inactive_7_days_ago <= last_online_utc < inactive_1_day_ago:
                    inactive_1_to_7_days.append(user)
            else:
                never_connected.append(user)

        summary['online_users'] = len(online_users_de) + len(online_users_fr)
        summary['total_usage'] = f"{(summary['usage_de_gb'] + summary['usage_fr_gb']):.2f} GB"
        summary['usage_de'] = f"{summary['usage_de_gb']:.2f} GB"
        summary['usage_fr'] = f"{summary['usage_fr_gb'] * 1024:.0f} MB" if summary['usage_fr_gb'] < 1 else f"{summary['usage_fr_gb']:.2f} GB"

        context = {
            "summary": summary,
            "online_users_de": sorted(online_users_de, key=lambda u: u.get('name', '').lower()),
            "online_users_fr": sorted(online_users_fr, key=lambda u: u.get('name', '').lower()),
            "active_last_24h": sorted(active_last_24h, key=lambda u: u.get('name', '').lower()),
            "inactive_1_to_7_days": sorted(inactive_1_to_7_days, key=lambda u: u.get('name', '').lower()),
            "never_connected": sorted(never_connected, key=lambda u: u.get('name', '').lower()),
            "hiddify_users": sorted(hiddify_users, key=lambda u: u.get('name', '').lower()),
            "marzban_users": sorted(marzban_users, key=lambda u: u.get('name', '').lower()),
            "top_consumers": sorted([u for u in all_users_data if u.get('current_usage_GB', 0) > 0], key=lambda u: u.get('current_usage_GB', 0), reverse=True)[:10],
            "payments": db.get_payment_history(),
            "birthdays": db.get_users_with_birthdays(),
            "bot_users": db.get_all_bot_users(),
            "today_shamsi": format_shamsi_tehran(datetime.now()).split(' ')[0]
        }
        
    except Exception as e:
        logger.error(f"Failed to generate comprehensive report: {e}", exc_info=True)
        return render_template('admin_error.html', error_message="خطا در تولید گزارش جامع.", is_admin=True)

    return render_template(
        'admin_comprehensive_report.html',
        report_data=context,
        is_admin=True,
        days_until_next_birthday=days_until_next_birthday
    )