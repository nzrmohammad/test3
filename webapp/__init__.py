from flask import Flask
import sys
import os

# این بخش برای پیدا کردن پوشه bot ضروری است
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_app():
    app = Flask(__name__)
    
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.main_bp)
        
    return app