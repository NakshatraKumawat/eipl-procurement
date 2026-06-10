import sqlite3

# Change 'inventory.db' to match your actual database filename if it is named differently
db_filename = "inventory.db" 

try:
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    # Add the missing Excel-feature columns to the items table
    print("Adding missing columns to the items table...")
    
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN category TEXT DEFAULT 'Consumables';")
        print("-> Added 'category' column successfully.")
    except sqlite3.OperationalError:
        print("-> 'category' column already exists.")
        
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN supplier TEXT DEFAULT 'Approved Vendor';")
        print("-> Added 'supplier' column successfully.")
    except sqlite3.OperationalError:
        print("-> 'supplier' column already exists.")
        
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN storage_site TEXT DEFAULT 'Store Yard';")
        print("-> Added 'storage_site' column successfully.")
    except sqlite3.OperationalError:
        print("-> 'storage_site' column already exists.")

    conn.commit()
    conn.close()
    print("\nDatabase columns successfully updated! You can now restart your application.")

except Exception as e:
    print(f"An error occurred: {e}")