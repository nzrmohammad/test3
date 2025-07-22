from flask import Blueprint, render_template, jsonify, request, Response, abort
import requests
import os
from functools import wraps
import logging

from bot.config import ADMIN_SUPPORT_CONTACT, HIDDIFY_DOMAIN, ADMIN_PROXY_PATH
from bot.marzban_api_handler import marzban_handler
from .services import get_processed_user_data
from .utils import load_json_file
from bot.database import db

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_key = os.getenv('ADMIN_WEB_KEY', 'default-secret-key')
        if request.args.get('key') != admin_key:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
    

@main_bp.route('/')
def index():
    support_username = ADMIN_SUPPORT_CONTACT.replace('@', '')
    support_link = f"https://t.me/{support_username}"
    return render_template('index.html', support_link=support_link)


@main_bp.route('/api/user/<string:uuid>')
def get_user_data_api(uuid):
    try:
        logger.info(f"API request for user data: UUID {uuid}")
        user_data = get_processed_user_data(uuid)
        if not user_data:
            return jsonify({"error": "کاربری با این شناسه یافت نشد."}), 404
        return jsonify(user_data)
    except Exception as e:
        logger.error(f"Error in get_user_data_api for UUID {uuid}: {e}", exc_info=True)
        return jsonify({"error": "خطا در پردازش اطلاعات در سرور."}), 500


@main_bp.route('/api/service_plans/<string:plan_type>')
def get_service_plans_api(plan_type):
    try:
        all_plans = load_json_file('plans.json')
        filtered_plans = [p for p in all_plans if p.get("type") == plan_type]
        return jsonify(filtered_plans)
    except Exception as e:
        logger.error(f"Error fetching service plans: {e}")
        return jsonify({"error": "خطا در دریافت لیست سرویس‌ها."}), 500
    

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
    
@main_bp.route('/api/user/<string:uuid>/usage_history')
def get_user_usage_history(uuid):
    """API برای دریافت تاریخچه مصرف کاربر در بازه‌های زمانی مختلف."""
    try:
        logger.info(f"API request for usage history: UUID {uuid}")
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if not uuid_id:
            return jsonify({"labels": [], "hiddify": [], "marzban": []})

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

@main_bp.route('/api/test_json_load')
def test_json_load():
    success = marzban_handler.reload_uuid_maps()
    if success:
        user_count = len(marzban_handler.uuid_to_username_map)
        return jsonify({
            "status": "موفق",
            "message": f"فایل JSON با موفقیت خوانده شد. تعداد {user_count} کاربر پیدا شد."
        })
    else:
        return jsonify({
            "status": "ناموفق",
            "message": "خطا در خواندن فایل JSON. لطفاً لاگ‌های سرویس وب‌اپلیکیشن را بررسی کنید."
        }), 500

@main_bp.route('/admin')
def admin_page():
    return render_template('admin_dashboard.html')

@main_bp.route('/api/admin/users')
def get_all_users_api():
    try:

        all_uuids = db.get_all_user_uuids()
        
        all_users_data = []
        for uuid in all_uuids:
            user_data = get_processed_user_data(uuid)
            if user_data:
                all_users_data.append(user_data)
        
        return jsonify(all_users_data)
    except Exception as e:
        logger.error(f"Error in get_all_users_api: {e}", exc_info=True)
        return jsonify({"error": "خطا در دریافت لیست کاربران."}), 500