# GitHub Backup Service
### Disclaimer: AI is probably resposible for over half of the coding. Does that mean it does not work? Ofcourse not. Just an FYI.
<p align="center" width="100%">
    <img width="33%" src="https://github.com/GitTimeraider/Assets/blob/main/GithubBackup-docker/img/ghbackup_icon.png">
</p>
A comprehensive web-based solution for backing up GitHub repositories with scheduling, multiple backup formats, and user management.

<p align="center" width="100%">
    <img width="100%" src="https://github.com/GitTimeraider/Assets/blob/main/GithubBackup-docker/img/dashboard3.jpg">
</p>

## Features

- **Web UI with Authentication**: Secure login system with automatic admin user creation
- **Password Reset System**: Forgot password functionality with server-logged reset codes
- **Repository Management**: Add, edit, delete, and manually trigger backups for GitHub repositories
- **Multiple Backup Formats**: Support for folder structure, ZIP, and TAR.GZ archives
- **Flexible Scheduling**: 
  - Manual backup triggering
  - Predefined schedules: Hourly, Daily (2 AM), Weekly (Sunday 2 AM), Monthly (1st, 2 AM)
  - Custom schedules: Every X days/weeks/months at specified time
    
<p align="center" width="100%">
    <img width="100%" src="https://github.com/GitTimeraider/Assets/blob/main/GithubBackup-docker/img/add.jpg">
</p>

- **Retention Policies**: Configurable backup retention (1-50 versions) with automatic cleanup
- **Private Repository Support**: Works with GitHub Personal Access Tokens
- **Dashboard Overview**: Statistics cards showing repository count, active repos, completed and failed jobs
- **Job Monitoring**: 
  - Real-time backup job status tracking (running, completed, failed)
  - Detailed backup job history with timestamps
  - Recent jobs display on dashboard

<p align="center" width="100%">
    <img width="100%" src="https://github.com/GitTimeraider/Assets/blob/main/GithubBackup-docker/img/jobs.jpg">
</p>

- **User Settings**: Change username and password functionality
- **Docker Ready**: Fully containerized with health checks and proper user permissions

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/GitTimeraider/GithubBackup.git
cd GithubBackup
```

2. Copy and modify the environment file:
```bash
cp .env.example .env
# Edit .env with your preferred settings
```

3. Start the service:
```bash
docker-compose up -d
```

4. Access the web interface at `http://localhost:8080`

5. Login with default credentials (created automatically):
   - **Username**: `admin`
   - **Password**: `changeme`
   - ⚠️ **Important**: Change the default password immediately after first login via Settings

### Using Pre-built Docker Image

```bash
docker run -d \
  --name github-backup \
  -p 8080:8080 \
  -v ./data:/app/data \
  -v ./backups:/app/backups \
  -v ./logs:/app/logs \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/gittimeraider/githubbackup:latest
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `dev-secret-key-change-in-production` |
| `DATABASE_URL` | SQLite database file path | `sqlite:////app/data/github_backup.db` |
| `PUID` | User ID for file permissions | `1000` |
| `PGID` | Group ID for file permissions | `1000` |

### GitHub Token Setup

For private repositories, you'll need a GitHub Personal Access Token:

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with `repo` scope for private repositories
3. Add the token when configuring repositories in the web UI

## Backup Formats

- **Folder Structure**: Preserves the original repository structure
- **ZIP Archive**: Compressed archive with good compression ratio
- **TAR.GZ Archive**: Unix-style compressed archive with excellent compression

## Scheduling Options

- **Manual**: Backup only when triggered manually via the web interface
- **Hourly**: Every hour at minute 0
- **Daily**: Every day at 2:00 AM
- **Weekly**: Every Sunday at 2:00 AM  
- **Monthly**: 1st of every month at 2:00 AM
- **Custom**: Every X days/weeks/months at a specified time
  - Days: 1-365 day intervals
  - Weeks: 1-52 week intervals  
  - Months: 1-12 month intervals
  - Custom time selection (24-hour format)

## Web Interface

The application provides a modern, responsive web interface with:

### Dashboard
- Repository statistics (total, active, completed backups, failed jobs)
- Recent repositories overview with status indicators
- Recent backup jobs with real-time status
- Quick access to add new repositories

### Repository Management
- Add repositories with GitHub URL
- Configure backup format (Folder, ZIP, TAR.GZ)
- Set up scheduling (predefined or custom intervals)
- Configure retention policies (1-50 backup versions)
- Edit repository settings
- Manual backup triggering
- Repository activation/deactivation

### Backup Jobs
- Real-time job status monitoring
- Complete backup history with timestamps
- Job status indicators (running, completed, failed)
- Auto-refresh for running jobs

### User Management
- Secure login system
- Password reset functionality (codes logged to server)
- User settings (change username/password)
- Automatic admin user creation on first run

## API Endpoints

- `GET /health` - Health check endpoint for monitoring
- `GET /favicon.ico` - Application favicon
- Web interface available at `/` (requires authentication)

## Development

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize database:
```bash
python init_db.py
```

3. Run the application:
```bash
python app.py
```

### Building Docker Image

```bash
docker build -t github-backup .
```

## Security Considerations

- **Change default credentials**: The application creates a default admin user (`admin`/`changeme`) - change this immediately
- **Change the SECRET_KEY**: Use a strong, unique secret key in production
- **Use strong passwords**: Enforce strong passwords for all user accounts
- **GitHub tokens**: Personal Access Tokens are stored in the database for private repository access
- **Container security**: The application runs as non-root user in Docker with configurable PUID/PGID
- **Regular updates**: Keep the application and dependencies updated for security patches
- **Password reset**: Reset codes are logged to server logs for manual distribution

## Backup Storage

Backups are organized as follows:
```
/app/backups/
├── user_1/
│   ├── repository1/
│   │   ├── repository1_20241214_020000.zip
│   │   └── repository1_20241213_020000.zip
│   └── repository2/
│       └── repository2_20241214_020000/
└── user_2/
    └── ...
```

## Monitoring

- **Web Interface**: Real-time backup job status and repository management
- **Dashboard**: Visual overview of repository count, active repos, and job statistics  
- **Job History**: Complete backup job history with timestamps and status
- **Container Health**: `docker healthcheck github-backup`
- **Application Logs**: `docker logs github-backup`
- **Persistent Logs**: Available in `/app/logs/` directory inside container
- **Health Endpoint**: `GET /health` returns JSON status for external monitoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
