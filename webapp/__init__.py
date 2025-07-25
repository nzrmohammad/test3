from flask import Flask

def create_app():

    app = Flask(__name__, instance_relative_config=True)
    
    from .user_routes import user_bp
    from .admin_routes import admin_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    print("Flask app created and blueprints registered successfully.")
    return app