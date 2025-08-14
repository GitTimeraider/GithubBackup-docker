#!/bin/bash

# Get PUID and PGID from environment variables, with defaults
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Get current user info
CURRENT_UID=$(id -u appuser)
CURRENT_GID=$(id -g appuser)

# Adjust IDs if needed
if [ "$PUID" != "$CURRENT_UID" ] || [ "$PGID" != "$CURRENT_GID" ]; then
    echo "Updating user appuser to UID:$PUID GID:$PGID"
    [ "$PGID" != "$CURRENT_GID" ] && groupmod -g "$PGID" appuser
    [ "$PUID" != "$CURRENT_UID" ] && usermod -u "$PUID" appuser
fi

# Always ensure directories exist and are owned correctly (important for SQLite write access)
for d in /app/data /app/backups /app/logs; do
    mkdir -p "$d"
    chown -R appuser:appuser "$d" 2>/dev/null || true
    chmod 775 "$d" 2>/dev/null || true
done

# Ensure app code ownership (helps when mounting volumes)
chown -R appuser:appuser /app 2>/dev/null || true

echo "Directory permissions:"
ls -ld /app/data /app/backups /app/logs 2>/dev/null || true

echo "Switching to appuser..."
exec gosu appuser "$@"
