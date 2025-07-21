# file: webapp/routes.py
from flask import Blueprint, render_template, jsonify, request, Response, abort
import requests
import os
from functools import wraps
import logging

# وارد کردن ابزارهای مورد نیاز از ربات
from bot.combined_handler import get_combined_user_info
from bot.database import db
from bot.config import ADMIN_SUPPORT_CONTACT, HIDDIFY_DOMAIN, ADMIN_PROXY_PATH
from bot.utils import format_shamsi_tehran, format_daily_usage

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# دکوراتور برای احراز هویت ادمین
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_key = os.getenv('ADMIN_WEB_KEY', 'default-secret-key')
        if request.args.get('key') != admin_key:
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    support_username = ADMIN_SUPPORT_CONTACT.replace('@', '')
    support_link = f"https://t.me/{support_username}"
    return render_template('index.html', support_link=support_link)

@main_bp.route('/api/user/<string:uuid>')
def get_user_data(uuid):
    """API to fetch fully enriched user data, including birthday and payment info."""
    try:
        logger.info(f"API request for enriched user data: UUID {uuid}")
        
        info = get_combined_user_info(uuid)
        if not info:
            return jsonify({"error": "کاربری با این شناسه یافت نشد."}), 404

        processed_info = { 'uuid': info.get('uuid'), 'name': info.get('name'), 'is_active': info.get('is_active'), 'expire': info.get('expire'), 'current_usage_GB': info.get('current_usage_GB', 0), 'usage_limit_GB': info.get('usage_limit_GB', 0), 'usage_percentage': info.get('usage_percentage', 0), 'last_online_shamsi': format_shamsi_tehran(info.get('last_online')), 'daily_usage_GB': info.get('daily_usage_GB', 0) }

        # --- Fetch and add Birthday and Payment info ---
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
        
        # Add server-specific details
        breakdown = info.get('breakdown', {})
        if 'hiddify' in breakdown and breakdown.get('hiddify'): processed_info['hiddify'] = breakdown['hiddify']
        if 'marzban' in breakdown and breakdown.get('marzban'): processed_info['marzban'] = breakdown['marzban']
            
        return jsonify(processed_info)
    except Exception as e:
        logger.error(f"Error in get_user_data for UUID {uuid}: {e}", exc_info=True)
        return jsonify({"error": "خطا در پردازش اطلاعات در سرور."}), 500

@main_bp.route('/api/service_plans/<string:plan_type>')
def get_service_plans(plan_type):
    """A new API to get filtered service plans."""
    try:
        all_plans = load_service_plans()
        # Filter plans based on the requested type (germany, france, combined)
        filtered_plans = [p for p in all_plans if p.get("type") == plan_type]
        return jsonify(filtered_plans)
    except Exception as e:
        logger.error(f"Error fetching service plans: {e}")
        return jsonify({"error": "خطا در دریافت لیست سرویس‌ها."}), 500
@main_bp.route('/api/user/<string:uuid>/usage_history')
def get_user_usage_history(uuid):
    """API برای دریافت تاریخچه مصرف با مدیریت خطای کامل."""
    try:
        logger.info(f"API request for usage history: UUID {uuid}")
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if not uuid_id:
            return jsonify({"error": "شناسه کاربر برای تاریخچه یافت نشد."}), 404

        h_usage = db.get_panel_usage_in_intervals(uuid_id, 'hiddify_usage_gb')
        m_usage = db.get_panel_usage_in_intervals(uuid_id, 'marzban_usage_gb')

        history_data = {
            "labels": ["۲۴ ساعت", "۱۲ ساعت", "۶ ساعت", "۳ ساعت"],
            "hiddify": [h_usage.get(24, 0), h_usage.get(12, 0), h_usage.get(6, 0), h_usage.get(3, 0)],
            "marzban": [m_usage.get(24, 0), m_usage.get(12, 0), m_usage.get(6, 0), m_usage.get(3, 0)]
        }
        return jsonify(history_data)
    except Exception as e:
        logger.error(f"Error in get_user_usage_history for UUID {uuid}: {e}", exc_info=True)
        return jsonify({"error": "خطا در دریافت تاریخچه مصرف."}), 500

@main_bp.route('/sub/<string:uuid>')
def subscription_generator(uuid):
    """لینک اشتراک هوشمند را تولید می‌کند."""
    if not HIDDIFY_DOMAIN:
        logger.error("Hiddify subscription config is not set.")
        return "سرویس اشتراک پیکربندی نشده است.", 500
        
    real_sub_url = f"{HIDDIFY_DOMAIN}/{ADMIN_PROXY_PATH}/{uuid}/"
    try:
        response = requests.get(real_sub_url, timeout=10)
        response.raise_for_status()
        return Response(response.content, mimetype='text/plain; charset=utf-8')
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch subscription for UUID {uuid}: {e}")
        return "خطا در دریافت اطلاعات اشتراک.", 502