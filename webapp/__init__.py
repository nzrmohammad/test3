from flask import Flask
import sys
import os
from webapp.user_routes import user_bp
from webapp.admin_routes import admin_bp

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_app():
    app = Flask(__name__)

    app.secret_key = os.urandom(24)
    
    with app.app_context():

        app.register_blueprint(user_bp)
        app.register_blueprint(admin_bp)
        
    return app