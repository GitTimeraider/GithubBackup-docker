import os
from datetime import datetime, timedelta
import pytz
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from backup_service import BackupService
from models import db, User, Repository, BackupJob, PasswordResetCode
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

# Set APScheduler logging level to DEBUG for better debugging
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

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

# Configure local timezone detection
def get_local_timezone():
    """Detect the local system timezone"""
    # Try environment variable first (Docker/container support)
    tz_env = os.environ.get('TZ')
    if tz_env:
        try:
            return pytz.timezone(tz_env)
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone in TZ environment variable: {tz_env}")
    
    # Try system timezone
    try:
        # Get system timezone
        local_tz_name = time.tzname[time.daylight] if time.daylight else time.tzname[0]
        if local_tz_name:
            # Try to map common abbreviations to full timezone names
            tz_mapping = {
                'CET': 'Europe/Amsterdam',
                'CEST': 'Europe/Amsterdam', 
                'EST': 'America/New_York',
                'EDT': 'America/New_York',
                'PST': 'America/Los_Angeles',
                'PDT': 'America/Los_Angeles',
                'UTC': 'UTC',
                'GMT': 'UTC'
            }
            
            full_tz_name = tz_mapping.get(local_tz_name, local_tz_name)
            return pytz.timezone(full_tz_name)
    except:
        pass
    
    # Fallback to UTC
    logger.warning("Could not detect local timezone, using UTC")
    return pytz.UTC

LOCAL_TZ = get_local_timezone()
logger.info(f"Using timezone: {LOCAL_TZ}")

