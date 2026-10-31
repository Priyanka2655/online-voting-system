from werkzeug.security import generate_password_hash
import mysql.connector
from getpass import getpass

print("Create an administrator account")
name = input("Admin full name: ").strip()
username = input("Admin username: ").strip()
password = getpass("Admin password (minimum 6 characters): ")
if not name or not username or len(password) < 6:
    raise SystemExit("Please enter valid details. Password must be at least 6 characters.")

conn = mysql.connector.connect(
    host="localhost", user="root", password="Piya@123", database="online_voting"
)
cur = conn.cursor()
try:
    cur.execute(
        "INSERT INTO users (name, username, password_hash, role) VALUES (%s,%s,%s,'admin')",
        (name, username, generate_password_hash(password))
    )
    conn.commit()
    print("Admin account created. You can now log in.")
except mysql.connector.IntegrityError:
    print("That username already exists.")
finally:
    cur.close()
    conn.close()
