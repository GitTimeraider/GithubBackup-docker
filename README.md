UNDER DEVELOPMENT. Do NOT use!

# GitHub Backup Service

A comprehensive web-based solution for backing up GitHub repositories with scheduling, multiple backup formats, and user management.

## Features

- **Web UI with Authentication**: Secure login system with user management
- **Repository Management**: Add, edit, and delete GitHub repositories for backup
- **Multiple Backup Formats**: Support for folder structure, ZIP, and TAR.GZ archives
- **Flexible Scheduling**: Manual, hourly, daily, weekly, and monthly backup schedules
- **Retention Policies**: Configurable backup retention with automatic cleanup
- **Private Repository Support**: Works with GitHub Personal Access Tokens
- **Job Monitoring**: Track backup job status and view error logs
- **Docker Ready**: Fully containerized with health checks

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

5. Create your admin account (first user becomes admin automatically)

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
| `LOG_LEVEL` | Logging level | `INFO` |

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

- **Manual**: Backup only when triggered manually
- **Hourly**: Every hour at minute 0
- **Daily**: Every day at 2:00 AM
- **Weekly**: Every Sunday at 2:00 AM
- **Monthly**: 1st of every month at 2:00 AM

## API Endpoints

- `GET /health` - Health check endpoint
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

- Change the default `SECRET_KEY` in production
- Use strong passwords for user accounts
- GitHub tokens are stored encrypted in the database
- The application runs as non-root user in Docker
- Regular security updates are recommended

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

- View backup job status in the web interface
- Check container health: `docker healthcheck github-backup`
- Monitor logs: `docker logs github-backup`
- Logs are also available in `/app/logs/` directory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
