import requests
import logging
import json
from datetime import datetime, timedelta
import pytz
import os
from .config import MARZBAN_API_BASE_URL, MARZBAN_API_USERNAME, MARZBAN_API_PASSWORD, API_TIMEOUT, api_cache
from .database import db
from cachetools import cached

logger = logging.getLogger(__name__)

class MarzbanAPIHandler:
    def __init__(self):
        self.base_url = MARZBAN_API_BASE_URL.rstrip('/')
        self.api_base_url = f"{self.base_url}/api"
        self.username = MARZBAN_API_USERNAME
        self.password = MARZBAN_API_PASSWORD
        self.access_token = None
        self.utc_tz = pytz.utc
        self.uuid_to_username_map, self.username_to_uuid_map = {}, {}
        self.session = self._create_session() 
        self.reload_uuid_maps()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        return session

    def reload_uuid_maps(self) -> bool:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        uuid_map_path = os.path.join(current_dir, 'uuid_to_marzban_user.json')
        try:
            with open(uuid_map_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.uuid_to_username_map = {k.lower(): v for k, v in data.items()}
                self.username_to_uuid_map = {v: k.lower() for k, v in data.items()}
                logger.info(f"Successfully loaded/reloaded {len(self.uuid_to_username_map)} user mappings from JSON.")
                return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load or reload {uuid_map_path}: {e}")
            self.uuid_to_username_map, self.username_to_uuid_map = {}, {}
            return False

    def _get_access_token(self) -> bool:
        """Fetches and sets the access token. Returns True on success, False on failure."""
        try:
            url = f"{self.api_base_url}/admin/token"
            data = {"username": self.username, "password": self.password}
            response = self.session.post(url, data=data, timeout=API_TIMEOUT) 
            response.raise_for_status()
            self.access_token = response.json().get("access_token")
            if self.access_token:
                logger.info("Marzban: Successfully obtained new access token.")
                self.session.headers.update({"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"})
                return True
            logger.error("Marzban: Failed to get access token, token not found in response.")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Marzban: Failed to get access token: {e}", exc_info=True)
            self.access_token = None
            return False
        
    def _request(self, method, endpoint, retry=True, **kwargs):
        """A central request function with automatic token refresh."""
        if not self.access_token:
            if not self._get_access_token():
                return None

        url = f"{self.api_base_url}/{endpoint.strip('/')}"
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        kwargs['headers'] = headers
        
        try:
            response = self.session.request(method, url, timeout=API_TIMEOUT, **kwargs) 
            if response.status_code == 401 and retry:
                logger.warning("Marzban: Access token expired or invalid. Retrying to get a new one.")
                if self._get_access_token():
                    kwargs['headers'] = self.session.headers
                    return self._request(method, endpoint, retry=False, **kwargs)

            response.raise_for_status()
            
            if response.status_code == 204:
                return True
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Marzban API request failed: {method} {url} - Error: {e}", exc_info=True)
            return None

    def add_user(self, user_data: dict) -> dict | None:
        expire_timestamp = 0
        if user_data.get('package_days', 0) > 0:
            expire_timestamp = int((datetime.now() + timedelta(days=user_data.get('package_days', 0))).timestamp())

        payload = {
            "username": user_data.get('username'),
            "proxies": {"vless": {}},
            "data_limit": int(user_data.get('usage_limit_GB', 0) * (1024**3)),
            "expire": expire_timestamp,
        }
        
        return self._request("POST", "/user", json=payload)

    def modify_user(self, username: str, data: dict = None, add_usage_gb: float = 0, add_days: int = 0) -> bool:
        # به جای requests.get از self._request استفاده می‌کنیم
        current_data = self._request("GET", f"/user/{username}")
        
        # اگر کاربر یافت نشد یا خطایی رخ داد، عملیات را متوقف کن
        if not current_data:
            logger.error(f"Marzban: Failed to get current data for user '{username}' before modification.")
            return False

        # بقیه کد شما کاملاً درست است و بدون تغییر باقی می‌ماند
        try:
            payload = data.copy() if data else {}

            if add_usage_gb != 0:
                current_limit = current_data.get('data_limit', 0)
                payload['data_limit'] = current_limit + int(add_usage_gb * (1024**3))

            if add_days != 0:
                current_expire_ts = current_data.get('expire', 0)
                base_time = datetime.fromtimestamp(current_expire_ts) if current_expire_ts > 0 else datetime.now()
                if base_time < datetime.now():
                    base_time = datetime.now()
                new_expire_dt = base_time + timedelta(days=add_days)
                payload['expire'] = int(new_expire_dt.timestamp())

            if not payload:
                return True

            response = self._request("PUT", f"/user/{username}", json=payload)
            
            return response is not None

        except Exception as e:
            logger.error(f"Marzban: Failed to process payload for modifying user '{username}': {e}")
        return False
        
    def _parse_marzban_datetime(self, date_str: str | None) -> datetime | None:
            if not date_str:
                return None
            try:
                clean_str = date_str.replace('Z', '+00:00').split('.')[0]
                dt_obj = datetime.fromisoformat(clean_str)

                if dt_obj.tzinfo is None:
                    dt_obj = self.utc_tz.localize(dt_obj)
                return dt_obj
            except (ValueError, TypeError):
                logger.warning(f"Could not parse Marzban datetime string: {date_str}")
                return None
        
    def get_user_info(self, uuid: str) -> dict | None:
        """Gets a single user's details from Marzban by their Hiddify UUID."""
        if not self.access_token:
            if not self._get_access_token():
                return None
        
        marzban_username = self.uuid_to_username_map.get(uuid.lower())
        if not marzban_username:
            return None

        return self.get_user_by_username(marzban_username)

    @cached(api_cache)
    def get_all_users(self) -> list[dict]:
            all_users_raw = self._request("GET", "/users")
            if not all_users_raw or 'users' not in all_users_raw:
                return []

            normalized_users = []
            for user in all_users_raw['users']:
                username = user.get("username")
                if not username:
                    continue

                data_limit = user.get('data_limit')
                limit_gb = round(data_limit / (1024**3), 3) if data_limit is not None else 0
                
                used_traffic = user.get('used_traffic', 0)
                usage_gb = used_traffic / (1024 ** 3)
                
                uuid = self.username_to_uuid_map.get(username)
                expire_timestamp = user.get('expire')
                expire_days = None
                if expire_timestamp and expire_timestamp > 0:
                    expire_datetime = datetime.fromtimestamp(expire_timestamp, tz=self.utc_tz)
                    expire_days = (expire_datetime - datetime.now(self.utc_tz)).days

                normalized_data = {
                    "username": username,
                    "name": username,
                    "uuid": uuid,
                    "is_active": user.get('status') == 'active',
                    "last_online": self._parse_marzban_datetime(user.get('online_at')),
                    "usage_limit_GB": limit_gb,
                    "current_usage_GB": usage_gb,
                    "remaining_GB": max(0, limit_gb - usage_gb),
                    "usage_percentage": (usage_gb / limit_gb * 100) if limit_gb > 0 else 0,
                    "expire": expire_days,
                }
                normalized_users.append(normalized_data)
                
            return normalized_users
        
    def get_user_by_username(self, username: str) -> dict | None:
        user = self._request("GET", f"/user/{username}")
        if not user: return None

        uuid = self.username_to_uuid_map.get(username, None)
        usage_gb = user.get('used_traffic', 0) / (1024 ** 3)
        limit_gb = round(user.get('data_limit', 0) / (1024 ** 3), 3)
        expire_timestamp = user.get('expire')
        expire_days = None
        if expire_timestamp and expire_timestamp > 0:
            expire_datetime = datetime.fromtimestamp(expire_timestamp, tz=self.utc_tz)
            expire_days = (expire_datetime - datetime.now(self.utc_tz)).days

        normalized_data = {
            "username": username, "name": username, "uuid": uuid, "is_active": user.get('status') == 'active',
            "last_online": self._parse_marzban_datetime(user.get('online_at')),
            "usage_limit_GB": limit_gb, "current_usage_GB": usage_gb,
            "remaining_GB": max(0, limit_gb - usage_gb),
            "usage_percentage": (usage_gb / limit_gb * 100) if limit_gb > 0 else 0,
            "expire": expire_days,
        }
        return normalized_data

    def get_system_stats(self) -> dict | None:
            if not self.access_token:
                return None
            try:
                url = f"{self.base_url}/api/system"
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Marzban: Failed to get system stats: {e}")
                return None

    def delete_user(self, username: str) -> bool:
        if not self.access_token:
            return False
        try:
            url = f"{self.base_url}/api/user/{username}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Marzban: Failed to delete user '{username}': {e}")
            return False

    def reset_user_usage(self, username: str) -> bool:
        if not self.access_token:
            return False
        try:
            url = f"{self.base_url}/api/user/{username}/reset"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(url, headers=headers, timeout=API_TIMEOUT)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Marzban: Failed to reset usage for user '{username}': {e}")
            return False

    def check_connection(self) -> bool:
        """برای بررسی صحت اتصال و اطلاعات ورود، وضعیت سیستم را درخواست می‌کند."""
        logger.info("Checking Marzban panel connection...")
        # تابع _get_access_token خودش اتصال را تست می‌کند
        return self._get_access_token()

marzban_handler = MarzbanAPIHandler()