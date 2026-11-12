from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Release backup modes: how many of the most recent releases to include (None = all)
RELEASE_MODES = {
    'none': 0,
    'latest': 1,
    'last5': 5,
    'all': None,
}

# Accent colors selectable in Appearance settings.
# primary/primary_2/primary_dark drive the accent gradient and hover states,
# rgb is primary as "r, g, b" for translucent shadows/highlights, and
# link_dark is a lighter variant used for link text on the dark theme so
# darker accents stay readable.
DEFAULT_ACCENT = 'purple'
ACCENT_COLORS = {
    'purple':      {'label': 'Purple',      'primary': '#7c3aed', 'primary_2': '#a855f7', 'primary_dark': '#6423c4', 'rgb': '124, 58, 237', 'link_dark': '#7c3aed'},
    'dark_purple': {'label': 'Dark Purple', 'primary': '#5b21b6', 'primary_2': '#7c3aed', 'primary_dark': '#4c1d95', 'rgb': '91, 33, 182',  'link_dark': '#a78bfa'},
    'red':         {'label': 'Red',         'primary': '#dc2626', 'primary_2': '#f87171', 'primary_dark': '#b91c1c', 'rgb': '220, 38, 38',  'link_dark': '#f87171'},
    'dark_red':    {'label': 'Dark Red',    'primary': '#991b1b', 'primary_2': '#dc2626', 'primary_dark': '#7f1d1d', 'rgb': '153, 27, 27',  'link_dark': '#f87171'},
    'blue':        {'label': 'Blue',        'primary': '#2563eb', 'primary_2': '#60a5fa', 'primary_dark': '#1d4ed8', 'rgb': '37, 99, 235',  'link_dark': '#60a5fa'},
    'indigo':      {'label': 'Indigo',      'primary': '#4f46e5', 'primary_2': '#818cf8', 'primary_dark': '#4338ca', 'rgb': '79, 70, 229',  'link_dark': '#818cf8'},
    'cyan':        {'label': 'Cyan',        'primary': '#0891b2', 'primary_2': '#22d3ee', 'primary_dark': '#0e7490', 'rgb': '8, 145, 178',  'link_dark': '#22d3ee'},
    'teal':        {'label': 'Teal',        'primary': '#0d9488', 'primary_2': '#2dd4bf', 'primary_dark': '#0f766e', 'rgb': '13, 148, 136', 'link_dark': '#2dd4bf'},
    'green':       {'label': 'Green',       'primary': '#16a34a', 'primary_2': '#4ade80', 'primary_dark': '#15803d', 'rgb': '22, 163, 74',  'link_dark': '#4ade80'},
    'orange':      {'label': 'Orange',      'primary': '#ea580c', 'primary_2': '#fb923c', 'primary_dark': '#c2410c', 'rgb': '234, 88, 12',  'link_dark': '#fb923c'},
    'pink':        {'label': 'Pink',        'primary': '#db2777', 'primary_2': '#f472b6', 'primary_dark': '#be185d', 'rgb': '219, 39, 119', 'link_dark': '#f472b6'},
    'slate':       {'label': 'Slate',       'primary': '#475569', 'primary_2': '#64748b', 'primary_dark': '#334155', 'rgb': '71, 85, 105',  'link_dark': '#94a3b8'},
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(10), default='dark')  # 'dark' or 'light'
    accent_color = db.Column(db.String(20), default=DEFAULT_ACCENT)  # key of ACCENT_COLORS
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
    release_mode = db.Column(db.String(10), default='none')  # none, latest, last5, all
    # Custom schedule fields
    custom_interval = db.Column(db.Integer)  # For custom schedule: interval value (e.g., 3 for "every 3 days")
    custom_unit = db.Column(db.String(10))   # For custom schedule: unit (days, weeks, months)
    custom_hour = db.Column(db.Integer, default=2)      # Hour to run backup (0-23)
    custom_minute = db.Column(db.Integer, default=0)    # Minute to run backup (0-59)
    is_active = db.Column(db.Boolean, default=True)
    last_backup = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    backup_jobs = db.relationship('BackupJob', backref='repository', lazy=True, cascade='all, delete-orphan')

    @property
    def owner(self):
        """GitHub owner (user or organization) taken from the repository URL"""
        url = (self.url or '').strip()
        try:
            if url.startswith('git@'):
                # git@github.com:owner/repo.git
                return url.split(':', 1)[1].split('/')[0]
            # https://github.com/owner/repo(.git)
            return url.rstrip('/').split('/')[-2]
        except IndexError:
            return ''

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
