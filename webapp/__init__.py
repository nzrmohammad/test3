from flask import Flask
import logging

def create_app():
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.INFO)

    app = Flask(__name__, instance_relative_config=True)

    from .user_routes import user_bp
    from .admin_routes import admin_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    logging.info("Flask app created and blueprints registered successfully.")
    return app