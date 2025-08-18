FROM python:3.13.7-slim

# Set environment variables to prevent interactive prompts and optimize Python
ENV DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PUID=1000 \
    PGID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    zip \
    unzip \
    cron \
    gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --disable-pip-version-check \
    -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions in one layer
RUN mkdir -p /app/backups /app/logs /app/data && \
    chmod +x start.sh && \
    chmod +x entrypoint.sh

# Create user with configurable UID/GID
RUN groupadd -g ${PGID} appuser && \
    useradd -u ${PUID} -g ${PGID} -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch back to root for entrypoint (needed for user/group modifications)
USER root

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["./start.sh"]
