#!/bin/bash

# Set Python path
export PYTHONPATH=/home/site/wwwroot:/home/site/wwwroot/webapp

# Collect static files
echo "Collecting static files..."
python /home/site/wwwroot/webapp/manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting Gunicorn..."
gunicorn --bind=0.0.0.0 --timeout 600 --access-logfile '-' --error-logfile '-' webapp.wsgi:application