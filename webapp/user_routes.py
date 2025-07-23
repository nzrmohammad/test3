from flask import Blueprint, render_template, abort
from webapp.services import get_processed_user_data
from .utils import load_json_file
from bot.config import ADMIN_SUPPORT_CONTACT
from bot.database import db

import logging
logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/<string:uuid>')
def user_dashboard(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('user_dashboard.html', user=user_data)


@user_bp.route('/<string:uuid>/links')
def subscription_links_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('subscription_links_page.html', user=user_data)


@user_bp.route('/user/<string:uuid>/usage')
def usage_chart_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")

    chart_data = {"series": [], "categories": []}
    try:
        uuid_id = db.get_uuid_id_by_uuid(uuid)
        if uuid_id:
            h_usage = db.get_panel_usage_in_intervals(uuid_id, 'hiddify_usage_gb')
            m_usage = db.get_panel_usage_in_intervals(uuid_id, 'marzban_usage_gb')
            
            h_data = [float(h_usage.get(h, 0)) for h in [24, 12, 6, 3]]
            m_data = [float(m_usage.get(h, 0)) for h in [24, 12, 6, 3]]
            
            chart_data = {
                "series": [
                    {"name": "Hiddify (GB)", "data": h_data},
                    {"name": "Marzban (GB)", "data": m_data}
                ],
                "categories": ["در ۲۴ ساعت گذشته", "در ۱۲ ساعت گذشته", "در ۶ ساعت گذشته", "در ۳ ساعت گذشته"]
            }
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های نمودار: {e}")

    return render_template('usage_chart_page.html', user=user_data, usage_data=chart_data)


@user_bp.route('/user/<string:uuid>/buy')
def buy_service_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    
    all_plans = load_json_file('plans.json')
    support_link = f"https://t.me/{ADMIN_SUPPORT_CONTACT.replace('@', '')}"

    combined_plans = []
    dedicated_plans = []
    if isinstance(all_plans, list):
        for plan in all_plans:
            if plan.get('type') == 'combined':
                combined_plans.append(plan)
            else:
                dedicated_plans.append(plan)

    return render_template(
        'buy_service_page.html', 
        user=user_data, 
        combined_plans=combined_plans, 
        dedicated_plans=dedicated_plans, 
        support_link=support_link
    )


@user_bp.route('/user/<string:uuid>/tutorials')
def tutorials_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('tutorials_page.html', user=user_data)