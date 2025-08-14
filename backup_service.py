import os
import git
import shutil
import zipfile
import tarfile
import logging
from datetime import datetime
from pathlib import Path
from github import Github
from models import db, BackupJob

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self):
        self.backup_base_dir = Path('/app/backups')
        self.backup_base_dir.mkdir(exist_ok=True)
    
    def backup_repository(self, repository):
        """Backup a repository according to its settings"""
        logger.info(f"Starting backup for repository: {repository.name}")
        
        # Create backup job record
        backup_job = BackupJob(
            user_id=repository.user_id,
            repository_id=repository.id,
            status='running',
            started_at=datetime.utcnow()
        )
        db.session.add(backup_job)
        db.session.commit()
        
        try:
            # Create user-specific backup directory
            user_backup_dir = self.backup_base_dir / f"user_{repository.user_id}"
            user_backup_dir.mkdir(exist_ok=True)
            
            # Create repository-specific backup directory
            repo_backup_dir = user_backup_dir / repository.name
            repo_backup_dir.mkdir(exist_ok=True)
            
            # Generate timestamp for this backup
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{repository.name}_{timestamp}"
            
            # Clone repository to temporary location
            temp_clone_dir = repo_backup_dir / f"temp_{timestamp}"
            temp_clone_dir.mkdir(exist_ok=True)
            
            try:
                self._clone_repository(repository, temp_clone_dir)
                
                # Create backup in specified format
                backup_path = self._create_backup(
                    temp_clone_dir, 
                    repo_backup_dir, 
                    backup_name, 
                    repository.backup_format
                )
                
                # Clean up old backups based on retention policy
                self._cleanup_old_backups(repo_backup_dir, repository.retention_count, repository.backup_format)
                
                # Update backup job record
                backup_job.status = 'completed'
                backup_job.backup_path = str(backup_path)
                backup_job.file_size = self._get_file_size(backup_path)
                backup_job.completed_at = datetime.utcnow()
                
                # Update repository last backup time
                repository.last_backup = datetime.utcnow()
                
                logger.info(f"Backup completed successfully: {backup_path}")
                
            finally:
                # Always clean up temporary directory
                if temp_clone_dir.exists():
                    shutil.rmtree(temp_clone_dir)
        
        except Exception as e:
            logger.error(f"Backup failed for repository {repository.name}: {str(e)}")
            backup_job.status = 'failed'
            backup_job.error_message = str(e)
            backup_job.completed_at = datetime.utcnow()
        
        finally:
            db.session.commit()
    
    def _clone_repository(self, repository, clone_dir):
        """Clone a repository to the specified directory"""
        clone_url = repository.url
        
        # If it's a private repository and we have a token, modify the URL
        if repository.github_token and repository.github_token.strip():
            if clone_url.startswith('https://github.com/'):
                # Convert https://github.com/user/repo to https://token@github.com/user/repo
                clone_url = clone_url.replace('https://github.com/', f'https://{repository.github_token}@github.com/')
        
        # Clone the repository
        git.Repo.clone_from(clone_url, clone_dir, depth=1)
        logger.info(f"Repository cloned to: {clone_dir}")
    
    def _create_backup(self, source_dir, backup_dir, backup_name, backup_format):
        """Create backup in the specified format"""
        if backup_format == 'folder':
            # Just copy the folder structure
            backup_path = backup_dir / backup_name
            shutil.copytree(source_dir, backup_path, ignore=shutil.ignore_patterns('.git'))
            return backup_path
            
        elif backup_format == 'zip':
            backup_path = backup_dir / f"{backup_name}.zip"
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for root, dirs, files in os.walk(source_dir):
                    # Skip .git directory
                    if '.git' in dirs:
                        dirs.remove('.git')
                    
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(source_dir)
                        zipf.write(file_path, arcname)
            return backup_path
            
        elif backup_format == 'tar.gz':
            backup_path = backup_dir / f"{backup_name}.tar.gz"
            with tarfile.open(backup_path, 'w:gz') as tarf:
                for root, dirs, files in os.walk(source_dir):
                    # Skip .git directory
                    if '.git' in dirs:
                        dirs.remove('.git')
                    
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(source_dir)
                        tarf.add(file_path, arcname)
            return backup_path
        
        else:
            raise ValueError(f"Unsupported backup format: {backup_format}")
    
    def _cleanup_old_backups(self, backup_dir, retention_count, backup_format):
        """Remove old backups beyond retention count"""
        if backup_format == 'folder':
            pattern = '*'
            backups = [d for d in backup_dir.iterdir() if d.is_dir() and not d.name.startswith('temp_')]
        elif backup_format == 'zip':
            pattern = '*.zip'
            backups = list(backup_dir.glob(pattern))
        elif backup_format == 'tar.gz':
            pattern = '*.tar.gz'
            backups = list(backup_dir.glob(pattern))
        else:
            return
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove backups beyond retention count
        for backup_to_remove in backups[retention_count:]:
            try:
                if backup_to_remove.is_dir():
                    shutil.rmtree(backup_to_remove)
                else:
                    backup_to_remove.unlink()
                logger.info(f"Removed old backup: {backup_to_remove}")
            except Exception as e:
                logger.error(f"Failed to remove old backup {backup_to_remove}: {str(e)}")
    
    def _get_file_size(self, path):
        """Get file or directory size in bytes"""
        path = Path(path)
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return 0
    
    def verify_github_access(self, repo_url, github_token=None):
        """Verify if we can access a GitHub repository"""
        try:
            # Extract owner and repo name from URL
            if 'github.com/' in repo_url:
                parts = repo_url.split('github.com/')[-1].split('/')
                if len(parts) >= 2:
                    owner = parts[0]
                    repo_name = parts[1].replace('.git', '')
                    
                    if github_token:
                        g = Github(github_token)
                    else:
                        g = Github()  # Anonymous access for public repos
                    
                    repo = g.get_repo(f"{owner}/{repo_name}")
                    return True, f"Repository access verified: {repo.full_name}"
            
            return False, "Invalid GitHub repository URL"
            
        except Exception as e:
            return False, f"Repository access failed: {str(e)}"
