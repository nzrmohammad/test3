from telebot import types
from .config import EMOJIS, PAGE_SIZE

class Menu:
    # =============================================================================
    # User Panel Menus
    # =============================================================================
    def main(self, is_admin: bool) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton(f"{EMOJIS['key']} مدیریت اکانت", callback_data="manage"),
            types.InlineKeyboardButton(f"{EMOJIS['lightning']} آمار فوری", callback_data="quick_stats")
        )

        btn_services = types.InlineKeyboardButton(f"{EMOJIS['money']} مشاهده سرویس ها", callback_data="view_plans")
        btn_settings = types.InlineKeyboardButton(f"{EMOJIS['bell']} تنظیمات", callback_data="settings")
        btn_birthday = types.InlineKeyboardButton("🎁 هدیه تولد", callback_data="birthday_gift")
        btn_support = types.InlineKeyboardButton("💬 پشتیبانی", callback_data="support")

        kb.add(btn_settings, btn_services)
        kb.add(btn_birthday, btn_support)

        if is_admin:
            kb.add(types.InlineKeyboardButton(f"{EMOJIS['crown']} پنل مدیریت", callback_data="admin:panel"))
        return kb

    def accounts(self, rows) -> types.InlineKeyboardMarkup:
            kb = types.InlineKeyboardMarkup(row_width=1)
            for r in rows:
                name = r.get('name', 'کاربر ناشناس')
                usage_percentage = r.get('usage_percentage', 0)
                expire_days = r.get('expire')

                summary = f"{usage_percentage:.0f}% Used"
                if expire_days is not None:
                    summary += f" / {expire_days} Days"

                button_text = f"📊 {name} ({summary})"
                kb.add(types.InlineKeyboardButton(button_text, callback_data=f"acc_{r['id']}"))

            kb.add(types.InlineKeyboardButton("➕ افزودن اکانت جدید", callback_data="add"))
            kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back"))
            return kb
    
    def account_menu(self, uuid_id: int) -> types.InlineKeyboardMarkup:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("⏱ مصرف بازه‌ای", callback_data=f"win_select_{uuid_id}"),
                types.InlineKeyboardButton(f"{EMOJIS['globe']} دریافت لینک‌ها", callback_data=f"getlinks_{uuid_id}")
            )
            kb.add(
                types.InlineKeyboardButton("💳 سابقه پرداخت", callback_data=f"payment_history_{uuid_id}_0"),
                types.InlineKeyboardButton("🗑 حذف", callback_data=f"del_{uuid_id}")
            )
            kb.add(types.InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="manage"))
            return kb

    def quick_stats_menu(self, num_accounts: int, current_page: int) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        nav_buttons = []
        if num_accounts > 1:
            if current_page > 0:
                # The missing quote is added back here
                nav_buttons.append(types.InlineKeyboardButton("⬅️ اکانت قبلی", callback_data=f"qstats_acc_page_{current_page - 1}"))
            if current_page < num_accounts - 1:
                nav_buttons.append(types.InlineKeyboardButton("اکانت بعدی ➡️", callback_data=f"qstats_acc_page_{current_page + 1}"))

        if nav_buttons:
            kb.row(*nav_buttons)

        kb.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back"))
        return kb

    def server_selection_menu(self, uuid_id: int, show_hiddify: bool, show_marzban: bool) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        buttons = []
        if show_hiddify:
            buttons.append(types.InlineKeyboardButton("آلمان 🇩🇪", callback_data=f"win_hiddify_{uuid_id}"))
        if show_marzban:
            buttons.append(types.InlineKeyboardButton("فرانسه 🇫🇷", callback_data=f"win_marzban_{uuid_id}"))
        
        if buttons:
            kb.add(*buttons)

        btn_back = types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"acc_{uuid_id}")
        kb.add(btn_back)
        return kb

    def plan_category_menu(self) -> types.InlineKeyboardMarkup:
            kb = types.InlineKeyboardMarkup(row_width=2)
            btn_germany = types.InlineKeyboardButton("🇩🇪 سرویس‌های آلمان", callback_data="show_plans:germany")
            btn_france = types.InlineKeyboardButton("🇫🇷 سرویس‌های فرانسه", callback_data="show_plans:france")
            btn_combined = types.InlineKeyboardButton("🚀 سرویس‌های ترکیبی", callback_data="show_plans:combined")
            btn_back = types.InlineKeyboardButton("🔙 بازگشت", callback_data="back")
            kb.add(btn_france, btn_germany)
            kb.add(btn_combined)
            kb.add(btn_back)
            return kb

    def settings(self, settings_dict: dict) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        daily_text = f"📊 گزارش روزانه: {'✅' if settings_dict.get('daily_reports', True) else '❌'}"
        expiry_text = f"⏰ هشدار انقضا: {'✅' if settings_dict.get('expiry_warnings', True) else '❌'}"
        kb.add(
            types.InlineKeyboardButton(daily_text, callback_data="toggle_daily_reports"),
            types.InlineKeyboardButton(expiry_text, callback_data="toggle_expiry_warnings")
        )
        hiddify_text = f"🇩🇪 هشدار حجم آلمان: {'✅' if settings_dict.get('data_warning_hiddify', True) else '❌'}"
        marzban_text = f"🇫🇷 هشدار حجم فرانسه: {'✅' if settings_dict.get('data_warning_marzban', True) else '❌'}"
        kb.add(
            types.InlineKeyboardButton(hiddify_text, callback_data="toggle_data_warning_hiddify"),
            types.InlineKeyboardButton(marzban_text, callback_data="toggle_data_warning_marzban")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="back"))
        return kb

    # =============================================================================
    # Admin Panel Menus
    # =============================================================================

    ### 1. Main Navigation ###
    def admin_panel(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("📜 گزارش گیری", callback_data="admin:reports_menu"),
            types.InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin:management_menu")
        )
        kb.add(
            types.InlineKeyboardButton("📊 وضعیت سیستم", callback_data="admin:system_status_menu"),
            types.InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="admin:search_menu")
        )
        kb.add(
            types.InlineKeyboardButton("🗄️ پشتیبان‌گیری", callback_data="admin:backup_menu"),
            types.InlineKeyboardButton("📤 پیام همگانی", callback_data="admin:broadcast")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back"))
        return kb

    def admin_server_selection_menu(self, base_callback: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("آلمان 🇩🇪", callback_data=f"{base_callback}:hiddify"),
            types.InlineKeyboardButton("فرانسه 🇫🇷", callback_data=f"{base_callback}:marzban")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin:panel"))
        return kb

    ### 2. User Management ###
    def admin_management_menu(self) -> types.InlineKeyboardMarkup:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("آلمان 🇩🇪", callback_data="admin:manage_panel:hiddify"),
                types.InlineKeyboardButton("فرانسه 🇫🇷", callback_data="admin:manage_panel:marzban")
            )
            kb.add(
                types.InlineKeyboardButton("⚙️ دستورات گروهی", callback_data="admin:group_actions_menu")
            )
            kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin:panel"))
            return kb

    def admin_panel_management_menu(self, panel: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("➕ افزودن کاربر جدید", callback_data=f"admin:add_user:{panel}"),
            types.InlineKeyboardButton("📋 لیست کاربران پنل", callback_data=f"admin:list:panel_users:{panel}:0")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به انتخاب پنل", callback_data="admin:management_menu"))
        return kb

    def admin_user_interactive_management(self, identifier: str, is_active: bool, panel: str, back_callback: str | None = None) -> types.InlineKeyboardMarkup:
            kb = types.InlineKeyboardMarkup(row_width=2)
            status_text = "🔴 غیرفعال کردن" if is_active else "🟢 فعال کردن"
            
            kb.add(
                types.InlineKeyboardButton(status_text, callback_data=f"admin:tgl:{identifier}"),
                types.InlineKeyboardButton("📝 یادداشت ادمین", callback_data=f"admin:note:{identifier}")
            )
            kb.add(types.InlineKeyboardButton("💳 ثبت پرداخت", callback_data=f"admin:log_payment:{identifier}"),
                types.InlineKeyboardButton("📜 سابقه پرداخت", callback_data=f"admin:payment_history:{identifier}:0"))
            kb.add(
                types.InlineKeyboardButton("🔄 ریست مصرف", callback_data=f"admin:rusg_m:{identifier}"),
                types.InlineKeyboardButton("🗑 حذف کامل", callback_data=f"admin:del_cfm:{identifier}")
            )
            kb.add(
                types.InlineKeyboardButton("🔧 ویرایش کاربر", callback_data=f"admin:edt:{identifier}"),
                types.InlineKeyboardButton("🔄 ریست تاریخ تولد", callback_data=f"admin:rb:{identifier}")
            )

            final_back_callback = back_callback or f"admin:manage_panel:{panel}"
            kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=final_back_callback))
            return kb

    def admin_edit_user_menu(self, identifier: str, panel: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("➕ افزودن حجم", callback_data=f"admin:ae:add_gb:{panel}:{identifier}"),
            types.InlineKeyboardButton("➕ افزودن روز", callback_data=f"admin:ae:add_days:{panel}:{identifier}")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin:us:{panel}:{identifier}"))
        return kb

    def admin_reset_usage_selection_menu(self, identifier: str, panel: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        btn_h = types.InlineKeyboardButton("آلمان 🇩🇪", callback_data=f"admin:rsa:hiddify:{identifier}")
        btn_m = types.InlineKeyboardButton("فرانسه 🇫🇷", callback_data=f"admin:rsa:marzban:{identifier}")
        btn_both = types.InlineKeyboardButton("هر دو پنل", callback_data=f"admin:rsa:both:{identifier}")
        btn_back = types.InlineKeyboardButton("🔙 لغو و بازگشت", callback_data=f"admin:us:{panel}:{identifier}")
        kb.add(btn_h, btn_m)
        kb.add(btn_both)
        kb.add(btn_back)
        return kb

    ### 3. Reporting & Analytics ###
    def admin_reports_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🇩🇪", callback_data="admin:panel_reports:hiddify"),
            types.InlineKeyboardButton("🇫🇷", callback_data="admin:panel_reports:marzban")
        )
        kb.add(types.InlineKeyboardButton("📈 تحلیل کاربران", callback_data="admin:user_analysis_menu"))
        kb.add(types.InlineKeyboardButton("📝 کاربران بدون پلن", callback_data="admin:list_no_plan:0"))
        kb.add(
             types.InlineKeyboardButton("💳 پرداخت‌ها", callback_data="admin:list:payments:0"),
             types.InlineKeyboardButton("🤖 لیست کاربران ربات", callback_data="admin:list:bot_users:0")
        )
        kb.add(types.InlineKeyboardButton("🎂 تولد کاربران", callback_data="admin:list:birthdays:0"))
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="admin:panel"))
        return kb
        
    def admin_panel_specific_reports_menu(self, panel: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ فعال (۲۴ ساعت اخیر)", callback_data=f"admin:list:active_users:{panel}:0"),
            types.InlineKeyboardButton("📡 کاربران آنلاین", callback_data=f"admin:list:online_users:{panel}:0")
        )
        kb.add(
            types.InlineKeyboardButton("🚫 هرگز متصل نشده", callback_data=f"admin:list:never_connected:{panel}:0"),
            types.InlineKeyboardButton("⏳ غیرفعال (۱ تا ۷ روز)", callback_data=f"admin:list:inactive_users:{panel}:0")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به گزارش‌گیری", callback_data="admin:reports_menu"))
        return kb

    def admin_analytics_menu(self, panel: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("🏆 پرمصرف‌ترین کاربران", callback_data=f"admin:list:top_consumers:{panel}:0"))
        if panel == 'hiddify':
            kb.add(types.InlineKeyboardButton("🌡️ وضعیت سلامت پنل", callback_data="admin:health_check"))
        elif panel == 'marzban':
            kb.add(types.InlineKeyboardButton("🖥️ وضعیت سیستم", callback_data="admin:marzban_stats"))

        kb.add(types.InlineKeyboardButton("🔙 بازگشت به انتخاب پنل", callback_data="admin:select_server:analytics_menu"),
               types.InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin:panel"))
        return kb

    def admin_select_plan_for_report_menu(self) -> types.InlineKeyboardMarkup:
        from utils import load_service_plans
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        plans = load_service_plans()
        for i, plan in enumerate(plans):
            callback = f"admin:list_by_plan:{i}:0"
            kb.add(types.InlineKeyboardButton(plan.get('name', f'Plan {i+1}'), callback_data=callback)) 
        kb.add(types.InlineKeyboardButton("📝 کاربران بدون پلن", callback_data="admin:list_no_plan:0"))
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin:reports_menu"))
        return kb
        
    ### 4. Group Actions & Other Tools ###
    def admin_select_plan_for_action_menu(self) -> types.InlineKeyboardMarkup:
            from utils import load_service_plans
            kb = types.InlineKeyboardMarkup(row_width=1)
            
            plans = load_service_plans()
            for i, plan in enumerate(plans):
                callback = f"admin:ga_select_type:{i}"
                kb.add(types.InlineKeyboardButton(plan.get('name', f'Plan {i+1}'), callback_data=callback))
                
            kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin:group_actions_menu"))
            return kb

    def admin_select_action_type_menu(self, context_value: any, context_type: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("➕ افزودن حجم", callback_data=f"admin:ga_ask_value:add_gb:{context_type}:{context_value}"),
            types.InlineKeyboardButton("➕ افزودن روز", callback_data=f"admin:ga_ask_value:add_days:{context_type}:{context_value}")
        )
        
        back_cb = "admin:group_action_select_plan" if context_type == 'plan' else "admin:adv_ga_select_filter"
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb))
        return kb

    def broadcast_target_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("📡 آنلاین", callback_data="admin:broadcast_target:online"),
            types.InlineKeyboardButton("✅ فعال اخیر", callback_data="admin:broadcast_target:active_1")
        )
        kb.add(
            types.InlineKeyboardButton("⏳ غیرفعال اخیر", callback_data="admin:broadcast_target:inactive_7"),
            types.InlineKeyboardButton("🚫 هرگز متصل نشده", callback_data="admin:broadcast_target:inactive_0")
        )
        kb.add(types.InlineKeyboardButton("👥 همه کاربران ربات", callback_data="admin:broadcast_target:all"))
        kb.add(types.InlineKeyboardButton("🔙 لغو و بازگشت", callback_data="admin:panel"))
        return kb

    def admin_backup_selection_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🗂 دیتابیس ربات (آلمان)", callback_data="admin:backup:bot_db"),
            types.InlineKeyboardButton("📄 کاربران فرانسه (JSON)", callback_data="admin:backup:marzban")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin:panel"))
        return kb

    # =============================================================================
    # Utility & Helper Menus
    # =============================================================================
    def create_pagination_menu(self, base_callback: str, current_page: int, total_items: int, back_callback: str) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        back_text = "🔙 بازگشت"

        if total_items <= PAGE_SIZE:
            kb.add(types.InlineKeyboardButton(back_text, callback_data=back_callback))
            return kb

        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ قبلی", callback_data=f"{base_callback}:{current_page - 1}"))
        if (current_page + 1) * PAGE_SIZE < total_items:
            nav_buttons.append(types.InlineKeyboardButton("بعدی ➡️", callback_data=f"{base_callback}:{current_page + 1}"))

        if nav_buttons:
            kb.row(*nav_buttons)

        kb.add(types.InlineKeyboardButton(back_text, callback_data=back_callback))
        return kb

    def cancel_action(self, back_callback="back") -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 لغو عملیات", callback_data=back_callback))
        return kb
        
    def confirm_delete(self, identifier: str, panel: str) -> types.InlineKeyboardMarkup:
        panel_short = 'h' if panel == 'hiddify' else 'm'
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("❌ بله، حذف کن", callback_data=f"admin:del_a:confirm:{panel_short}:{identifier}"),
            types.InlineKeyboardButton("✅ نه، لغو کن", callback_data=f"admin:del_a:cancel:{panel_short}:{identifier}")
        )
        return kb
    
    def admin_advanced_group_action_filter_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("⏳ کاربران در آستانه انقضا (کمتر از ۳ روز)", callback_data="admin:adv_ga_select_action:expiring_soon"))
        kb.add(types.InlineKeyboardButton("🚫 کاربران غیرفعال (بیش از ۳۰ روز)", callback_data="admin:adv_ga_select_action:inactive_30_days"))
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin:management_menu"))
        return kb

    def admin_search_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🔎 جستجوی جامع کاربر", callback_data="admin:sg"),
            types.InlineKeyboardButton("🆔 جستجو با آیدی تلگرام", callback_data="admin:search_by_tid")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin:management_menu"))
        return kb

    def admin_group_actions_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("⚙️ دستور گروهی (بر اساس پلن)", callback_data="admin:group_action_select_plan"),
            types.InlineKeyboardButton("🔥 دستور گروهی (پیشرفته)", callback_data="admin:adv_ga_select_filter")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin:management_menu"))
        return kb
    
    def get_links_menu(self, uuid_id: int) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("📋 Normal", callback_data=f"getlink_normal_{uuid_id}"),
            types.InlineKeyboardButton("📝 Base64", callback_data=f"getlink_b64_{uuid_id}")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"acc_{uuid_id}"))
        return kb

    def admin_system_status_menu(self) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("آلمان 🇩🇪", callback_data="admin:health_check"),
            types.InlineKeyboardButton("فرانسه 🇫🇷", callback_data="admin:marzban_stats")
        )
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="admin:panel"))
        return kb

menu = Menu()