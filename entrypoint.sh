#!/bin/bash

# Get PUID and PGID from environment variables, with defaults
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Get current user info
CURRENT_UID=$(id -u appuser)
CURRENT_GID=$(id -g appuser)

# Only modify user/group if they're different from current
if [ "$PUID" != "$CURRENT_UID" ] || [ "$PGID" != "$CURRENT_GID" ]; then
    echo "Updating user appuser to UID:$PUID and GID:$PGID"
    
    # Update group ID if needed
    if [ "$PGID" != "$CURRENT_GID" ]; then
        groupmod -g "$PGID" appuser
    fi
    
    # Update user ID if needed
    if [ "$PUID" != "$CURRENT_UID" ]; then
        usermod -u "$PUID" appuser
    fi
    
    # Fix ownership of app directory
    chown -R appuser:appuser /app
    
    # Fix ownership of mounted volumes if they exist
    [ -d /app/data ] && chown -R appuser:appuser /app/data
    [ -d /app/backups ] && chown -R appuser:appuser /app/backups
    [ -d /app/logs ] && chown -R appuser:appuser /app/logs
fi

# Switch to appuser and execute the original command
exec gosu appuser "$@"
