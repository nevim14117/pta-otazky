import csv
import sqlite3
import os

# Paths
CSV_FILE = os.path.join('birds', 'dataset_ptaci_final.csv')
DB_FILE = os.path.join('birds', 'ptaci.db')

def create_database():
    """Create SQLite database and table for birds"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create table with specified columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ptaci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazev TEXT,
            vedecky_nazev TEXT,
            rad TEXT,
            celed TEXT,
            delka_cm INTEGER,
            rozpeti_cm INTEGER,
            hmotnost_g INTEGER,
            status_ohrozeni TEXT,
            typ_potravy TEXT,
            migrace INTEGER,
            vyskyt_kontinent TEXT,
            snuska_ks REAL
        )
    ''')
    
    conn.commit()
    return conn, cursor

def import_csv_to_db(conn, cursor):
    """Read CSV file and insert records into database"""
    try:
        with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            inserted_count = 0
            for row in reader:
                # Map old CSV columns to new database columns
                cursor.execute('''
                    INSERT INTO ptaci (nazev, vedecky_nazev, rad, celed, delka_cm, 
                                       rozpeti_cm, hmotnost_g, status_ohrozeni, typ_potravy, 
                                       migrace, vyskyt_kontinent, snuska_ks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get('Name', ''),
                    row.get('Species', ''),
                    row.get('Family', ''),
                    row.get('Habitat', ''),
                    None,  # delka_cm
                    None,  # rozpeti_cm
                    None,  # hmotnost_g
                    row.get('Conservation_Status', ''),
                    row.get('Diet', ''),
                    None,  # migrace
                    None,  # vyskyt_kontinent
                    None   # snuska_ks
                ))
                inserted_count += 1
            
            conn.commit()
            return inserted_count
    
    except FileNotFoundError:
        print(f"✗ Error: File {CSV_FILE} not found!")
        return 0
    except Exception as e:
        print(f"✗ Error during import: {e}")
        return 0

def verify_import(cursor):
    """Verify the import by displaying stats"""
    try:
        cursor.execute('SELECT COUNT(*) FROM ptaci')
        count = cursor.fetchone()[0]
        print(f"✓ Database contains {count} birds")
        
        cursor.execute('SELECT * FROM ptaci LIMIT 3')
        columns = [description[0] for description in cursor.description]
        print(f"\nColumns: {', '.join(columns)}")
        
        print("\nFirst 3 records:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")
    except Exception as e:
        print(f"✗ Verification error: {e}")

if __name__ == "__main__":
    print("Starting bird database import...\n")
    
    # Create database and table
    conn, cursor = create_database()
    print(f"✓ Database {DB_FILE} created (or already exists)")
    
    # Import CSV data
    imported = import_csv_to_db(conn, cursor)
    
    # Verify import
    if imported > 0:
        print(f"✓ Successfully imported {imported} bird records into {DB_FILE}\n")
        verify_import(cursor)
    else:
        print("✗ No records were imported!")
    
    # Close connection
    conn.close()
    print("\n" + "="*50)
    print(f"Import Summary: {imported} records imported")
    print("="*50)
