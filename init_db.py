import os
from app import app
from models import db

def ensure_sqlite_path():
    uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    if uri and uri.startswith('sqlite:///'):
        db_file = uri.replace('sqlite:///', '')
        db_dir = os.path.dirname(db_file)
        if db_dir and not os.path.isdir(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created database directory: {db_dir}")
        print(f"Target SQLite file: {db_file}")
        return db_file
    return None

if __name__ == '__main__':
    db_file = ensure_sqlite_path()
    with app.app_context():
        try:
            # Create tables if they don't exist
            db.create_all()
            
            # Update existing users without theme to use dark theme
            from models import User
            users_without_theme = User.query.filter_by(theme=None).all()
            for user in users_without_theme:
                user.theme = 'dark'
            
            if users_without_theme:
                db.session.commit()
                print(f"Updated {len(users_without_theme)} users to use dark theme by default")
            
            print("Database initialized successfully!")
            
            if db_file and os.path.exists(db_file):
                st = os.stat(db_file)
                print(f"Database file created: {db_file} (size {st.st_size} bytes, perms {oct(st.st_mode)[-3:]})")
            elif db_file:
                print(f"Warning: Database file not found yet at {db_file}")
        except Exception as e:
            print(f"Error creating database: {e}")
            raise
