import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from backup_service import BackupService
from models import db, User, Repository, BackupJob
import atexit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////app/data/github_backup.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Diagnostic logging for DB path
db_uri = app.config['SQLALCHEMY_DATABASE_URI']
logger.info(f"Configured DB URI: {db_uri}")
if db_uri.startswith('sqlite:///') or db_uri.startswith('sqlite:////'):
    # Normalize both relative and absolute sqlite URIs
    normalized = db_uri.replace('sqlite:////', '/').replace('sqlite:///', '')
    # If we replaced absolute variant, ensure leading slash retained
    if db_uri.startswith('sqlite:////'):
        sqlite_file = '/' + normalized.lstrip('/')
    else:
        sqlite_file = os.path.abspath(normalized)
    parent = os.path.dirname(sqlite_file)
    try:
        os.makedirs(parent, exist_ok=True)
        stat_parent = os.stat(parent)
        logger.info(f"SQLite file target: {sqlite_file} (parent exists, perms {oct(stat_parent.st_mode)[-3:]})")
    except Exception as e:
        logger.error(f"Failed ensuring SQLite directory {parent}: {e}")

# Initialize extensions
db.init_app(app)

# Immediate connectivity test (runs once at startup)
from sqlalchemy import text
with app.app_context():
    try:
        db.session.execute(text('SELECT 1'))
        logger.info('Initial DB connectivity test succeeded.')
    except Exception as e:
        logger.error(f'Initial DB connectivity test failed: {e}')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize backup service
backup_service = BackupService()

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def dashboard():
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    recent_jobs = BackupJob.query.filter_by(user_id=current_user.id).order_by(BackupJob.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', repositories=repositories, recent_jobs=recent_jobs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Check if this is the first user (admin)
    user_count = User.query.count()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html', first_user=user_count == 0)
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html', first_user=user_count == 0)
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=(user_count == 0)  # First user becomes admin
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Registration successful', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html', first_user=user_count == 0)

@app.route('/repositories')
@login_required
def repositories():
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('repositories.html', repositories=repos)

@app.route('/repositories/add', methods=['GET', 'POST'])
@login_required
def add_repository():
    if request.method == 'POST':
        repo_url = request.form['repo_url']
        github_token = request.form.get('github_token', '')
        backup_format = request.form['backup_format']
        schedule_type = request.form['schedule_type']
        retention_count = int(request.form['retention_count'])
        
        # Extract repo name from URL
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        
        repository = Repository(
            user_id=current_user.id,
            name=repo_name,
            url=repo_url,
            github_token=github_token,
            backup_format=backup_format,
            schedule_type=schedule_type,
            retention_count=retention_count,
            is_active=True
        )
        
        db.session.add(repository)
        db.session.commit()
        
        # Schedule the backup job
        schedule_backup_job(repository)
        
        flash('Repository added successfully', 'success')
        return redirect(url_for('repositories'))
    
    return render_template('add_repository.html')

@app.route('/repositories/<int:repo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_repository(repo_id):
    repository = Repository.query.filter_by(id=repo_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        repository.github_token = request.form.get('github_token', '')
        repository.backup_format = request.form['backup_format']
        repository.schedule_type = request.form['schedule_type']
        repository.retention_count = int(request.form['retention_count'])
        repository.is_active = 'is_active' in request.form
        
        db.session.commit()
        
        # Reschedule the backup job
        scheduler.remove_job(f'backup_{repo_id}', jobstore=None)
        if repository.is_active:
            schedule_backup_job(repository)
        
        flash('Repository updated successfully', 'success')
        return redirect(url_for('repositories'))
    
    return render_template('edit_repository.html', repository=repository)

@app.route('/repositories/<int:repo_id>/delete', methods=['POST'])
@login_required
def delete_repository(repo_id):
    repository = Repository.query.filter_by(id=repo_id, user_id=current_user.id).first_or_404()
    
    # Remove scheduled job
    try:
        scheduler.remove_job(f'backup_{repo_id}')
    except:
        pass
    
    db.session.delete(repository)
    db.session.commit()
    
    flash('Repository deleted successfully', 'success')
    return redirect(url_for('repositories'))

@app.route('/repositories/<int:repo_id>/backup', methods=['POST'])
@login_required
def manual_backup(repo_id):
    repository = Repository.query.filter_by(id=repo_id, user_id=current_user.id).first_or_404()
    
    try:
        backup_service.backup_repository(repository)
        flash('Backup started successfully', 'success')
    except Exception as e:
        logger.error(f"Manual backup failed: {str(e)}")
        flash('Backup failed. Check logs for details.', 'error')
    
    return redirect(url_for('repositories'))

@app.route('/jobs')
@login_required
def backup_jobs():
    jobs = BackupJob.query.filter_by(user_id=current_user.id).order_by(BackupJob.created_at.desc()).all()
    return render_template('backup_jobs.html', jobs=jobs)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

def schedule_backup_job(repository):
    """Schedule a backup job for a repository"""
    if not repository.is_active:
        return
    
    job_id = f'backup_{repository.id}'
    
    # Remove existing job if it exists
    try:
        scheduler.remove_job(job_id)
    except:
        pass
    
    # Create new schedule based on schedule_type
    if repository.schedule_type == 'hourly':
        trigger = CronTrigger(minute=0)
    elif repository.schedule_type == 'daily':
        trigger = CronTrigger(hour=2, minute=0)  # 2 AM daily
    elif repository.schedule_type == 'weekly':
        trigger = CronTrigger(day_of_week=0, hour=2, minute=0)  # Sunday 2 AM
    elif repository.schedule_type == 'monthly':
        trigger = CronTrigger(day=1, hour=2, minute=0)  # 1st of month 2 AM
    else:
        return  # Manual only
    
    scheduler.add_job(
        func=backup_service.backup_repository,
        trigger=trigger,
        args=[repository],
        id=job_id,
        name=f'Backup {repository.name}',
        replace_existing=True
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
