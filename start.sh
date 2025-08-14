#!/bin/bash

# Start cron daemon
service cron start

# Initialize database if it doesn't exist
python init_db.py

# Start the Flask application
exec gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 app:app
