import logging
from .config import EMOJIS, PAGE_SIZE
from .database import db
from . import combined_handler
from datetime import datetime
from .utils import (
    create_progress_bar,
    format_daily_usage, escape_markdown,
    load_service_plans, format_raw_datetime, format_shamsi_tehran, gregorian_to_shamsi_str, days_until_next_birthday
)

logger = logging.getLogger(__name__)

def fmt_one(info: dict, daily_usage_dict: dict) -> str:
    if not info: return "❌ خطا در دریافت اطلاعات"
    
    name = escape_markdown(info.get("name", "کاربر ناشناس"))
    status_emoji = "🟢" if info.get("is_active") else "🔴"
    status_text = "فعال" if info.get("is_active") else "غیرفعال"
    
    name_line = f"👤 *نام :* {name} \\({status_emoji} {status_text}\\)"

    h_info = info.get('breakdown', {}).get('hiddify', {})
    m_info = info.get('breakdown', {}).get('marzban', {})

    expire_days = info.get("expire")
    expire_label = "نامحدود"
    if expire_days is not None: expire_label = f"{expire_days} روز"
    escaped_expire_label = escape_markdown(expire_label)
    uuid = escape_markdown(info.get('uuid', ''))
    
    usage_percentage = info.get("usage_percentage", 0)
    bar = create_progress_bar(usage_percentage) 

    report = [name_line]

    # نمایش اطلاعات مجموع فقط اگر کاربر در هر دو پنل باشد
    if h_info and m_info:
        total_limit_gb = escape_markdown(f"{info.get('usage_limit_GB', 0):.2f} GB")
        total_usage_gb = escape_markdown(f"{info.get('current_usage_GB', 0):.2f} GB")
        total_remaining_gb = escape_markdown(f"{info.get('remaining_GB', 0):.2f} GB")
        total_daily_gb_str = escape_markdown(format_daily_usage(sum(daily_usage_dict.values())))
        report.extend([
            "",
            f"📦 *مجموع حجم :* `{total_limit_gb}`",
            f"🔥 *مجموع مصرف شده :* `{total_usage_gb}`",
            f"📥 *مجموع باقیمانده:* `{total_remaining_gb}`",
            f"⚡️ *مجموع مصرف امروز:* `{total_daily_gb_str}`" # این خط حالا شرطی است
        ])

    # نمایش جزئیات سرورها
    if h_info or m_info:
        report.append("\n*جزئیات سرورها*")
    if h_info:
        h_limit_str = escape_markdown(f"{h_info.get('usage_limit_GB', 0.0):.2f} GB")
        h_usage_str = escape_markdown(f"{h_info.get('current_usage_GB', 0.0):.2f} GB")
        h_daily_str = escape_markdown(format_daily_usage(daily_usage_dict.get('hiddify', 0.0)))
        h_last_online = escape_markdown(format_shamsi_tehran(h_info.get('last_online')))
        report.extend([
            "",
            "آلمان 🇩🇪",
            f"🗂️ *مجموع حجم :* `{h_limit_str}`",
            f"🔥 *مجموع مصرف شده :* `{h_usage_str}`",
            f"⚡️ *مصرف امروز :* `{h_daily_str}`",
            f"⏰ *آخرین اتصال :* `{h_last_online}`"
        ])
    if m_info:
        m_limit_str = escape_markdown(f"{m_info.get('usage_limit_GB', 0.0):.2f} GB")
        m_usage_str = escape_markdown(f"{m_info.get('current_usage_GB', 0.0):.2f} GB")
        m_daily_str = escape_markdown(format_daily_usage(daily_usage_dict.get('marzban', 0.0)))
        m_last_online = escape_markdown(format_shamsi_tehran(m_info.get('last_online')))
        report.extend([
            "",
            "فرانسه 🇫🇷",
            f"🗂️ *مجموع حجم :* `{m_limit_str}`",
            f"🔥 *مجموع مصرف شده :* `{m_usage_str}`",
            f"⚡️ *مصرف امروز :* `{m_daily_str}`",
            f"⏰ *آخرین اتصال :* `{m_last_online}`"
        ])

    report.extend([
        "",
        f"📅 *انقضا:* `{escaped_expire_label}`",
        f"🔑 *شناسه یکتا:* `{uuid}`",
        "",
        f"*وضعیت :* {bar}"
    ])
    
    return "\n".join(report)


