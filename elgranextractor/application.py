"""
Azure App Service entry point.
This file is required for Azure to detect and run the Django application.
"""

import os
import sys

# Add the current directory to the path so we can import webapp
sys.path.insert(0, os.path.dirname(__file__))

# Import the WSGI application from Django
from webapp.wsgi import application as app

# Azure looks for 'application' module with 'app' object
# This satisfies both: 'application:app' and 'webapp.wsgi:application'