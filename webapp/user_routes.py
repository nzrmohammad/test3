from flask import Blueprint, render_template, abort, request, Response, url_for, jsonify
from bot.utils import load_json_file, generate_user_subscription_configs, get_processed_user_data
from bot.config import ADMIN_SUPPORT_CONTACT
from bot.database import db
import qrcode
import io
import base64
import urllib.parse
import re


import logging
logger = logging.getLogger(__name__)
user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/<string:uuid>')
def user_dashboard(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")
    return render_template('user_dashboard.html', user=user_data)


@user_bp.route('/sub/<string:uuid>')
def serve_normal_subscription(uuid):
    configs = generate_user_subscription_configs(uuid)
    if not configs:
        abort(404)
    subscription_content = "\n".join(configs)
    return Response(subscription_content, mimetype='text/plain; charset=utf-8')

@user_bp.route('/sub/b64/<string:uuid>')
def serve_base64_subscription(uuid):
    configs = generate_user_subscription_configs(uuid)
    if not configs:
        abort(404)
    subscription_content = "\n".join(configs)
    encoded_content = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
    return Response(encoded_content, mimetype='text/plain; charset=utf-8')

# --- صفحه اصلی لینک‌ها (با منطق اصلاح‌شده برای پرچم) ---
@user_bp.route('/<string:uuid>/links')
def subscription_links_page(uuid):
    user_data = get_processed_user_data(uuid)
    if not user_data:
        abort(404, "کاربر یافت نشد")

    # لیست کانفیگ‌های خام را از سرویس دریافت کن
    raw_configs = generate_user_subscription_configs(uuid)
    individual_configs = []

    for config_str in raw_configs:
        try:
            # نام کانفیگ را از رشته کامل استخراج کن
            name_part = config_str.split('#', 1)[1]
            config_name = urllib.parse.unquote(name_part, encoding='utf-8')
        except IndexError:
            config_name = "کانفیگ بدون نام"

        # --- بخش جدید: فقط کد کشور را شناسایی کن، جایگزین نکن ---
        detected_code = None
        name_lower = config_name.lower()
        if any(c in name_lower for c in ['(de)', '[de]', 'de ']):
            detected_code = 'de'
        elif any(c in name_lower for c in ['(fr)', '[fr]', 'fr ']):
            detected_code = 'fr'
        # برای کشورهای دیگر می‌توانید به همین شکل elif اضافه کنید

        individual_configs.append({
            "name": config_name,         # نام اصلی و بدون تغییر
            "url": config_str,
            "country_code": detected_code  # کد کشور شناسایی شده (مثلا 'de')
        })

    # ساخت لینک‌های اشتراک کلی
    base_url = request.host_url
    subscription_links = [
        {"type": "همه کانفیگ‌ها (Normal)", "url": url_for('user.serve_normal_subscription', uuid=uuid, _external=True)},
        {"type": "همه کانفیگ‌ها (Base64)", "url": url_for('user.serve_base64_subscription', uuid=uuid, _external=True)}
    ]

    # ساخت QR کد برای همه لینک‌ها
    for link_list in [subscription_links, individual_configs]:
        for link in link_list:
            img = qrcode.make(link['url'])
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            qr_code_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            link['qr_code_data_uri'] = f"data:image/png;base64,{qr_code_b64}"

    return render_template(
        'subscription_links_page.html',
        user=user_data,
        subscription_links=subscription_links,
        individual_configs=individual_configs
    )



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