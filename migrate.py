from database import engine
from sqlalchemy import text, inspect

def add_missing_columns():
    with engine.connect() as ctx:
        # Check what columns already exist in the employees table
        inspector = inspect(engine)
        existing_columns = [col['name'] for col in inspector.get_columns('employees')]
        
        # Add 'location' if it doesn't exist
        if 'location' not in existing_columns:
            ctx.execute(text("ALTER TABLE employees ADD COLUMN location TEXT DEFAULT 'Not Specified';"))
            print("Successfully added column: location")
        else:
            print("Column 'location' already exists. Skipping...")
            
        # Add 'contact' if it doesn't exist
        if 'contact' not in existing_columns:
            ctx.execute(text("ALTER TABLE employees ADD COLUMN contact TEXT DEFAULT 'Not Specified';"))
            print("Successfully added column: contact")
        else:
            print("Column 'contact' already exists. Skipping...")
            
        ctx.commit()

if __name__ == "__main__":
    add_missing_columns()