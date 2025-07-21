# file: run.py
from webapp import create_app
import os

# برنامه فلسک را ایجاد می‌کند
app = create_app()

if __name__ == '__main__':
    # این بخش فقط زمانی اجرا می‌شود که شما مستقیماً این فایل را اجرا کنید
    # (مثلاً با دستور: python run.py)
    # و برای اجرای اصلی روی سرور استفاده نمی‌شود.
    app.run(host='0.0.0.0', port=5000, debug=True)