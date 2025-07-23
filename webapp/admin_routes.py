# file: webapp/blueprints/admin_routes.py

from flask import Blueprint, render_template, request, abort, jsonify
from functools import wraps
import logging

# وارد کردن متغیرها و ابزارهای لازم
from bot.config import ADMIN_SECRET_KEY
from bot.database import db
from webapp.services import get_processed_user_data

logger = logging.getLogger(__name__)

# ساخت بلوپرینت جدید برای ادمین با پیشوند /admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- تابع امنیتی ---
def admin_required():
    provided_key = request.args.get('key')
    if not provided_key or provided_key != ADMIN_SECRET_KEY:
        abort(403, "Access Forbidden: Invalid or missing admin key.")
admin_bp.before_request(admin_required)


# --- روت‌های اصلی داشبورد ---
@admin_bp.route('/')
def dashboard():
    try:
        all_uuids = db.get_all_user_uuids() if hasattr(db, 'get_all_user_uuids') else db.all_active_uuids()
        stats = {
            'total_users': len(all_uuids),
            'online_users': 'N/A',
            'total_usage_today': 'N/A',
            'new_users_today': 'N/A'
        }
    except Exception as e:
        logger.error(f"Failed to load admin stats: {e}")
        stats = { 'total_users': 'خطا' }
    return render_template('admin_dashboard.html', stats=stats, is_admin=True)

@admin_bp.route('/api/users')
def get_all_users_api():
    try:
        all_uuids_dicts = db.get_all_user_uuids() if hasattr(db, 'get_all_user_uuids') else db.all_active_uuids()
        uuids_list = [item['uuid'] for item in all_uuids_dicts]
        all_users_data = [get_processed_user_data(uuid) for uuid in uuids_list if get_processed_user_data(uuid)]
        return jsonify(all_users_data)
    except Exception as e:
        logger.error(f"Error fetching all users for admin: {e}", exc_info=True)
        return jsonify({"error": "خطا در دریافت لیست کاربران"}), 500


# --- روت‌های مدیریت الگوهای کانفیگ ---
@admin_bp.route('/templates')
def manage_templates_page():
    templates = db.get_all_config_templates()
    return render_template('admin_templates.html', templates=templates, is_admin=True)

@admin_bp.route('/api/templates', methods=['POST'])
def add_templates_api():
    """API برای افزودن دسته‌ای الگوهای جدید با فیلتر هوشمند."""
    data = request.json
    raw_text = data.get('templates_str')

    if not raw_text:
        return jsonify({'success': False, 'message': 'کادر ورود کانفیگ‌ها نمی‌تواند خالی باشد.'}), 400
    
    # پروتکل‌های معتبر کانفیگ را تعریف می‌کنیم
    VALID_PROTOCOLS = ('vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://')
    
    # 1. رشته ورودی را بر اساس خطوط جدید جدا کن
    # 2. موارد خالی را حذف کن
    # 3. فقط خطوطی را نگه دار که با یکی از پروتکل‌های معتبر شروع می‌شوند
    config_list = [
        line.strip() for line in raw_text.splitlines() 
        if line.strip().startswith(VALID_PROTOCOLS)
    ]

    if not config_list:
        return jsonify({'success': False, 'message': 'هیچ کانفیگ معتبری (مانند vless://, vmess:// و...) در متن ورودی یافت نشد.'}), 400
    
    try:
        added_count = db.add_batch_templates(config_list)
        message = f"{added_count} کانفیگ جدید با موفقیت به سیستم اضافه شد."
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"API Failed to add batch templates: {e}")
        return jsonify({'success': False, 'message': 'خطا در پردازش و افزودن کانفیگ‌ها به دیتابیس.'}), 500

@admin_bp.route('/api/templates/toggle/<int:template_id>', methods=['POST'])
def toggle_template_api(template_id):
    try:
        db.toggle_template_status(template_id)
        return jsonify({'success': True, 'message': 'وضعیت کانفیگ با موفقیت تغییر کرد.'})
    except Exception as e:
        logger.error(f"API Failed to toggle template {template_id}: {e}")
        return jsonify({'success': False, 'message': 'خطا در تغییر وضعیت کانفیگ.'}), 500

@admin_bp.route('/api/templates/<int:template_id>', methods=['DELETE'])
def delete_template_api(template_id):
    try:
        db.delete_template(template_id)
        return jsonify({'success': True, 'message': 'کانفیگ با موفقیت حذف شد.'})
    except Exception as e:
        logger.error(f"API Failed to delete template {template_id}: {e}")
        return jsonify({'success': False, 'message': 'خطا در حذف کانفیگ.'}), 500