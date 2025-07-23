from flask import Blueprint, render_template, jsonify, request, Response, abort, redirect, url_for
import requests
import os
from functools import wraps
import logging

from bot.config import ADMIN_SUPPORT_CONTACT, HIDDIFY_DOMAIN, ADMIN_PROXY_PATH
from .services import get_processed_user_data
from .utils import load_json_file
from bot.database import db

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# --- روت‌های نمایش صفحات ---

@main_bp.route('/')
def index():
    # به صورت پیش‌فرض به صفحه ادمین هدایت می‌شود
    return redirect(url_for('main.admin_page'))

@main_bp.route('/user/<string:uuid>')
def user_dashboard(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('user_dashboard.html', user=user_data)

# --- (جدید) روت صفحه لینک‌های اتصال ---
@main_bp.route('/user/<string:uuid>/links')
def subscription_links_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('subscription_links_page.html', user=user_data)

@main_bp.route('/user/<string:uuid>/usage')
def usage_chart_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('usage_chart_page.html', user=user_data)

@main_bp.route('/user/<string:uuid>/buy')
def buy_service_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    
    all_plans = load_json_file('plans.json')
    support_link = f"https://t.me/{ADMIN_SUPPORT_CONTACT.replace('@', '')}"
    return render_template('buy_service_page.html', user=user_data, plans=all_plans or [], support_link=support_link)

# --- (جدید) روت صفحه آموزش ---
@main_bp.route('/user/<string:uuid>/tutorials')
def tutorials_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('tutorials_page.html', user=user_data)


@main_bp.route('/admin')
def admin_page():
    stats = {
        'total_users': len(db.get_all_user_uuids()),
        'online_users': 'N/A', 'total_usage_today': 'N/A', 'new_users_today': 'N/A'
    }
    return render_template('admin_dashboard.html', stats=stats)


# --- API & Subscription Routes ---
# (این بخش‌ها بدون تغییر باقی می‌مانند)

@main_bp.route('/sub/<string:uuid>')
def subscription_generator(uuid):
    if not HIDDIFY_DOMAIN:
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
def get_user_usage_history_api(uuid):
    try:
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
        logger.error(f"Error in get_user_usage_history_api for UUID {uuid}: {e}", exc_info=True)
        return jsonify({"error": "خطا در دریافت تاریخچه مصرف."}), 500