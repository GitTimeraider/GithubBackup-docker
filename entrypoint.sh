#!/bin/bash

# Get PUID and PGID from environment variables, with defaults
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Already running as a non-root user (e.g. `--user 99:100` / `user: "99:100"`).
# No user switching or chown is possible or needed; just run the command.
if [ "$(id -u)" != "0" ]; then
    echo "Running as UID:$(id -u) GID:$(id -g) (container started with --user); skipping PUID/PGID handling"
    # The UID may have no passwd entry/home; give git and friends a writable HOME
    if [ -z "$HOME" ] || [ "$HOME" = "/" ] || [ ! -w "$HOME" ]; then
        export HOME=/tmp
    fi
    for d in /app/data /app/backups /app/logs; do
        if [ ! -w "$d" ]; then
            echo "WARNING: $d is not writable by UID $(id -u). Fix the ownership of the mounted host directory."
        fi
    done
    exec "$@"
fi

# Get current user info
CURRENT_UID=$(id -u appuser)
CURRENT_GID=$(id -g appuser)

# Adjust IDs if needed. -o allows reusing an ID that already exists in the image
# (e.g. GID 100 is the "users" group, as used by Unraid/Synology PGID=100).
if [ "$PUID" != "$CURRENT_UID" ] || [ "$PGID" != "$CURRENT_GID" ]; then
    echo "Updating user appuser to UID:$PUID GID:$PGID"
    if [ "$PGID" != "$CURRENT_GID" ]; then
        groupmod -o -g "$PGID" appuser || echo "WARNING: failed to change appuser GID to $PGID"
    fi
    if [ "$PUID" != "$CURRENT_UID" ]; then
        # usermod also tries to chown the home dir; that part may fail without CAP_CHOWN
        usermod -o -u "$PUID" appuser 2>/dev/null || true
        [ "$(id -u appuser)" = "$PUID" ] || echo "WARNING: failed to change appuser UID to $PUID"
    fi
    chown -R appuser:appuser /home/appuser 2>/dev/null || true
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

# Switching users requires CAP_SETUID and CAP_SETGID. They are missing when the
# container is started with --cap-drop=ALL (or cap_drop: [ALL]).
if ! gosu appuser true 2>/dev/null; then
    cat >&2 <<EOF
ERROR: cannot switch to appuser (UID:$PUID GID:$PGID): the container lacks the
SETUID/SETGID capabilities (probably started with --cap-drop=ALL).

Fix it in one of two ways:
  1. Add back the capabilities the entrypoint needs:
       --cap-drop=ALL --cap-add=SETUID --cap-add=SETGID --cap-add=CHOWN --cap-add=DAC_OVERRIDE --cap-add=FOWNER
  2. Or run directly as your user and skip the switch entirely:
       --cap-drop=ALL --user $PUID:$PGID
     (the mounted data/backups/logs directories must then be owned by $PUID:$PGID on the host)
EOF
    exit 1
fi

echo "Switching to appuser..."
exec gosu appuser "$@"