def quick_stats(uuid_rows: list, page: int = 0) -> tuple[str, dict]:
    num_uuids = len(uuid_rows)
    menu_data = {"num_accounts": num_uuids, "current_page": 0}
    if not num_uuids: return "هیچ اکانتی ثبت نشده است", menu_data

    current_page = max(0, min(page, num_uuids - 1))
    menu_data["current_page"] = current_page
    
    target_row = uuid_rows[current_page]
    info = combined_handler.get_combined_user_info(target_row['uuid'])
    
    if not info: return f"❌ خطا در دریافت اطلاعات برای اکانت در صفحه {current_page + 1}", menu_data

    # --- Data Preparation ---
    name = escape_markdown(info.get("name", "کاربر ناشناس"))
    status_emoji = "🟢" if info.get("is_active") else "🔴"
    status_text = "فعال" if info.get("is_active") else "غیرفعال"
    
    name_line = f"👤 *نام :* {name} \\({status_emoji} {status_text}\\)"

    h_info = info.get('breakdown', {}).get('hiddify', {})
    m_info = info.get('breakdown', {}).get('marzban', {})
    daily_usage_dict = db.get_usage_since_midnight(target_row['id'])

    # --- Report Generation ---
    report = [name_line]

    # Display combined stats only if the user is in both panels
    if h_info and m_info:
        total_limit_gb = escape_markdown(f"{info.get('usage_limit_GB', 0):.2f} GB")
        total_usage_gb = escape_markdown(f"{info.get('current_usage_GB', 0):.2f} GB")
        total_remaining_gb = escape_markdown(f"{info.get('remaining_GB', 0):.2f} GB")
        total_daily_gb_str = escape_markdown(format_daily_usage(sum(daily_usage_dict.values())))
        report.extend([
            "",
            f"📦 *مجموع حجم :* `{total_limit_gb}`",
            f"🔥 *مجموع مصرف شده :* `{total_usage_gb}`",
            f"📥 *مجموع باقیمانده:* `{total_remaining_gb}`",
            f"⚡️ *مجموع مصرف امروز:* `{total_daily_gb_str}`"
        ])

    # Display server details
    if h_info or m_info:
        report.append("\n*جزئیات سرورها*")
        
    if h_info:
        h_limit_str = escape_markdown(f"{h_info.get('usage_limit_GB', 0.0):.2f} GB")
        h_usage_str = escape_markdown(f"{h_info.get('current_usage_GB', 0.0):.2f} GB")
        h_daily_str = escape_markdown(format_daily_usage(daily_usage_dict.get('hiddify', 0.0)))
        h_last_online = escape_markdown(format_shamsi_tehran(h_info.get('last_online')))
        report.extend([
            "",
            "آلمان 🇩🇪",
            f"🗂️ *مجموع حجم :* `{h_limit_str}`",
            f"🔥 *مجموع مصرف شده :* `{h_usage_str}`",
            f"⚡️ *مصرف امروز :* `{h_daily_str}`",
            f"⏰ *آخرین اتصال :* `{h_last_online}`"
        ])
        
    if m_info:
        m_limit_str = escape_markdown(f"{m_info.get('usage_limit_GB', 0.0):.2f} GB")
        m_usage_str = escape_markdown(f"{m_info.get('current_usage_GB', 0.0):.2f} GB")
        m_daily_str = escape_markdown(format_daily_usage(daily_usage_dict.get('marzban', 0.0)))
        m_last_online = escape_markdown(format_shamsi_tehran(m_info.get('last_online')))
        report.extend([
            "",
            "فرانسه 🇫🇷",
            f"🗂️ *مجموع حجم :* `{m_limit_str}`",
            f"🔥 *مجموع مصرف شده :* `{m_usage_str}`",
            f"⚡️ *مصرف امروز :* `{m_daily_str}`",
            f"⏰ *آخرین اتصال :* `{m_last_online}`"
        ])

    return "\n".join(report), menu_data