def to_local_time(utc_dt):
    """Convert UTC datetime to local time"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(LOCAL_TZ)

# Add Jinja2 filters
@app.template_filter('local_time')
def local_time_filter(utc_dt):
    """Jinja2 filter to convert UTC time to local time"""
    return to_local_time(utc_dt)

@app.template_filter('format_local_time')
def format_local_time_filter(utc_dt, format_str='%Y-%m-%d %H:%M'):
    """Jinja2 filter to format UTC time as local time"""
    local_dt = to_local_time(utc_dt)
    if local_dt is None:
        return "Never"
    
    # Get timezone abbreviation
    tz_name = local_dt.strftime('%Z')
    if not tz_name:  # Fallback if %Z doesn't work
        tz_name = str(LOCAL_TZ).split('/')[-1] if '/' in str(LOCAL_TZ) else str(LOCAL_TZ)
    
    return f"{local_dt.strftime(format_str)} {tz_name}"

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

def schedule_all_repositories():
    """Schedule all active repositories on startup"""
    try:
        repositories = Repository.query.filter_by(is_active=True).all()
        scheduled_count = 0
        for repository in repositories:
            if repository.schedule_type != 'manual':
                schedule_backup_job(repository)
                scheduled_count += 1
                logger.info(f"Scheduled backup job for repository: {repository.name} ({repository.schedule_type})")
        logger.info(f"Scheduled {scheduled_count} backup jobs on startup")
    except Exception as e:
        logger.error(f"Error scheduling repositories on startup: {e}")

# Flag to ensure we only initialize once
_scheduler_initialized = False

def ensure_scheduler_initialized():
    """Ensure scheduler is initialized with existing repositories"""
    global _scheduler_initialized
    if not _scheduler_initialized:
        schedule_all_repositories()
        _scheduler_initialized = True

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def dashboard():
    ensure_scheduler_initialized()
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    recent_jobs = BackupJob.query.filter_by(user_id=current_user.id).order_by(BackupJob.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', repositories=repositories, recent_jobs=recent_jobs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Auto-create default admin if no users
    if User.query.count() == 0:
        admin = User(username='admin', password_hash=generate_password_hash('changeme'), is_admin=True, theme='dark')
        db.session.add(admin)
        db.session.commit()
        logger.warning('Default admin user created with username=admin password=changeme; please change immediately.')
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

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    if request.method == 'POST':
        # Handle theme change
        theme = request.form.get('theme')
        if theme in ['dark', 'light']:
            current_user.theme = theme
            flash('Appearance settings updated', 'success')
            db.session.commit()
            return redirect(url_for('user_settings'))
        
        # Handle account changes
        new_username = request.form.get('username', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Change username
        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash('Username already taken', 'error')
                return redirect(url_for('user_settings'))
            current_user.username = new_username
            flash('Username updated', 'success')

        # Change password
        if new_password:
            if not check_password_hash(current_user.password_hash, current_password):
                flash('Current password incorrect', 'error')
                return redirect(url_for('user_settings'))
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return redirect(url_for('user_settings'))
            current_user.password_hash = generate_password_hash(new_password)
            flash('Password updated', 'success')

        db.session.commit()
        return redirect(url_for('user_settings'))

    return render_template('settings.html')

import secrets

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('If that user exists, a reset code has been generated (check logs).', 'info')
            return redirect(url_for('forgot_password'))
        # Invalidate previous unused codes for this user
        PasswordResetCode.query.filter_by(user_id=user.id, used=False).delete()
        code = secrets.token_hex(4)
        prc = PasswordResetCode(user_id=user.id, code=code)
        db.session.add(prc)
        db.session.commit()
        logger.warning(f'PASSWORD RESET CODE for user={user.username}: {code}')
        flash('Reset code generated. Check server logs.', 'info')
        return redirect(url_for('reset_password'))
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        code = request.form.get('code', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Invalid code or user', 'error')
            return redirect(url_for('reset_password'))
        prc = PasswordResetCode.query.filter_by(user_id=user.id, code=code, used=False).first()
        if not prc:
            flash('Invalid or already used code', 'error')
            return redirect(url_for('reset_password'))
        if new_password != confirm_password or not new_password:
            flash('Passwords do not match or empty', 'error')
            return redirect(url_for('reset_password'))
        user.password_hash = generate_password_hash(new_password)
        prc.used = True
        db.session.commit()
        flash('Password reset successful. You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html')

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
        
        # Handle custom schedule fields
        custom_interval = None
        custom_unit = None
        custom_hour = 2
        custom_minute = 0
        
        if schedule_type == 'custom':
            custom_interval = int(request.form.get('custom_interval', 1))
            custom_unit = request.form.get('custom_unit', 'days')
            custom_time = request.form.get('custom_time', '02:00')
            
            # Validate custom schedule parameters
            if custom_unit == 'days' and (custom_interval < 1 or custom_interval > 365):
                flash('Custom interval for days must be between 1 and 365', 'error')
                return render_template('add_repository.html')
            elif custom_unit == 'weeks' and (custom_interval < 1 or custom_interval > 52):
                flash('Custom interval for weeks must be between 1 and 52', 'error')
                return render_template('add_repository.html')
            elif custom_unit == 'months' and (custom_interval < 1 or custom_interval > 12):
                flash('Custom interval for months must be between 1 and 12', 'error')
                return render_template('add_repository.html')
            
            try:
                time_parts = custom_time.split(':')
                custom_hour = int(time_parts[0])
                custom_minute = int(time_parts[1])
                
                if custom_hour < 0 or custom_hour > 23:
                    flash('Hour must be between 0 and 23', 'error')
                    return render_template('add_repository.html')
                if custom_minute < 0 or custom_minute > 59:
                    flash('Minute must be between 0 and 59', 'error')
                    return render_template('add_repository.html')
                    
            except (IndexError, ValueError):
                flash('Invalid time format. Please use HH:MM format', 'error')
                return render_template('add_repository.html')
        
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
            custom_interval=custom_interval,
            custom_unit=custom_unit,
            custom_hour=custom_hour,
            custom_minute=custom_minute,
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
        
        # Handle custom schedule fields
        if repository.schedule_type == 'custom':
            custom_interval = int(request.form.get('custom_interval', 1))
            custom_unit = request.form.get('custom_unit', 'days')
            custom_time = request.form.get('custom_time', '02:00')
            
            # Validate custom schedule parameters
            if custom_unit == 'days' and (custom_interval < 1 or custom_interval > 365):
                flash('Custom interval for days must be between 1 and 365', 'error')
                return render_template('edit_repository.html', repository=repository)
            elif custom_unit == 'weeks' and (custom_interval < 1 or custom_interval > 52):
                flash('Custom interval for weeks must be between 1 and 52', 'error')
                return render_template('edit_repository.html', repository=repository)
            elif custom_unit == 'months' and (custom_interval < 1 or custom_interval > 12):
                flash('Custom interval for months must be between 1 and 12', 'error')
                return render_template('edit_repository.html', repository=repository)
            
            repository.custom_interval = custom_interval
            repository.custom_unit = custom_unit
            
            try:
                time_parts = custom_time.split(':')
                repository.custom_hour = int(time_parts[0])
                repository.custom_minute = int(time_parts[1])
                
                if repository.custom_hour < 0 or repository.custom_hour > 23:
                    flash('Hour must be between 0 and 23', 'error')
                    return render_template('edit_repository.html', repository=repository)
                if repository.custom_minute < 0 or repository.custom_minute > 59:
                    flash('Minute must be between 0 and 59', 'error')
                    return render_template('edit_repository.html', repository=repository)
                    
            except (IndexError, ValueError):
                flash('Invalid time format. Please use HH:MM format', 'error')
                return render_template('edit_repository.html', repository=repository)
        else:
            # Reset custom fields when not using custom schedule
            repository.custom_interval = None
            repository.custom_unit = None
            repository.custom_hour = 2
            repository.custom_minute = 0
        
        db.session.commit()
        
        # Reschedule the backup job
        try:
            scheduler.remove_job(f'backup_{repo_id}', jobstore=None)
        except:
            pass
        
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
        # Manual backups are already in app context, so no wrapper needed
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
    has_running = any(job.status == 'running' for job in jobs)
    return render_template('backup_jobs.html', jobs=jobs, has_running=has_running)

@app.route('/health')
def health_check():
    local_time = datetime.now(LOCAL_TZ)
    utc_time = datetime.utcnow()
    return jsonify({
        'status': 'healthy', 
        'utc_time': utc_time.isoformat(),
        'local_time': local_time.isoformat(),
        'timezone': str(LOCAL_TZ),
        'timezone_name': local_time.strftime('%Z')
    })

@app.route('/api/scheduler/status')
@login_required
def scheduler_status():
    """Debug endpoint to check scheduled jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    return jsonify({
        'scheduler_running': scheduler.running,
        'scheduled_jobs': jobs,
        'total_jobs': len(jobs)
    })

