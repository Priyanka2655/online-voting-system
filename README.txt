ONLINE VOTING SYSTEM - PYTHON FLASK + MYSQL
===========================================

FEATURES
--------
1. Voter registration and login
2. Admin login
3. Admin can add candidates and party names
4. Voter can vote only once (enforced by a UNIQUE database constraint)
5. Admin dashboard shows voter count, votes cast and candidate-wise results
6. Passwords are stored as secure password hashes

REQUIREMENTS
------------
- Python 3.9 or newer
- MySQL Server 8.x (or compatible)
- VS Code (recommended)

SETUP (WINDOWS / VS CODE)
-------------------------
1. Extract the ZIP file.
2. Open the extracted Online_Voting_System_Flask_MySQL folder in VS Code.
3. Start MySQL Server.
4. Open MySQL Workbench or MySQL Command Line Client.
5. Run the complete schema.sql file. It creates the online_voting database and tables.
6. Open VS Code Terminal in the project folder and run:

   py -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt

7. IMPORTANT: If your MySQL root account has a password, edit create_admin.py
   and set password="YOUR_MYSQL_PASSWORD". If root has no password, leave it "".
8. Create the admin account:

   python create_admin.py

   Enter the admin name, username and password when prompted.

9. If your MySQL root account has a password, also set DB_PASSWORD before starting:
   PowerShell:
   $env:DB_PASSWORD="YOUR_MYSQL_PASSWORD"

   If root has no password, no change is required.

10. Run the project:

   python app.py

11. Open this address in your browser:
   http://127.0.0.1:5000

LOGIN / TESTING
---------------
- First create an admin using create_admin.py.
- Log in with the admin username and password you just created.
- Add candidates from the Admin Dashboard.
- Register a voter using the Register page.
- Log in as the voter and cast one vote.
- Log back in as admin to see the results.

TROUBLESHOOTING
---------------
- "Access denied for user root": Check the MySQL password in create_admin.py
  and the DB_PASSWORD environment variable.
- "Unknown database online_voting": Run schema.sql in MySQL.
- "Can't connect to MySQL server": Start the MySQL80 service / MySQL Server.
- "No module named mysql": Activate venv and run pip install -r requirements.txt.

NOTE
----
This is an educational/demo project for local college use. It is not certified
for real public elections. Before any real deployment, add HTTPS, CSRF protection,
audit/security review, stronger identity verification and production configuration.
