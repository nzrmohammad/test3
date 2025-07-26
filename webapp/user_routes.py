from flask import Blueprint, render_template, abort, request, Response, url_for
from bot.utils import load_json_file, generate_user_subscription_configs
from bot.config import ADMIN_SUPPORT_CONTACT
from bot.database import db
from .user_service import user_service
import base64
import urllib.parse
import logging

logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__, url_prefix='/user')

# این بخش به صورت خودکار UUID را به تمام تمپلیت‌ها اضافه می‌کند
# و مشکل لینک‌های خالی را برای همیشه حل می‌کند.
@user_bp.context_processor
def inject_uuid_for_user_pages():
    uuid = request.view_args.get('uuid')
    if uuid:
        return dict(uuid=uuid)
    return {}

# ✅ اصلاح شده: <string:uuid> به تمام آدرس‌ها اضافه شد
@user_bp.route('/<string:uuid>')
def user_dashboard(uuid):
    user_data = user_service.get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('user_dashboard.html', user=user_data)

@user_bp.route('/sub/<string:uuid>')
def serve_normal_subscription(uuid):
    configs = generate_user_subscription_configs(uuid)
    if not configs:
        abort(404, "کانفیگ یافت نشد")
    subscription_content = "\n".join(configs)
    return Response(subscription_content, mimetype='text/plain; charset=utf-8')

@user_bp.route('/sub/b64/<string:uuid>')
def serve_base64_subscription(uuid):
    configs = generate_user_subscription_configs(uuid)
    if not configs:
        abort(404, "کانفیگ یافت نشد")
    subscription_content = "\n".join(configs)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
    return Response(encoded_content, mimetype='text/plain; charset=utf-8')

@user_bp.route('/<string:uuid>/links')
def subscription_links_page(uuid):
    raw_configs = generate_user_subscription_configs(uuid)
    individual_configs = []
    
    if raw_configs:
        for config_str in raw_configs:
            try:
                name_part = config_str.split('#', 1)[1]
                config_name = urllib.parse.unquote(name_part, encoding='utf-8')
            except IndexError:
                config_name = "کانفیگ بدون نام"
            
            detected_code = None
            name_lower = config_name.lower()
            if any(c in name_lower for c in ['(de)', '[de]', 'de ']): detected_code = 'de'
            elif any(c in name_lower for c in ['(fr)', '[fr]', 'fr ']): detected_code = 'fr'
            
            individual_configs.append({"name": config_name, "url": config_str, "country_code": detected_code})

    subscription_links = [
        {"type": "همه کانفیگ‌ها (Normal)", "url": url_for('user.serve_normal_subscription', uuid=uuid, _external=True)},
        {"type": "همه کانفیگ‌ها (Base64)", "url": url_for('user.serve_base64_subscription', uuid=uuid, _external=True)}
    ]
    
    user_data = {"username": "کاربر"}
    return render_template('subscription_links_page.html', user=user_data, subscription_links=subscription_links, individual_configs=individual_configs)

@user_bp.route('/<string:uuid>/usage')
def usage_chart_page(uuid):
    user_data = user_service.get_processed_user_data(uuid)
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
                "series": [{"name": "Hiddify (GB)", "data": h_data}, {"name": "Marzban (GB)", "data": m_data}],
                "categories": ["در ۲۴ ساعت گذشته", "در ۱۲ ساعت گذشته", "در ۶ ساعت گذشته", "در ۳ ساعت گذشته"]
            }
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های نمودار: {e}")
    
    return render_template('usage_chart_page.html', user=user_data, usage_data=chart_data)

@user_bp.route('/<string:uuid>/buy')
def buy_service_page(uuid):
    all_plans = load_json_file('plans.json')
    support_link = f"https://t.me/{ADMIN_SUPPORT_CONTACT.replace('@', '')}"
    
    combined_plans, dedicated_plans = [], []
    if isinstance(all_plans, list):
        for plan in all_plans:
            if plan.get('type') == 'combined': combined_plans.append(plan)
            else: dedicated_plans.append(plan)
    
    user_data = {"username": "کاربر"}
    return render_template('buy_service_page.html', user=user_data, combined_plans=combined_plans, dedicated_plans=dedicated_plans, support_link=support_link)

@user_bp.route('/<string:uuid>/tutorials')
def tutorials_page(uuid):
    user_data = user_service.get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    
    return render_template('tutorials_page.html', user=user_data)
