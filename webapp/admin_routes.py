from flask import Blueprint, render_template, request, abort, jsonify
from functools import wraps
import logging
from bot.config import ADMIN_SECRET_KEY
from bot.database import db

from .services import (
    get_dashboard_data,
    generate_comprehensive_report_data,
    get_paginated_users,
    create_user_in_panel,
    delete_user_from_panels,
    add_templates_from_text,
    update_user_in_panels,
    toggle_template,
    update_template,
    delete_template
)

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- تابع امنیتی ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.args.get('key') != ADMIN_SECRET_KEY:
            abort(403, "Access Forbidden")
        return f(*args, **kwargs)
    return decorated_function

# --- روت‌های اصلی ---
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    try:
        context = get_dashboard_data()
        return render_template('admin_dashboard.html', **context, is_admin=True, admin_key=ADMIN_SECRET_KEY)
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {e}", exc_info=True)
        return "<h1>خطا در بارگذاری داشبورد</h1>", 500

@admin_bp.route('/reports/comprehensive')
@admin_required
def comprehensive_report_page():
    try:
        report_data = generate_comprehensive_report_data()
        return render_template('admin_comprehensive_report.html', report_data=report_data, is_admin=True)
    except Exception as e:
        logger.error(f"Failed to generate comprehensive report: {e}", exc_info=True)
        return render_template('admin_error.html', error_message="خطا در تولید گزارش جامع.", is_admin=True)

# --- بخش مدیریت کاربران ---
@admin_bp.route('/users')
@admin_required
def user_management_page():
    return render_template('admin_user_management.html', is_admin=True)

@admin_bp.route('/api/users')
@admin_required
def get_users_api_paginated():
    try:
        data = get_paginated_users(request.args)
        return jsonify(data)
    except Exception as e:
        logger.error(f"API Error in get_paginated_users: {e}", exc_info=True)
        return jsonify({"error": "خطا در دریافت لیست کاربران."}), 500

@admin_bp.route('/api/users/create', methods=['POST'])
@admin_required
def create_user_api():
    try:
        create_user_in_panel(request.json)
        return jsonify({'success': True, 'message': 'کاربر با موفقیت ساخته شد.'})
    except Exception as e:
        logger.error(f"API Failed to create user: {e}", exc_info=True)
        error_message = "کاربری با این نام وجود دارد." if "UNIQUE" in str(e) or "already exists" in str(e) else str(e)
        return jsonify({'success': False, 'message': f'خطا: {error_message}'}), 500
    
@admin_bp.route('/api/users/update', methods=['POST'])
@admin_required
def update_user_api():
    try:
        update_user_in_panels(request.json)
        return jsonify({'success': True, 'message': 'کاربر با موفقیت به‌روزرسانی شد.'})
    except Exception as e:
        logger.error(f"API Failed to update user: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'خطا در به‌روزرسانی: {e}'}), 500

@admin_bp.route('/api/users/delete/<string:uuid>', methods=['DELETE'])
@admin_required
def delete_user_api(uuid):
    try:
        delete_user_from_panels(uuid)
        return jsonify({'success': True, 'message': 'کاربر با موفقیت حذف شد.'})
    except Exception as e:
        logger.error(f"API Failed to delete user {uuid}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'خطا در حذف: {e}'}), 500

# --- بخش مدیریت قالب‌ها ---
@admin_bp.route('/templates')
@admin_required
def manage_templates_page():
    templates = db.get_all_config_templates()
    return render_template('admin_templates.html', templates=templates, is_admin=True)

@admin_bp.route('/api/templates', methods=['POST'])
@admin_required
def add_templates_api():
    try:
        added_count = add_templates_from_text(request.json.get('templates_str'))
        return jsonify({'success': True, 'message': f"{added_count} کانفیگ جدید اضافه شد."})
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"API Failed to add batch templates: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطا در افزودن کانفیگ‌ها.'}), 500

@admin_bp.route('/api/templates/toggle/<int:template_id>', methods=['POST'])
@admin_required
def toggle_template_api(template_id):
    try:
        toggle_template(template_id)
        return jsonify({'success': True, 'message': 'وضعیت کانفیگ تغییر کرد.'})
    except Exception as e:
        logger.error(f"API Failed to toggle template {template_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطا در تغییر وضعیت.'}), 500

# ✅ روت جدید برای ویرایش
@admin_bp.route('/api/templates/update/<int:template_id>', methods=['POST'])
@admin_required
def update_template_api(template_id):
    try:
        data = request.get_json()
        if not data or 'template_str' not in data:
            return jsonify({'success': False, 'message': 'اطلاعات ارسالی ناقص است.'}), 400
        
        update_template(template_id, data['template_str'])
        return jsonify({'success': True, 'message': 'کانفیگ با موفقیت به‌روزرسانی شد.'})
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"API Failed to update template {template_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'خطا در به‌روزرسانی: {e}'}), 500

@admin_bp.route('/api/templates/<int:template_id>', methods=['DELETE'])
@admin_required
def delete_template_api(template_id):
    try:
        delete_template(template_id)
        return jsonify({'success': True, 'message': 'کانفیگ حذف شد.'})
    except Exception as e:
        logger.error(f"API Failed to delete template {template_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'خطا در حذف کانفیگ.'}), 500