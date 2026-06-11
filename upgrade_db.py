import sqlite3
import os

# Define the absolute target database file configuration path
DB_PATH = "inventory.db"

if not os.path.exists(DB_PATH):
    print(f"Error: Could not locate '{DB_PATH}' in this workspace folder.")
else:
    # Open direct execution tunnel pipeline connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Initiating schema extension migration queries...")
    
    try:
        # 1. Inject 'is_new_item' column safely with Boolean 0 (False) default status values
        cursor.execute("ALTER TABLE procurement_requests ADD COLUMN is_new_item BOOLEAN DEFAULT 0;")
        print(" -> Added 'is_new_item' column successfully.")
    except sqlite3.OperationalError as e:
        print(f" -> 'is_new_item' notice: {e} (It may already exist)")

    try:
        # 2. Inject 'new_item_name' nullable string column
        cursor.execute("ALTER TABLE procurement_requests ADD COLUMN new_item_name TEXT;")
        print(" -> Added 'new_item_name' column successfully.")
    except sqlite3.OperationalError as e:
        print(f" -> 'new_item_name' notice: {e}")

    try:
        # 3. Inject 'detailed_specification' nullable string column
        cursor.execute("ALTER TABLE procurement_requests ADD COLUMN detailed_specification TEXT;")
        print(" -> Added 'detailed_specification' column successfully.")
    except sqlite3.OperationalError as e:
        print(f" -> 'detailed_specification' notice: {e}")

    # Commit transactions permanently and sever connections
    conn.commit()
    conn.close()
    print("\nDatabase structure upgraded successfully! You can now safely delete this script.")