def fmt_user_report(user_infos: list) -> str:
    logger.info(f"USER_FORMATTER: fmt_user_report called to format a report for {len(user_infos)} account(s).")
    if not user_infos:
        logger.warning("USER_FORMATTER: No active accounts found for user to generate a report.")
        return ""

    accounts_reports = []
    total_daily_usage_all_accounts = 0.0

    for info in user_infos:
        name = escape_markdown(info.get("name", "کاربر ناشناس"))
        account_lines = [f"👤 *اکانت : {name}*"]
        
        daily_usage_dict = db.get_usage_since_midnight(info['db_id'])
        total_daily_usage_all_accounts += sum(daily_usage_dict.values())
        
        h_info = info.get('breakdown', {}).get('hiddify', {})
        m_info = info.get('breakdown', {}).get('marzban', {})

        # Display combined stats only if user is on both panels
        if h_info and m_info:
            account_lines.append(f"      📊 حجم‌کل : {escape_markdown(f'{info.get("usage_limit_GB", 0):.2f} GB')}")
            account_lines.append(f"      🔥 حجم‌مصرف شده : {escape_markdown(f'{info.get("current_usage_GB", 0):.2f} GB')}")
            account_lines.append(f"      📥 حجم‌باقی‌مانده : {escape_markdown(f'{info.get("remaining_GB", 0):.2f} GB')}")
        # Display individual stats if user is on one panel
        else:
            panel_info = h_info or m_info
            account_lines.append(f"      📊 حجم‌کل : {escape_markdown(f'{panel_info.get("usage_limit_GB", 0):.2f} GB')}")
            account_lines.append(f"      🔥 حجم‌مصرف‌شده : {escape_markdown(f'{panel_info.get("current_usage_GB", 0):.2f} GB')}")
            account_lines.append(f"      📥 حجم‌باقی‌مانده : {escape_markdown(f'{max(0, panel_info.get("usage_limit_GB", 0) - panel_info.get("current_usage_GB", 0)):.2f} GB')}")

        if h_info:
            account_lines.append(f" 🇩🇪 : {escape_markdown(format_daily_usage(daily_usage_dict.get('hiddify', 0.0)))}")
        if m_info:
            account_lines.append(f" 🇫🇷 : {escape_markdown(format_daily_usage(daily_usage_dict.get('marzban', 0.0)))}")

        expire_days = info.get("expire")
        expire_str = "`نامحدود`"
        if expire_days is not None:
            expire_str = f"{expire_days} روز" if expire_days >= 0 else "منقضی شده"
        account_lines.append(f"      📅 انقضا : {expire_str}")
        accounts_reports.append("\n".join(account_lines))
    final_report = "\n\n".join(accounts_reports)

    footer_text = ""
    if len(user_infos) > 1:
        footer_text = f"⚡️ *مجموع مصرف امروز اکانت ها : * {escape_markdown(format_daily_usage(total_daily_usage_all_accounts))}"
    else:
        footer_text = f"⚡️ *مجموع کل مصرف امروز : * {escape_markdown(format_daily_usage(total_daily_usage_all_accounts))}"

    if footer_text:
        final_report += f"\n\n {footer_text}"

    return final_report

def fmt_service_plans(plans_to_show: list, plan_type: str) -> str:
    if not plans_to_show:
        return "در حال حاضر پلن فعالی برای نمایش در این دسته وجود ندارد"
    
    type_map = {
        "combined": "ترکیبی",
        "germany": "آلمان",
        "france": "فرانسه"
    }
    type_title = type_map.get(plan_type, "عمومی")
    
    title_content = f"{EMOJIS['rocket']} پلن‌های فروش سرویس ({type_title})"
    title_text = f"*{escape_markdown(title_content)}*"
    lines = [title_text]
    
    for plan in plans_to_show:
        lines.append("`────────────────────`")
        lines.append(f"*{escape_markdown(plan.get('name'))}*")
        
        if plan.get('total_volume'):
            lines.append(f"حجم کل: *{escape_markdown(plan['total_volume'])}*")
        
        # تغيير: نمایش شرطی حجم بر اساس نوع پلن
        # حالا به درستی لیبل و مقدار مربوط به هر کشور را نمایش می‌دهد
        if plan_type == 'germany' and plan.get('volume_de'):
             lines.append(f"حجم: *{escape_markdown(plan['volume_de'])}*")
        elif plan_type == 'france' and plan.get('volume_fr'):
            lines.append(f"حجم: *{escape_markdown(plan['volume_fr'])}*")
        elif plan_type == 'combined':
            if plan.get('volume_de'):
                lines.append(f"آلمان: *{escape_markdown(plan['volume_de'])}*")
            if plan.get('volume_fr'):
                lines.append(f"فرانسه: *{escape_markdown(plan['volume_fr'])}*")
            
        lines.append(f"مدت زمان: *{escape_markdown(plan['duration'])}*")
                
    lines.append("`────────────────────`")
    if plan_type == "combined":
        lines.append(escape_markdown("نکته: حجم 🇫🇷 قابل تبدیل به 🇩🇪 هست ولی 🇩🇪 قابل تبدیل به 🇫🇷 نیست"))
    
    lines.append(escape_markdown("برای اطلاع از قیمت‌ها و دریافت مشاوره، لطفاً به ادمین پیام دهید"))
    
    return "\n".join(lines)

