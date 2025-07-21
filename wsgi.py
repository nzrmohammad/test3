# file: /opt/custom_bot/wsgi.py
from dotenv import load_dotenv

# .env is in the same directory, so this will work correctly
load_dotenv()

# Since gunicorn will run from this directory, it can see the 'webapp' package
from webapp import create_app

# Create the app for Gunicorn
app = create_app()