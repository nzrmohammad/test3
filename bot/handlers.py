# handlers.py

import logging
from telebot import types, apihelper, telebot

from config import BOT_TOKEN, ADMIN_IDS, SUBSCRIPTION_LINKS, EMOJIS
from database import db
from api_handler import api_handler
from menu import menu
from utils import validate_uuid, escape_markdown
from formatters import (
    fmt_one, fmt_users_list, quick_stats, fmt_panel_info, 
    fmt_top_consumers, fmt_online_users_list
)

logger = logging.getLogger(__name__)

# حذف parse_mode پیش‌فرض برای جلوگیری از خطا
bot = telebot.TeleBot(BOT_TOKEN)

admin_conversations = {}

# ──────────────────────────────── HELPERS (توابع کمکی متمرکز) ────────────────────────────────

def _send(chat_id: int, text: str, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return None

def _safe_edit(chat_id: int, msg_id: int, text: str, **kwargs):
    kwargs.setdefault('parse_mode', 'MarkdownV2')
    try:
        bot.edit_message_text(text, chat_id, msg_id, **kwargs)
    except apihelper.ApiTelegramException as e:
        if 'message is not modified' not in str(e):
            logger.error(f"Safe edit error on message {msg_id}: {e}")

# ──────────────────────────────── COMMAND HANDLERS & CONVERSATIONS ────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg: types.Message):
    uid = msg.from_user.id
    db.add_or_update_user(uid, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)
    if db.uuids(uid):
        _send(uid, "🏠 *به منوی اصلی خوش آمدید*", reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
    else:
        m = _send(uid, "👋 *خوش آمدید\\!*\n\nلطفاً `UUID` اکانت خود را ارسال کنید\\.", parse_mode="MarkdownV2")
        if m:
            bot.register_next_step_handler(m, _save_first_uuid)

def _save_first_uuid(message: types.Message):
    """Saves the very first UUID for a new user."""
    uid, uuid_str = message.from_user.id, message.text.strip()
    if not validate_uuid(uuid_str):
        m = _send(uid, "❌ `UUID` نامعتبر است\\. دوباره تلاش کنید\\.", parse_mode="MarkdownV2")
        if m:
            bot.register_next_step_handler(m, _save_first_uuid)
        return
    info = api_handler.user_info(uuid_str)
    if not info:
        m = _send(uid, "❌ `UUID` در پنل یافت نشد\\. دوباره تلاش کنید\\.", parse_mode="MarkdownV2")
        if m:
            bot.register_next_step_handler(m, _save_first_uuid)
        return
    db.add_uuid(uid, uuid_str, info["name"])
    _send(uid, "✅ اکانت شما با موفقیت افزوده شد\\.", reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")

def _add_uuid_step(message: types.Message):
    """Handles adding a new UUID via the 'add' button."""
    uid, uuid_str = message.from_user.id, message.text.strip()
    
    if not validate_uuid(uuid_str):
        _send(uid, "❌ `UUID` نامعتبر است\\.", parse_mode="MarkdownV2")
        return

    if len(db.uuids(uid)) >= 5:
        _send(uid, "❌ شما به حداکثر تعداد اکانت \\(۵ عدد\\) رسیده‌اید\\.", parse_mode="MarkdownV2")
        return

    info = api_handler.user_info(uuid_str)
    if not info:
        _send(uid, "❌ خطا در ارتباط با پنل یا `UUID` اشتباه است\\.", parse_mode="MarkdownV2")
        return

    if db.add_uuid(uid, uuid_str, info["name"]):
        _send(uid, f"✅ اکانت *{escape_markdown(info['name'])}* با موفقیت افزوده شد\\.", reply_markup=menu.main(uid in ADMIN_IDS), parse_mode="MarkdownV2")
    else:
        _send(uid, "❌ این `UUID` قبلاً توسط شما یا کاربر دیگری ثبت شده است\\.", parse_mode="MarkdownV2")

# ──────────────────────────────── CONVERSATION HANDLERS (ADMIN) ────────────────────────────────
def _start_add_user_convo(uid, msg_id):
    prompt = "لطفاً یک نام برای کاربر جدید وارد کنید:"
    _safe_edit(uid, msg_id, prompt, parse_mode=None)
    bot.register_next_step_handler_by_chat_id(uid, _get_name_for_add_user)

def _get_name_for_add_user(msg: types.Message):
    uid = msg.from_user.id
    admin_conversations[uid] = {'name': msg.text.strip()}
    
    name = msg.text.strip()
    prompt = f"نام کاربر: {name}\n\nحالا حجم مصرف (به گیگابایت) را وارد کنید (مثلاً: 50)."
    m = _send(uid, prompt)
    if m:
        bot.register_next_step_handler_by_chat_id(uid, _get_limit_for_add_user)

def _get_limit_for_add_user(msg: types.Message):
    uid = msg.from_user.id
    try:
        limit = float(msg.text)
        admin_conversations[uid]['usage_limit_GB'] = limit
        
        prompt = f"حجم: {limit} GB\n\nحالا مدت زمان پلن (به روز) را وارد کنید (مثلاً: 30)."
        m = _send(uid, prompt)
        if m:
            bot.register_next_step_handler_by_chat_id(uid, _get_days_for_add_user)
    except (ValueError, TypeError):
        _send(uid, "❌ ورودی نامعتبر است. لطفاً یک عدد وارد کنید.")
        if uid in admin_conversations:
            del admin_conversations[uid]

def _get_days_for_add_user(msg: types.Message):
    uid = msg.from_user.id
    try:
        days = int(msg.text)
        admin_conversations[uid]['package_days'] = days
        
        user_data = admin_conversations.pop(uid)
        
        name = escape_markdown(user_data['name'])
        limit = user_data['usage_limit_GB']
        days_val = user_data['package_days']
        
        wait_msg_text = f"⏳ در حال ساخت کاربر با اطلاعات:\nنام: `{name}`\nحجم: `{limit} GB`\nمدت: `{days_val} روز`"
        _send(uid, wait_msg_text, parse_mode="MarkdownV2")

        new_user_info = api_handler.add_user(user_data)

        if new_user_info:
            report = fmt_one(new_user_info, 0)
            uuid_escaped = escape_markdown(new_user_info['uuid'])
            success_text = (
                f"✅ کاربر با موفقیت ساخته شد\\.\n\n"
                f"{report}\n\n"
                f"جهت کپی کردن UUID روی آن کلیک کنید:\n`{uuid_escaped}`"
            )
            _send(uid, success_text, parse_mode="MarkdownV2")
        else:
            error_text = "❌ خطا در ساخت کاربر\\. ممکن است نام تکراری باشد یا پنل در دسترس نباشد\\."
            _send(uid, error_text, parse_mode="MarkdownV2")
            
    except (ValueError, TypeError):
        error_text = "❌ ورودی نامعتبر است\\. لطفاً یک عدد صحیح وارد کنید\\."
        _send(uid, error_text, parse_mode="MarkdownV2")
        if uid in admin_conversations:
            del admin_conversations[uid]

# ────────────────── CALLBACK ROUTER & HANDLERS ──────────────────
def _handle_user_callbacks(call: types.CallbackQuery, is_admin: bool):
    """Handles callback queries for the general user menu."""
    uid, data, msg_id = call.from_user.id, call.data, call.message.message_id

    if data == "manage":
        _safe_edit(uid, msg_id, "🔐 *فهرست اکانت‌ها*", reply_markup=menu.accounts(db.uuids(uid)))
    elif data == "quick_stats":
        text = quick_stats(db.uuids(uid))
        _safe_edit(uid, msg_id, text, reply_markup=menu.main(is_admin))
    elif data == "add":
        m = _send(uid, "UUID جدید را ارسال کنید:")
        if m:
            bot.register_next_step_handler_by_chat_id(uid, _add_uuid_step)
    elif data == "settings":
        settings = db.get_user_settings(uid)
        _safe_edit(uid, msg_id, "⚙️ *تنظیمات اعلان‌ها*", reply_markup=menu.settings(settings))
    elif data == "back":
        _safe_edit(uid, msg_id, "🏠 *منوی اصلی*", reply_markup=menu.main(is_admin))
    elif data.startswith("acc_"):
        uuid_id = int(data.split("_")[1])
        row = db.uuid_by_id(uid, uuid_id)
        if row and (info := api_handler.user_info(row["uuid"])):
            daily_usage = db.get_daily_usage(uuid_id)
            text = fmt_one(info, daily_usage)
            _safe_edit(uid, msg_id, text, reply_markup=menu.account_menu(uuid_id))
    elif data.startswith("toggle_"):
        setting_key = data.replace("toggle_", "")
        current_settings = db.get_user_settings(uid)
        db.update_user_setting(uid, setting_key, not current_settings.get(setting_key, True))
        _safe_edit(uid, msg_id, "⚙️ *تنظیمات شما به‌روز شد*", reply_markup=menu.settings(db.get_user_settings(uid)))
    elif data.startswith("getlinks_"):
        uuid_id = int(data.split("_")[1])
        row = db.uuid_by_id(uid, uuid_id)
        if row:
            name = escape_markdown(row['name'])
            link1 = escape_markdown(SUBSCRIPTION_LINKS['normal'])
            link2 = escape_markdown(SUBSCRIPTION_LINKS['b64'])
            text = f"🔗 *لینک اشتراک «{name}»*\n\n`{link1}`\n\n`{link2}`"
            _send(uid, text, parse_mode="MarkdownV2")
    elif data.startswith("del_"):
        uuid_id = int(data.split("_")[1])
        db.deactivate_uuid(uid, uuid_id)
        _safe_edit(uid, msg_id, "🗑 اکانت حذف شد\\.", reply_markup=menu.accounts(db.uuids(uid)))
    elif data.startswith("win_"):
        uuid_id = int(data.split("_")[1])
        txt = ["*مصرف در بازه‌های زمانی اخیر*\n"]
        for h in (3, 6, 12, 24):
            usage = db.window_usage(uuid_id, h)
            txt.append(f"• `{h:>2} ساعت گذشته:` `{usage:.2f} GB`")
        _safe_edit(uid, msg_id, "\n".join(txt), reply_markup=menu.account_menu(uuid_id))

def _handle_admin_callbacks(call: types.CallbackQuery):
    """Handles callback queries for the admin panel."""
    uid, data, msg_id = call.from_user.id, call.data, call.message.message_id
    
    if data == "admin_panel":
        _safe_edit(uid, msg_id, "👑 پنل مدیریت", reply_markup=menu.admin_panel(), parse_mode=None)
    elif data == "admin_management_menu":
        _safe_edit(uid, msg_id, "👥 مدیریت کاربران", reply_markup=menu.admin_management_menu(), parse_mode=None)
    elif data.startswith("admin_reports"):
        _safe_edit(uid, msg_id, "📜 *گزارش‌گیری کاربران*", reply_markup=menu.admin_reports_menu())
    elif data.startswith("admin_analytics"):
        _safe_edit(uid, msg_id, "📊 *تحلیل و گزارش‌ها*", reply_markup=menu.admin_analytics_menu())
    elif data == "admin_add_user":
        _start_add_user_convo(uid, msg_id)
    elif data == "admin_search_user":
        bot.answer_callback_query(call.id, "این قابلیت به زودی اضافه خواهد شد.")
    elif data == "admin_top_consumers":
        text = fmt_top_consumers(api_handler.get_all_users())
        _safe_edit(uid, msg_id, text, reply_markup=menu.admin_analytics_menu())
    elif data == "admin_health_check":
        text = fmt_panel_info(api_handler.get_panel_info())
        _safe_edit(uid, msg_id, text, reply_markup=menu.admin_analytics_menu())
    elif data.startswith(("admin_online_", "admin_active_1_", "admin_inactive_")):
        try:
            parts = data.split('_')
            base_callback = f"{parts[0]}_{parts[1]}"
            if "online" in base_callback: base_callback = "admin_online"

            page = int(parts[-1])
            bot.answer_callback_query(call.id, "در حال دریافت لیست...")
            
            text, kb = "", None

            if base_callback == "admin_online":
                online_list = api_handler.online_users()
                for user in online_list:
                    user['daily_usage_GB'] = db.get_daily_usage_by_uuid(user['uuid'])
                text = fmt_online_users_list(online_list, page)
                kb = menu.admin_user_list_menu(online_list, base_callback, page)
                if page == 0:
                    db.add_or_update_scheduled_message('online_users_report', uid, msg_id)
            else:
                lists = {
                    "admin_active_1": (api_handler.get_active_users, (1,), "کاربران فعال در ۲۴ ساعت گذشته"),
                    "admin_inactive_7": (api_handler.get_inactive_users, (1, 7), "غیرفعال (۱ تا ۷ روز)"),
                    "admin_inactive_0": (api_handler.get_inactive_users, (-1, -1), "هرگز متصل نشده")
                }
                base_callback = data.rsplit('_', 1)[0] # e.g., admin_inactive_7
                func, args, title = lists[base_callback]
                user_list = func(*args)
                text = fmt_users_list(user_list, title)
                kb = menu.admin_user_list_menu(user_list, base_callback, page)
            
            _safe_edit(uid, msg_id, text, reply_markup=kb)

        except Exception as e:
            logger.exception(f"ADMIN LIST Error for chat {uid}, data: {data}")
            _safe_edit(uid, msg_id, "❌ خطایی در پردازش لیست رخ داد.", reply_markup=menu.admin_reports_menu())
        try:
            days_str = data.split("_")[2]
            days = int(days_str)
            title, inactive_list = "", []
            if days == 0:
                inactive_list = api_handler.get_inactive_users(min_days=-1, max_days=-1)
                title = "کاربران هرگز متصل نشده"
            elif days == 7:
                inactive_list = api_handler.get_inactive_users(min_days=1, max_days=7)
                title = "کاربران غیرفعال بین ۱ تا ۷ روز"
            text = fmt_users_list(inactive_list, title)
            _safe_edit(uid, msg_id, text, reply_markup=menu.admin_user_list_menu(inactive_list, "admin_reports_menu"))
        except Exception as e:
            logger.error(f"Error fetching inactive users: {e}")
            _safe_edit(uid, msg_id, "❌ خطایی در دریافت لیست کاربران غیرفعال رخ داد\\.", reply_markup=menu.admin_reports_menu())
    
    elif data.startswith("admin_manage_"):
        uuid = data.replace("admin_manage_", "")
        info = api_handler.user_info(uuid)
        if info:
            daily_usage = db.get_daily_usage_by_uuid(uuid)
            text = fmt_one(info, daily_usage)
            _safe_edit(uid, msg_id, text, reply_markup=menu.admin_user_management(uuid, info['is_active']))
        else:
            bot.answer_callback_query(call.id, "❌ کاربر یافت نشد. ممکن است حذف شده باشد.")
            _safe_edit(uid, msg_id, "کاربر مورد نظر یافت نشد.", reply_markup=menu.admin_reports_menu())
    elif data.startswith("admin_toggle_"):
        uuid = data.replace("admin_toggle_", "")
        info = api_handler.user_info(uuid)
        if info:
            new_status = not info['is_active']
            if api_handler.modify_user(uuid, {'is_active': new_status}):
                bot.answer_callback_query(call.id, f"کاربر {'فعال' if new_status else 'غیرفعال'} شد.")
                new_info = api_handler.user_info(uuid)
                daily_usage = db.get_daily_usage_by_uuid(uuid)
                text = fmt_one(new_info, daily_usage)
                _safe_edit(uid, msg_id, text, reply_markup=menu.admin_user_management(uuid, new_info['is_active']))
            else:
                bot.answer_callback_query(call.id, "❌ خطا در تغییر وضعیت.")
    elif data.startswith("admin_reset_"):
        uuid = data.replace("admin_reset_", "")
        if api_handler.reset_user_usage(uuid):
            bot.answer_callback_query(call.id, "✅ مصرف کاربر صفر شد.")
            new_info = api_handler.user_info(uuid)
            daily_usage = db.get_daily_usage_by_uuid(uuid)
            text = fmt_one(new_info, daily_usage)
            _safe_edit(uid, msg_id, text, reply_markup=menu.admin_user_management(uuid, new_info['is_active']))
        else:
            bot.answer_callback_query(call.id, "❌ خطا در ریست کردن مصرف.")
    elif data.startswith("admin_delete_"):
        uuid = data.replace("admin_delete_", "")
        text = f"⚠️ *آیا از حذف کامل کاربر با UUID زیر اطمینان دارید؟*\n`{escape_markdown(uuid)}`\n\nاین عمل غیرقابل بازگشت است!"
        _safe_edit(uid, msg_id, text, reply_markup=menu.confirm_delete(uuid))
    elif data.startswith("admin_confirm_delete_"):
        uuid = data.replace("admin_confirm_delete_", "")
        _safe_edit(uid, msg_id, "⏳ در حال حذف کامل کاربر...")
        if api_handler.delete_user(uuid):
            db.delete_user_by_uuid(uuid)
            _safe_edit(uid, msg_id, "✅ کاربر با موفقیت از پنل و ربات حذف شد.", reply_markup=menu.admin_reports_menu())
        else:
            _safe_edit(uid, msg_id, "❌ خطا در حذف کاربر از پنل.", reply_markup=menu.admin_reports_menu())
    elif data.startswith("admin_cancel_delete_"):
        uuid = data.replace("admin_cancel_delete_", "")
        info = api_handler.user_info(uuid)
        if info:
            daily_usage = db.get_daily_usage_by_uuid(uuid)
            text = fmt_one(info, daily_usage)
            _safe_edit(uid, msg_id, text, reply_markup=menu.admin_user_management(uuid, info['is_active']))
        else:
            _safe_edit(uid, msg_id, "بازگشت به منوی گزارشات.", reply_markup=menu.admin_reports_menu())


@bot.callback_query_handler(func=lambda _: True)
def main_callback_router(call: types.CallbackQuery):
    """Routes all callback queries to the appropriate handler."""
    uid = call.from_user.id
    data = call.data
    is_admin = uid in ADMIN_IDS
    bot.answer_callback_query(call.id)

    if is_admin and data.startswith("admin_"):
        _handle_admin_callbacks(call)
    else:
        _handle_user_callbacks(call, is_admin)