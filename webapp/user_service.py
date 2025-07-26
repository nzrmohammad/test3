from datetime import datetime, timedelta
import pytz
from bot.database import db
from bot.combined_handler import get_combined_user_info
from bot.utils import to_shamsi, format_relative_time, days_until_next_birthday
import logging

logger = logging.getLogger(__name__)

class UserService:
    """سرویس مخصوص داشبورد کاربری - نسخه نهایی با تمام قابلیت‌های یکپارچه"""
    
    @staticmethod
    def get_user_usage_stats(uuid_id):
        tehran_tz = pytz.timezone("Asia/Tehran")
        labels, hiddify_data, marzban_data = [], [], []
        total_usage_7_days = 0
        
        with db._conn() as c:
            for i in range(6, -1, -1):
                target_date = datetime.now(tehran_tz) - timedelta(days=i)
                day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                day_start_utc, day_end_utc = day_start.astimezone(pytz.utc), day_end.astimezone(pytz.utc)
                
                query = "SELECT (MAX(hiddify_usage_gb) - MIN(hiddify_usage_gb)) as h, (MAX(marzban_usage_gb) - MIN(marzban_usage_gb)) as m FROM usage_snapshots WHERE uuid_id = ? AND taken_at >= ? AND taken_at < ?"
                row = c.execute(query, (uuid_id, day_start_utc, day_end_utc)).fetchone()
                
                h_usage = max(0, row['h'] or 0) if row else 0
                m_usage = max(0, row['m'] or 0) if row else 0
                
                labels.append(day_start.strftime('%m/%d'))
                hiddify_data.append(round(h_usage, 2))
                marzban_data.append(round(m_usage, 2))
                total_usage_7_days += h_usage + m_usage
        
        avg_daily_usage = total_usage_7_days / 7 if total_usage_7_days > 0 else 0
        chart_data = {"labels": labels, "hiddify_data": hiddify_data, "marzban_data": marzban_data}
        
        return chart_data, avg_daily_usage

    @staticmethod
    def get_birthday_info(user_basic):
        birthday = user_basic.get("birthday")
        days_until = days_until_next_birthday(birthday) if birthday else None
        message = None
        if days_until is not None:
            if days_until == 0: message = "🎉 تولدتان مبارک!"
            elif days_until <= 7: message = f"🎂 {days_until} روز تا تولد شما!"
        return {"days_until_birthday": days_until, "birthday_message": message, "has_birthday": birthday is not None}
    
    @staticmethod
    def get_general_status(is_active, expire_days, usage_percentage):
        if not is_active: return {"text": "غیرفعال", "class": "status-inactive"}
        if expire_days is not None and (expire_days < 7 or usage_percentage >= 90): return {"text": "رو به اتمام", "class": "status-warning"}
        return {"text": "فعال", "class": "status-active"}

    @staticmethod
    def get_online_status(last_online):
        online_status, online_class = "آفلاین", "text-danger"
        if last_online:
            now_utc = datetime.now(pytz.utc)
            if last_online.tzinfo is None: last_online = pytz.utc.localize(last_online)
            time_diff = (now_utc - last_online).total_seconds()
            if time_diff < 180: online_status, online_class = "آنلاین", "text-success"
            elif time_diff < 300: online_status, online_class = "اخیراً آنلاین", "text-warning"
        return online_status, online_class
        
    @staticmethod
    def get_user_breakdown_data(combined_info, usage_today):
        """پردازش داده‌های breakdown با افزودن تمام جزئیات برای هر پنل"""
        breakdown = {}
        if not (combined_info and 'breakdown' in combined_info):
            return breakdown
        breakdown = combined_info['breakdown'].copy()
        
        if 'hiddify' in breakdown: breakdown['hiddify']['today_usage_GB'] = usage_today.get('hiddify', 0)
        if 'marzban' in breakdown: breakdown['marzban']['today_usage_GB'] = usage_today.get('marzban', 0)

        for panel_data in breakdown.values():
            usage = panel_data.get('current_usage_GB', 0)
            limit = panel_data.get('usage_limit_GB', 0)
            panel_data['usage_percentage'] = (usage / limit * 100) if limit > 0 else 0
            
            expire_val = panel_data.get('expire')
            if expire_val is not None: panel_data['expire_shamsi'] = to_shamsi(datetime.now() + timedelta(days=expire_val))
            else: panel_data['expire_shamsi'] = "نامشخص"

            last_online_dt = panel_data.get('last_online')
            panel_data['online_status'], _ = UserService.get_online_status(last_online_dt)
            panel_data['last_online_shamsi'] = to_shamsi(last_online_dt, include_time=True) if last_online_dt else "هرگز"
            
        return breakdown

    @staticmethod
    def get_processed_user_data(uuid):
        try:
            uuid_record = db.get_user_uuid_record(uuid)
            if not uuid_record: return None
            
            uuid_id = uuid_record['id']
            user_basic = db.user(uuid_record.get('user_id')) or {}
            combined_info = get_combined_user_info(uuid) or {}
            
            expire_days = combined_info.get('expire')
            
            current_usage = combined_info.get('usage', {}).get('total_usage_GB', 0)
            usage_limit = combined_info.get('usage', {}).get('data_limit_GB', 50)
            usage_percentage = (current_usage / usage_limit * 100) if usage_limit > 0 else 0
            
            usage_today = db.get_usage_since_midnight_by_uuid(uuid)
            chart_data, avg_daily_usage = UserService.get_user_usage_stats(uuid_id)
            
            is_active = uuid_record.get("is_active", 0) == 1
            general_status = UserService.get_general_status(is_active, expire_days, usage_percentage)
            
            expire_shamsi = "نامشخص"
            if expire_days is not None:
                if expire_days < 0: expire_shamsi = "منقضی شده"
                elif expire_days == 0: expire_shamsi = "امروز منقضی می‌شود"
                else: expire_shamsi = to_shamsi(datetime.now() + timedelta(days=expire_days))

            return {
                "is_active": is_active,
                "general_status": general_status,
                "avg_daily_usage_GB": avg_daily_usage,
                "expire_shamsi": expire_shamsi,
                "expire": expire_days if expire_days is not None and expire_days >= 0 else 0,
                "current_usage_GB": current_usage,
                "usage_limit_GB": usage_limit,
                "usage_percentage": round(usage_percentage, 1),
                "usage_chart_data": chart_data,
                "username": user_basic.get("username", "کاربر"),
                "breakdown": UserService.get_user_breakdown_data(combined_info, usage_today),
                **UserService.get_birthday_info(user_basic)
            }
        except Exception as e:
            logger.error(f"خطا در دریافت داده‌های کاربر {uuid}: {e}", exc_info=True)
            return None

user_service = UserService()
