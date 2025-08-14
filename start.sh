#!/bin/bash
set -e

echo "Starting GitHub Backup Service..."

# Ensure required directories exist with proper permissions
mkdir -p /app/data /app/logs /app/backups
chmod 755 /app/data /app/logs /app/backups

echo "Directories created/verified:"
ls -la /app/ | grep -E "(data|logs|backups)"

# Note: Running as non-root user, so we can't start system cron
# Instead, we'll rely on APScheduler for job scheduling

# Initialize database if it doesn't exist
echo "Initializing database..."
python init_db.py

if [ $? -eq 0 ]; then
    echo "Database initialization completed successfully"
else
    echo "Database initialization failed!"
    exit 1
fi

# Verify database file exists
if [ -f "/app/data/github_backup.db" ]; then
    echo "✅ Database file found: /app/data/github_backup.db"
    ls -la /app/data/github_backup.db
else
    echo "❌ Database file not found at /app/data/github_backup.db"
    echo "Directory contents:"
    ls -la /app/data/
fi

# Start the Flask application
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 app:app
