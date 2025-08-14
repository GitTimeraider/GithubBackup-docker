# Deployment Guide

## Quick Deploy to GHCR.io

This project is automatically built and published to GitHub Container Registry (ghcr.io) via GitHub Actions.

### 1. Deploy with Docker Run

```bash
# Get your user and group IDs
USER_ID=$(id -u)
GROUP_ID=$(id -g)

# Create directories for persistent data
mkdir -p ./data ./backups ./logs

# Run the container with proper user/group IDs
docker run -d \
  --name github-backup \
  --restart unless-stopped \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/backups:/app/backups \
  -v $(pwd)/logs:/app/logs \
  -e SECRET_KEY="$(openssl rand -base64 32)" \
  -e PUID=${USER_ID} \
  -e PGID=${GROUP_ID} \
  ghcr.io/gittimeraider/githubbackup:latest
```

### 2. Deploy with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  github-backup:
    image: ghcr.io/gittimeraider/githubbackup:latest
    container_name: github-backup
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:///data/github_backup.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Then run:
```bash
# Set your user/group IDs and secret key
export PUID=$(id -u)
export PGID=$(id -g)
export SECRET_KEY=$(openssl rand -base64 32)
docker-compose up -d
```

### 3. Deploy with Kubernetes

Create a deployment file `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: github-backup
spec:
  replicas: 1
  selector:
    matchLabels:
      app: github-backup
  template:
    metadata:
      labels:
        app: github-backup
    spec:
      containers:
      - name: github-backup
        image: ghcr.io/gittimeraider/githubbackup:latest
        ports:
        - containerPort: 8080
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: github-backup-secret
              key: secret-key
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: backups
          mountPath: /app/backups
        - name: logs
          mountPath: /app/logs
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: github-backup-data
      - name: backups
        persistentVolumeClaim:
          claimName: github-backup-backups
      - name: logs
        persistentVolumeClaim:
          claimName: github-backup-logs
---
apiVersion: v1
kind: Service
metadata:
  name: github-backup-service
spec:
  selector:
    app: github-backup
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer
```

### 4. Environment Configuration

Create a `.env` file for environment variables:

```bash
# Required: Change this in production
SECRET_KEY=your-super-secret-key-here

# User/Group IDs for proper file permissions
PUID=1000  # Your user ID (run 'id -u' to get this)
PGID=1000  # Your group ID (run 'id -g' to get this)

# Optional: Database (defaults to SQLite)
DATABASE_URL=sqlite:///data/github_backup.db

# Optional: Application settings
FLASK_ENV=production
LOG_LEVEL=INFO
```

#### Understanding PUID and PGID

The `PUID` (Process User ID) and `PGID` (Process Group ID) environment variables allow you to run the container with the same user and group IDs as your host system user. This ensures that:

- Files created by the container have the correct ownership
- You can read/write the mounted volumes without permission issues
- Backups are accessible from the host system

To find your IDs:
```bash
# Get your user ID
id -u

# Get your group ID  
id -g

# Get both at once
id
```

**Example output:**
```
uid=1000(username) gid=1000(username) groups=1000(username),4(adm),24(cdrom)...
```

In this case, set `PUID=1000` and `PGID=1000`.

### 5. First Time Setup

1. Access the web interface at `http://localhost:8080`
2. Create the first user account (becomes admin automatically)
3. Add your first repository
4. Configure GitHub Personal Access Token for private repos

### 6. Backup the Application Data

Important directories to backup:
- `./data/` - Contains the database and application data
- `./backups/` - Contains all repository backups
- `./logs/` - Contains application logs

### 7. Monitoring and Maintenance

```bash
# Check container health
docker ps
docker logs github-backup

# View backup jobs
curl http://localhost:8080/health

# Backup the application data
tar -czf backup-$(date +%Y%m%d).tar.gz data/ backups/ logs/
```

### 8. Updating

```bash
# Pull latest image
docker pull ghcr.io/gittimeraider/githubbackup:latest

# Restart with new image
docker-compose down
docker-compose up -d

# Or with docker run
docker stop github-backup
docker rm github-backup
# Run the docker run command again
```

### 9. Troubleshooting

Common issues and solutions:

- **Port 8080 already in use**: Change the port mapping `-p 8081:8080`
- **Permission denied**: Ensure the volumes have correct permissions
- **Database locked**: Stop the container before backing up SQLite database
- **GitHub API rate limits**: Use Personal Access Tokens for higher limits

### 10. Security Considerations

- Change the default `SECRET_KEY`
- Use strong passwords for user accounts
- Regularly update the Docker image
- Monitor access logs
- Backup your data regularly
- Use HTTPS in production (add reverse proxy like nginx)

## Production Deployment with HTTPS

For production, add a reverse proxy:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  github-backup:
    image: ghcr.io/gittimeraider/githubbackup:latest
    container_name: github-backup
    restart: unless-stopped
    expose:
      - "8080"
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
    environment:
      - SECRET_KEY=${SECRET_KEY}
    networks:
      - internal

  nginx:
    image: nginx:alpine
    container_name: github-backup-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - github-backup
    networks:
      - internal

networks:
  internal:
    driver: bridge
```
