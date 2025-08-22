from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(10), default='dark')  # 'dark' or 'light'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    repositories = db.relationship('Repository', backref='user', lazy=True, cascade='all, delete-orphan')
    backup_jobs = db.relationship('BackupJob', backref='user', lazy=True, cascade='all, delete-orphan')

class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    github_token = db.Column(db.String(200))  # For private repos
    backup_format = db.Column(db.String(20), default='folder')  # folder, zip, tar.gz
    schedule_type = db.Column(db.String(20), default='daily')  # manual, hourly, daily, weekly, monthly, custom
    retention_count = db.Column(db.Integer, default=5)  # Number of backups to keep
    # Custom schedule fields
    custom_interval = db.Column(db.Integer)  # For custom schedule: interval value (e.g., 3 for "every 3 days")
    custom_unit = db.Column(db.String(10))   # For custom schedule: unit (days, weeks, months)
    custom_hour = db.Column(db.Integer, default=2)      # Hour to run backup (0-23)
    custom_minute = db.Column(db.Integer, default=0)    # Minute to run backup (0-59)
    is_active = db.Column(db.Boolean, default=True)
    last_backup = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    backup_jobs = db.relationship('BackupJob', backref='repository', lazy=True, cascade='all, delete-orphan')

class BackupJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    repository_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    backup_path = db.Column(db.String(500))
    file_size = db.Column(db.BigInteger)
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PasswordResetCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(32), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)