def fmt_panel_quick_stats(panel_name: str, stats: dict) -> str:    
    title = f"*{escape_markdown(f'📊 آمار مصرف سرور {panel_name}')}*"
    
    lines = [title, ""]
    if not stats:
        lines.append("اطلاعاتی برای نمایش وجود ندارد")
        return "\n".join(lines)
        
    for hours, usage_gb in stats.items():
        usage_str = format_daily_usage(usage_gb)
        lines.append(f"`• {hours}` ساعت گذشته: `{escape_markdown(usage_str)}`")
        
    lines.append("\n*نکته:* این آمار تجمعی است\\. برای مثال، مصرف ۶ ساعت گذشته شامل مصرف ۳ ساعت اخیر نیز می‌باشد\\.")
        
    return "\n".join(lines)

def fmt_user_payment_history(payments: list, user_name: str, page: int) -> str:
    escaped_user_name = escape_markdown(user_name)
    
    total_payments = len(payments)
    title_action = "خرید" if total_payments == 1 else "پرداخت‌های"
    title = f"💳 *سابقه {title_action} اکانت {escaped_user_name}*"
    
    if not payments:
        return f"*{escape_markdown(f'سابقه پرداخت‌های اکانت {user_name}')}*\n\nهیچ سابقه پرداختی برای این اکانت ثبت نشده است"

    header_text = title
    if total_payments > PAGE_SIZE:
        total_pages = (total_payments + PAGE_SIZE - 1) // PAGE_SIZE
        pagination_text = f"(صفحه {page + 1} از {total_pages})"
        header_text += f"\n{escape_markdown(pagination_text)}"

    lines = [header_text]
    paginated_payments = payments[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    for i, payment in enumerate(paginated_payments):
        payment_number = total_payments - (page * PAGE_SIZE + i)
        label = "تاریخ خرید" if payment_number == 1 else "تاریخ تمدید"
        shamsi_datetime = format_shamsi_tehran(payment.get('payment_date'))
        lines.append(f"`•` {label}: `{shamsi_datetime}`")

    return "\n".join(lines)

def fmt_registered_birthday_info(user_data: dict) -> str:

    if not user_data or not user_data.get('birthday'):
        return "خطایی در دریافت اطلاعات تولد رخ داد."

    birthday_obj = user_data['birthday']
    shamsi_date_str = gregorian_to_shamsi_str(birthday_obj)
    remaining_days = days_until_next_birthday(birthday_obj)

    header = "🎁 *وضعیت هدیه تولد شما*"
    
    lines = [header, "`────────────────────`"]
    
    lines.append(f"تاریخ ثبت شده: *{escape_markdown(shamsi_date_str)}*")

    if remaining_days is not None:
        if remaining_days == 0:
            lines.append("شمارش معکوس: *امروز تولد شماست\\!* 🎉")
            lines.append("\nهدیه شما به صورت خودکار به اکانتتان اضافه شده است\\.")
        else:
            lines.append(f"شمارش معکوس: *{remaining_days} روز* تا تولد بعدی شما باقی مانده است\\.")
    
    lines.append("`────────────────────`")
    lines.append("⚠️ *نکته:* تاریخ تولد ثبت شده قابل ویرایش نیست\\. در صورت ورود اشتباه، لطفاً به ادمین اطلاع دهید\\.")

    return "\n".join(lines)