@app.route('/api/test-backup/<int:repo_id>', methods=['POST'])
@login_required
def test_scheduled_backup(repo_id):
    """Test endpoint to simulate a scheduled backup (for debugging)"""
    repository = Repository.query.filter_by(id=repo_id, user_id=current_user.id).first_or_404()
    
    def test_backup_with_context():
        with app.app_context():
            try:
                # Refresh the repository object to ensure it's bound to the current session
                repo = Repository.query.get(repository.id)
                if repo and repo.is_active:
                    backup_service.backup_repository(repo)
                    return "Backup completed successfully"
                else:
                    return f"Repository {repository.id} not found or inactive"
            except Exception as e:
                logger.error(f"Error in test backup for repository {repository.id}: {e}")
                return f"Error: {str(e)}"
    
    try:
        result = test_backup_with_context()
        return jsonify({'success': True, 'message': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/theme', methods=['POST'])
@login_required
def update_theme():
    data = request.get_json()
    theme = data.get('theme')
    
    if theme in ['dark', 'light']:
        current_user.theme = theme
        db.session.commit()
        return jsonify({'success': True, 'theme': theme})
    
    return jsonify({'success': False, 'error': 'Invalid theme'}), 400

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'), 'ghbackup_ico.ico', mimetype='image/vnd.microsoft.icon')

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
    
    # Create a wrapper function that includes Flask app context
    def backup_with_context():
        with app.app_context():
            try:
                # Refresh the repository object to ensure it's bound to the current session
                repo = Repository.query.get(repository.id)
                if repo and repo.is_active:
                    backup_service.backup_repository(repo)
                else:
                    logger.warning(f"Repository {repository.id} not found or inactive, skipping backup")
            except Exception as e:
                logger.error(f"Error in scheduled backup for repository {repository.id}: {e}")
    
    # Create new schedule based on schedule_type
    if repository.schedule_type == 'hourly':
        trigger = CronTrigger(minute=0, timezone=LOCAL_TZ)
    elif repository.schedule_type == 'daily':
        trigger = CronTrigger(hour=2, minute=0, timezone=LOCAL_TZ)  # 2 AM local time
    elif repository.schedule_type == 'weekly':
        trigger = CronTrigger(day_of_week=0, hour=2, minute=0, timezone=LOCAL_TZ)  # Sunday 2 AM local time
    elif repository.schedule_type == 'monthly':
        trigger = CronTrigger(day=1, hour=2, minute=0, timezone=LOCAL_TZ)  # 1st of month 2 AM local time
    elif repository.schedule_type == 'custom':
        # Handle custom schedule
        hour = repository.custom_hour or 2
        minute = repository.custom_minute or 0
        interval = repository.custom_interval or 1
        unit = repository.custom_unit or 'days'
        
        if unit == 'days':
            # For daily intervals, use interval_trigger if more than 1 day
            if interval == 1:
                trigger = CronTrigger(hour=hour, minute=minute, timezone=LOCAL_TZ)  # Daily
            else:
                # Use interval trigger for multi-day schedules
                from apscheduler.triggers.interval import IntervalTrigger
                from datetime import datetime, time
                # Calculate next run time at the specified hour/minute in local timezone
                now = datetime.now(LOCAL_TZ)
                start_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if start_date <= now:
                    start_date = start_date + timedelta(days=1)
                trigger = IntervalTrigger(days=interval, start_date=start_date, timezone=LOCAL_TZ)
        elif unit == 'weeks':
            # For weekly intervals
            if interval == 1:
                trigger = CronTrigger(day_of_week=0, hour=hour, minute=minute, timezone=LOCAL_TZ)  # Every Sunday
            else:
                from apscheduler.triggers.interval import IntervalTrigger
                from datetime import datetime
                now = datetime.now(LOCAL_TZ)
                start_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # Find next Sunday
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and start_date <= now:
                    days_until_sunday = 7
                start_date = start_date + timedelta(days=days_until_sunday)
                trigger = IntervalTrigger(weeks=interval, start_date=start_date, timezone=LOCAL_TZ)
        elif unit == 'months':
            # For monthly intervals
            if interval == 1:
                trigger = CronTrigger(day=1, hour=hour, minute=minute, timezone=LOCAL_TZ)  # 1st of every month
            else:
                from apscheduler.triggers.interval import IntervalTrigger
                from datetime import datetime
                now = datetime.now(LOCAL_TZ)
                start_date = now.replace(day=1, hour=hour, minute=minute, second=0, microsecond=0)
                if start_date <= now:
                    # Move to next month
                    if start_date.month == 12:
                        start_date = start_date.replace(year=start_date.year + 1, month=1)
                    else:
                        start_date = start_date.replace(month=start_date.month + 1)
                # Note: Using weeks approximation for months since APScheduler doesn't have months interval
                trigger = IntervalTrigger(weeks=interval*4, start_date=start_date, timezone=LOCAL_TZ)
        else:
            return  # Invalid unit
    else:
        return  # Manual only
    
    scheduler.add_job(
        func=backup_with_context,  # Use the wrapper function instead
        trigger=trigger,
        id=job_id,
        name=f'Backup {repository.name}',
        replace_existing=True
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
