# GitHub Backup Service Configuration

# Docker image configuration for GHCR.io deployment
# This file contains additional deployment configurations

# Health check configuration
HEALTHCHECK_INTERVAL = "30s"
HEALTHCHECK_TIMEOUT = "10s"
HEALTHCHECK_RETRIES = 3

# Application performance
GUNICORN_WORKERS = 4
GUNICORN_TIMEOUT = 120
GUNICORN_BIND = "0.0.0.0:8080"

# Backup settings
DEFAULT_RETENTION_COUNT = 5
MAX_RETENTION_COUNT = 50
BACKUP_TIMEOUT = 300

# GitHub API settings
GITHUB_API_TIMEOUT = 30
GITHUB_CLONE_TIMEOUT = 600

# Security settings
SESSION_TIMEOUT = 3600
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300
