"""
SQLite3 Credential Manager for Contract & Invoice Leakage Finder
Directly interacts with the SQLite3 database (.db) to fetch, store, and manage user credentials.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add project root to path for security password hashing
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.security import get_password_hash, verify_password

DB_PATH = os.path.join(ROOT_DIR, "leakage_finder.db")
CREDENTIALS_DB_PATH = os.path.join(ROOT_DIR, "credentials.db")

def get_connection(db_file=DB_PATH):
    """Establishes a raw sqlite3 connection to the database."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_all_credentials(db_file=DB_PATH):
    """Fetches all user credentials directly from the SQLite3 .db database."""
    conn = get_connection(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.hashed_password, o.name as org_name
        FROM users u
        LEFT JOIN organizations o ON u.organization_id = o.id
        ORDER BY u.created_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_credentials_db():
    """
    Creates an isolated credentials.db SQLite3 file and synchronizes all user credentials into it.
    """
    conn_creds = sqlite3.connect(CREDENTIALS_DB_PATH)
    cur_creds = conn_creds.cursor()
    cur_creds.execute("""
        CREATE TABLE IF NOT EXISTS user_credentials (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            hashed_password TEXT NOT NULL,
            demo_password_hint TEXT,
            organization_name TEXT
        )
    """)

    # Fetch from main app db
    main_rows = fetch_all_credentials(DB_PATH)
    for r in main_rows:
        cur_creds.execute("""
            INSERT OR REPLACE INTO user_credentials 
            (id, email, full_name, role, is_active, hashed_password, demo_password_hint, organization_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["id"],
            r["email"],
            r["full_name"],
            r["role"],
            r["is_active"],
            r["hashed_password"],
            "Password123!" if r["email"] in [
                "admin@apexretail.co.uk",
                "manager@apexretail.co.uk",
                "reviewer@apexretail.co.uk",
                "viewer@apexretail.co.uk"
            ] else "Custom user password",
            r["org_name"]
        ))
    conn_creds.commit()
    conn_creds.close()
    print(f"Created & synchronized dedicated credentials database: {CREDENTIALS_DB_PATH}")

def add_or_update_user(email: str, password: str, full_name: str, role: str = "REVIEWER"):
    """Adds or updates a user password across both SQLite databases."""
    import uuid
    hashed = get_password_hash(password)
    email_clean = email.strip().lower()

    # Update main application db
    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, organization_id FROM users WHERE email = ?", (email_clean,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE users SET hashed_password = ?, full_name = ?, role = ? WHERE email = ?", (hashed, full_name, role, email_clean))
        user_id = existing["id"]
    else:
        # Get default organization
        cur.execute("SELECT id FROM organizations LIMIT 1")
        org = cur.fetchone()
        org_id = org["id"] if org else str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, organization_id, email, hashed_password, full_name, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (user_id, org_id, email_clean, hashed, full_name, role))
    conn.commit()
    conn.close()

    # Update credentials.db
    create_credentials_db()
    print(f"Successfully saved credentials for '{email_clean}' in SQLite3 database!")

def print_credentials():
    print(f"\n=======================================================")
    print(f"  ACTIVE APPLICATION DATABASE: {DB_PATH}")
    print(f"  STANDALONE CREDENTIALS DB:   {CREDENTIALS_DB_PATH}")
    print(f"=======================================================")
    users = fetch_all_credentials(DB_PATH)
    if not users:
        print("No users found.")
        return

    print(f"{'Email':<30} | {'Role':<10} | {'Full Name':<35} | {'Status'}")
    print("-" * 88)
    for u in users:
        status = "Active" if u["is_active"] else "Disabled"
        print(f"{u['email']:<30} | {u['role']:<10} | {u['full_name']:<35} | {status}")
    print("-" * 88)
    print("\nDefault demo password for pre-seeded accounts: Password123!\n")

if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "add":
        # Usage: python manage_credentials.py add <email> <password> <full_name> [role]
        email_arg = sys.argv[2]
        pwd_arg = sys.argv[3]
        name_arg = sys.argv[4] if len(sys.argv) > 4 else "New User"
        role_arg = sys.argv[5] if len(sys.argv) > 5 else "REVIEWER"
        add_or_update_user(email_arg, pwd_arg, name_arg, role_arg)
    else:
        create_credentials_db()
        print_credentials()
