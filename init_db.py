import os
from app import app
from models import db

if __name__ == '__main__':
    # Ensure the data directory exists
    data_dir = '/app/data'
    os.makedirs(data_dir, exist_ok=True)
    print(f"Ensured data directory exists: {data_dir}")
    
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
        
        # Verify the database file was created
        db_path = '/app/data/github_backup.db'
        if os.path.exists(db_path):
            print(f"Database file created at: {db_path}")
        else:
            print("Warning: Database file not found after initialization")
