import logging
from telebot import types, telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import jdatetime
from .config import ADMIN_IDS, CUSTOM_SUB_LINK_BASE_URL, EMOJIS, ADMIN_SUPPORT_CONTACT
from .database import db
from . import combined_handler 
from .menu import menu
from .utils import validate_uuid, escape_markdown, load_custom_links, _safe_edit
from .user_formatters import fmt_one, quick_stats, fmt_service_plans, fmt_panel_quick_stats, fmt_user_payment_history, fmt_registered_birthday_info 
from .utils import load_service_plans
import io
import qrcode

logger = logging.getLogger(__name__)
bot = telebot.TeleBot("YOUR_BOT_TOKEN")

def _save_first_uuid(message: types.Message):
    uid, uuid_str = message.from_user.id, message.text.strip().lower()
    if not validate_uuid(uuid_str):
        m = bot.send_message(uid, "❌ `UUID` نامعتبر است. دوباره تلاش کنید", parse_mode="MarkdownV2")
        if m: bot.register_next_step_handler(m, _save_first_uuid)
        return
        
    info = combined_handler.get_combined_user_info(uuid_str)
    if not info:
        m = bot.send_message(uid, "❌ `UUID` در پنل یافت نشد. دوباره تلاش کنید", parse_mode="MarkdownV2")
        if m: bot.register_next_step_handler(m, _save_first_uuid)
        return

    status_message = db.add_uuid(uid, uuid_str, info.get("name", "کاربر ناشناس"))
    
    if "✅" in status_message:
        bot.send_message(uid, escape_markdown(status_message), reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
    else:
        bot.send_message(uid, escape_markdown(status_message), parse_mode="MarkdownV2")
        m = bot.send_message(uid, "لطفاً یک `UUID` دیگر وارد کنید", parse_mode="MarkdownV2")
        if m: bot.register_next_step_handler(m, _save_first_uuid)

def _add_uuid_step(message: types.Message):
    uid, uuid_str = message.from_user.id, message.text.strip().lower()

    if uuid_str.startswith('/'):
        bot.clear_step_handler_by_chat_id(uid)
        bot.send_message(uid, "عملیات افزودن اکانت لغو شد", reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
        return

    if not validate_uuid(uuid_str):
        m = bot.send_message(uid, "❌ `UUID` نامعتبر است. دوباره تلاش کنید یا عملیات را لغو کنید", reply_markup=menu.cancel_action("manage"), parse_mode="MarkdownV2")
        if m: bot.register_next_step_handler(m, _add_uuid_step)
        return

    info = combined_handler.get_combined_user_info(uuid_str)
    if not info:
        m = bot.send_message(uid, "❌ `UUID` در پنل یافت نشد. دوباره تلاش کنید یا عملیات را لغو کنید", reply_markup=menu.cancel_action("manage"), parse_mode="MarkdownV2")
        if m: bot.register_next_step_handler(m, _add_uuid_step)
        return
    
    status_message = db.add_uuid(uid, uuid_str, info.get("name", "کاربر ناشناس"))
    bot.send_message(uid, escape_markdown(status_message), reply_markup=menu.accounts(db.uuids(uid)), parse_mode="MarkdownV2")

def _get_birthday_step(message: types.Message):
    uid = message.from_user.id
    birthday_str = message.text.strip()
    
    try:
        shamsi_date = jdatetime.datetime.strptime(birthday_str, '%Y/%m/%d')
        gregorian_date = shamsi_date.togregorian().date()
        
        db.update_user_birthday(uid, gregorian_date)
        bot.send_message(uid, "✅ تاریخ تولد شما با موفقیت ثبت شد",
                         reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
    except ValueError:
        m = bot.send_message(uid, "❌ فرمت تاریخ نامعتبر است. لطفاً به شکل شمسی `YYYY/MM/DD` وارد کنید (مثلاً `1370/01/15`)", parse_mode="MarkdownV2")
        bot.clear_step_handler_by_chat_id(uid)
        if m: bot.register_next_step_handler(m, _get_birthday_step)


def _handle_add_uuid_request(call: types.CallbackQuery):
    _safe_edit(call.from_user.id, call.message.message_id, "لطفاً UUID جدید را ارسال کنید:", reply_markup=menu.cancel_action("manage"), parse_mode=None)
    bot.register_next_step_handler_by_chat_id(call.from_user.id, _add_uuid_step)

def _show_manage_menu(call: types.CallbackQuery):
    uid = call.from_user.id
    user_uuids_from_db = db.uuids(uid)
    
    user_accounts_details = []
    for row in user_uuids_from_db:
        info = combined_handler.get_combined_user_info(row["uuid"])
        if info:
            info['id'] = row['id']
            user_accounts_details.append(info)
            
    _safe_edit(uid, call.message.message_id, "🔐 *فهرست اکانت‌ها*", reply_markup=menu.accounts(user_accounts_details))

def _show_quick_stats(call: types.CallbackQuery):
    text, menu_data = quick_stats(db.uuids(call.from_user.id), page=0)
    reply_markup = menu.quick_stats_menu(menu_data['num_accounts'], menu_data['current_page'])
    _safe_edit(call.from_user.id, call.message.message_id, text, reply_markup=reply_markup)

def _show_settings(call: types.CallbackQuery):
    settings = db.get_user_settings(call.from_user.id)
    _safe_edit(call.from_user.id, call.message.message_id, "⚙️ *تنظیمات اعلان‌ها*", reply_markup=menu.settings(settings))

def _go_back_to_main(call: types.CallbackQuery):
    _safe_edit(call.from_user.id, call.message.message_id, "🏠 *منوی اصلی*", reply_markup=menu.main(call.from_user.id in ADMIN_IDS))

def _handle_birthday_gift_request(call: types.CallbackQuery):
    uid = call.from_user.id
    user_data = db.user(uid)
    
    if user_data and user_data.get('birthday'):
        text = fmt_registered_birthday_info(user_data)
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back"))
        _safe_edit(uid, call.message.message_id, text, reply_markup=kb, parse_mode="MarkdownV2")
    else:
        prompt = "لطفاً تاریخ تولد خود را به فرمت *شمسی* `YYYY/MM/DD` وارد کنید \\(مثلاً: `1370/01/15`\\)\\.\n\nدر روز تولدتان از ما هدیه بگیرید\\!"
        _safe_edit(uid, call.message.message_id, prompt, reply_markup=menu.cancel_action("back"), parse_mode="MarkdownV2")
        bot.register_next_step_handler_by_chat_id(uid, _get_birthday_step)

def _show_plan_categories(call: types.CallbackQuery):
    prompt = "لطفاً دسته‌بندی سرویس مورد نظر خود را انتخاب کنید:"
    _safe_edit(call.from_user.id, call.message.message_id, prompt, reply_markup=menu.plan_category_menu())

def _show_filtered_plans(call: types.CallbackQuery):
    plan_type = call.data.split(":")[1]
    
    all_plans = load_service_plans()
    filtered_plans = [p for p in all_plans if p.get("type") == plan_type]
    text = fmt_service_plans(filtered_plans, plan_type)
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"{EMOJIS['back']} بازگشت", callback_data="view_plans"))
    _safe_edit(call.from_user.id, call.message.message_id, text, reply_markup=kb)

def _handle_support_request(call: types.CallbackQuery):
    text = (
        f"🙋‍♂️ *راهنمای پشتیبانی*\n\n"
        f"در صورت بروز هرگونه مشکل یا سوال در مورد سرویس خود، می‌توانید مستقیماً با ادمین در ارتباط باشید\\.\n\n"
        f"لطفاً برای تماس، به شناسه‌ی زیر پیام دهید:\n"
        f"👤 *{escape_markdown(ADMIN_SUPPORT_CONTACT)}*"
    )
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back"))
    _safe_edit(call.from_user.id, call.message.message_id, text, reply_markup=kb, parse_mode="MarkdownV2")

USER_CALLBACK_MAP = {
    "add": _handle_add_uuid_request,
    "manage": _show_manage_menu,
    "quick_stats": _show_quick_stats,
    "settings": _show_settings,
    "support": _handle_support_request,
    "back": _go_back_to_main,
    "birthday_gift": _handle_birthday_gift_request,
    "view_plans": _show_plan_categories,
}

def handle_user_callbacks(call: types.CallbackQuery):
    uid, data, msg_id = call.from_user.id, call.data, call.message.message_id

    handler = USER_CALLBACK_MAP.get(data)
    if handler:
        bot.clear_step_handler_by_chat_id(uid)
        handler(call)
        return
    
    if data.startswith("acc_"):
        uuid_id = int(data.split("_")[1])
        row = db.uuid_by_id(uid, uuid_id)
        if row and (info := combined_handler.get_combined_user_info(row["uuid"])):
            daily_usage_data = db.get_usage_since_midnight(uuid_id)
            text = fmt_one(info, daily_usage_data)
            _safe_edit(uid, msg_id, text, reply_markup=menu.account_menu(uuid_id))
            
    elif data.startswith("toggle_"):
        setting_key = data.replace("toggle_", "")
        current_settings = db.get_user_settings(uid)
        db.update_user_setting(uid, setting_key, not current_settings.get(setting_key, True))
        _safe_edit(uid, msg_id, "⚙️ *تنظیمات شما به‌روز شد*", reply_markup=menu.settings(db.get_user_settings(uid)))

    elif data.startswith("getlinks_"):
        uuid_id = int(data.split("_")[1])
        text = (
            "لطفاً نوع لینک اشتراک مورد نظر خود را انتخاب کنید:\n\n"
            "*Normal:* برای اکثر اپلیکیشن‌ها در اندروید و ویندوز مناسب است\\.\n"
            "*Base64:* برای اپلیکیشن‌هایی مانند NapsternetV در iOS مناسب است\\."
        )
        _safe_edit(uid, msg_id, text, reply_markup=menu.get_links_menu(uuid_id))
    
    # تغيير: این بلوک کامل برای پردازش دکمه‌های لینک اضافه شد
    elif data.startswith("getlink_normal_") or data.startswith("getlink_b64_"):
        parts = data.split("_")
        link_type = parts[1]
        uuid_id = int(parts[2])

        row = db.uuid_by_id(uid, uuid_id)
        if not row:
            bot.answer_callback_query(call.id, "❌ خطا: اطلاعات اکانت یافت نشد", show_alert=True)
            return

        user_uuid = row['uuid']
        custom_links = load_custom_links()
        user_links_data = custom_links.get(user_uuid)
        link_key = 'normal' if link_type == 'normal' else 'base64'
        
        if user_links_data and user_links_data.get(link_key):
            link_id = user_links_data[link_key]
            full_sub_link = CUSTOM_SUB_LINK_BASE_URL.rstrip('/') + '/' + link_id.lstrip('/') if not link_id.startswith('http') else link_id
            
            qr_img = qrcode.make(full_sub_link)
            stream = io.BytesIO()
            qr_img.save(stream, 'PNG')
            stream.seek(0)
            
            text = (
                f"🔗 *لینک اشتراک شما ({link_type.capitalize()}) آماده است*\n\n"
                f"۱\\. برای کپی کردن، روی لینک زیر ضربه بزنید:\n"
                f"`{escape_markdown(full_sub_link)}`\n\n"
                f"۲\\. یا کد QR بالا را در اپلیکیشن خود اسکن کنید\\."
            )
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"acc_{uuid_id}"))

            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_photo(uid, photo=stream, caption=text, reply_markup=kb, parse_mode="MarkdownV2")
        else:
            bot.answer_callback_query(call.id, f"❌ لینک نوع {link_type} برای این اکانت تعریف نشده است", show_alert=True)
            
    elif data.startswith("del_"):
        uuid_id = int(data.split("_")[1])
        db.deactivate_uuid(uuid_id)
        _safe_edit(call.from_user.id, call.message.message_id, "🗑 اکانت با موفقیت حذف شد", reply_markup=menu.accounts(db.uuids(call.from_user.id)))

    elif data.startswith("win_hiddify_") or data.startswith("win_marzban_"):
        parts = data.split("_")
        panel_code = parts[1]
        uuid_id = int(parts[2])

        if db.uuid_by_id(uid, uuid_id):
            panel_db_name = f"{panel_code}_usage_gb"
            panel_display_name = "آلمان 🇩🇪" if panel_code == "hiddify" else "فرانسه 🇫🇷"

            stats = db.get_panel_usage_in_intervals(uuid_id, panel_db_name)
            text = fmt_panel_quick_stats(panel_display_name, stats)

            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton(f"{EMOJIS['back']} بازگشت", callback_data=f"win_select_{uuid_id}")
            )
            _safe_edit(uid, msg_id, text, reply_markup=markup)

    elif data.startswith("win_select_"):
        uuid_id = int(data.split("_")[2])
        row = db.uuid_by_id(uid, uuid_id)
        if row:
            info = combined_handler.get_combined_user_info(row['uuid'])
            h_info = info.get('breakdown', {}).get('hiddify', {})
            m_info = info.get('breakdown', {}).get('marzban', {})

            text = "لطفاً سرور مورد نظر خود را برای مشاهده آمار مصرف انتخاب کنید:"
            _safe_edit(uid, msg_id, text, reply_markup=menu.server_selection_menu(uuid_id, show_hiddify=bool(h_info), show_marzban=bool(m_info)), parse_mode=None)
            
    elif data.startswith("qstats_acc_page_"):
        page = int(data.split("_")[3])
        text, menu_data = quick_stats(db.uuids(uid), page=page)
        reply_markup = menu.quick_stats_menu(menu_data['num_accounts'], menu_data['current_page'])
        _safe_edit(uid, msg_id, text, reply_markup=reply_markup)

    elif data.startswith("payment_history_"):
        parts = data.split('_')
        uuid_id, page = int(parts[2]), int(parts[3])
        
        row = db.uuid_by_id(uid, uuid_id)
        if not row:
            bot.answer_callback_query(call.id, "❌ خطا: اطلاعات اکانت یافت نشد", show_alert=True)
            return

        payment_history = db.get_user_payment_history(uuid_id)
        
        text = fmt_user_payment_history(payment_history, row.get('name', 'کاربر ناشناس'), page)

        base_cb = f"payment_history_{uuid_id}"
        back_cb = f"acc_{uuid_id}"
        kb = menu.create_pagination_menu(base_cb, page, len(payment_history), back_cb)
        _safe_edit(uid, msg_id, text, reply_markup=kb)

    if data.startswith("show_plans:"):
        _show_filtered_plans(call)
        return

def register_user_handlers(b: telebot.TeleBot):
    global bot
    bot = b

    @bot.message_handler(commands=["start"])
    def cmd_start(msg: types.Message):
        uid = msg.from_user.id
        log_adapter = logging.LoggerAdapter(logger, {'user_id': uid})
        log_adapter.info("User started the bot.")
        db.add_or_update_user(uid, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
        
        welcome_message = "🏠 *به منوی اصلی خوش آمدید*"

        if db.uuids(uid):
            bot.send_message(uid, welcome_message, reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
        else:
            m = bot.send_message(uid, "👋 *خوش آمدید\\!*\n\nلطفاً `UUID` اکانت خود را ارسال کنید", parse_mode="MarkdownV2")
            if m: bot.register_next_step_handler(m, _save_first_uuid)