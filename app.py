import os
from io import BytesIO
from functools import wraps

import mysql.connector
from mysql.connector import Error

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet

from openpyxl import Workbook

# =====================================================
# FLASK CONFIGURATION
# =====================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key-before-deployment"
)


# =====================================================
# MYSQL CONFIGURATION
# =====================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Piya@123"),
    "database": os.getenv("DB_NAME", "online_voting"),
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# =====================================================
# LOGIN REQUIRED DECORATOR
# =====================================================

def login_required(role=None):

    def decorator(view):

        @wraps(view)
        def wrapped(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            if role and session.get("role") != role:
                flash("You are not authorized to open that page.", "error")
                return redirect(url_for("home"))

            return view(*args, **kwargs)

        return wrapped

    return decorator


# =====================================================
# COMMON LOGIN FUNCTION
# =====================================================

def authenticate_user(admin_only=False):

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cur.fetchone()

    finally:
        cur.close()
        conn.close()

    if user and check_password_hash(user["password_hash"], password):

        if admin_only and user["role"] != "admin":
            flash("Only administrators can log in here.", "error")
            return None

        session.clear()

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        return user

    return None


# =====================================================
# HOME PAGE
# =====================================================

@app.route("/")
def home():

    return render_template("home.html")


# =====================================================
# VOTER REGISTRATION
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not name or not username or len(password) < 6:

            flash(
                "Enter all details. Password must contain at least 6 characters.",
                "error"
            )

            return redirect(url_for("register"))

        conn = get_db()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO users
                (name, username, password_hash, role)
                VALUES (%s, %s, %s, 'voter')
                """,
                (
                    name,
                    username,
                    generate_password_hash(password)
                )
            )

            conn.commit()

            flash(
                "Registration successful. Please log in.",
                "success"
            )

            return redirect(url_for("login"))

        except mysql.connector.IntegrityError:

            flash(
                "This username is already registered.",
                "error"
            )

        finally:
            cur.close()
            conn.close()

    return render_template("register.html")


# =====================================================
# VOTER LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        user = authenticate_user()

        if user:

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("voter_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# =====================================================
# SEPARATE ADMIN LOGIN
# =====================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        user = authenticate_user(admin_only=True)

        if user:
            return redirect(url_for("admin_dashboard"))

        if not any(
            category == "error"
            for category, message in session.get("_flashes", [])
        ):
            flash("Invalid admin username or password.", "error")

    return render_template("login.html", admin_only=True)


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("home"))


# =====================================================
# VOTER DASHBOARD
# =====================================================

@app.route("/voter")
@login_required("voter")
def voter_dashboard():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            "SELECT id, name, party FROM candidates ORDER BY name"
        )

        candidates = cur.fetchall()

        cur.execute(
            "SELECT candidate_id FROM votes WHERE user_id=%s",
            (session["user_id"],)
        )

        voted = cur.fetchone()

    finally:
        cur.close()
        conn.close()

    return render_template(
        "voter.html",
        candidates=candidates,
        voted=bool(voted)
    )


# =====================================================
# SUBMIT VOTE
# =====================================================

@app.route("/vote/<int:candidate_id>", methods=["POST"])
@login_required("voter")
def vote(candidate_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute(
            "SELECT id FROM candidates WHERE id=%s",
            (candidate_id,)
        )

        candidate = cur.fetchone()

        if not candidate:

            flash("Candidate not found.", "error")

            return redirect(url_for("voter_dashboard"))

        cur.execute(
            """
            INSERT INTO votes (user_id, candidate_id)
            VALUES (%s, %s)
            """,
            (
                session["user_id"],
                candidate_id
            )
        )

        conn.commit()

        return redirect(url_for("vote_confirmation"))

    except mysql.connector.IntegrityError:

        conn.rollback()

        flash(
            "You have already voted. Only one vote per account is allowed.",
            "error"
        )

        return redirect(url_for("voter_dashboard"))

    finally:
        cur.close()
        conn.close()


# =====================================================
# VOTE CONFIRMATION PAGE
# =====================================================

@app.route("/vote-confirmation")
@login_required("voter")
def vote_confirmation():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                candidates.name,
                candidates.party
            FROM votes
            JOIN candidates
            ON votes.candidate_id = candidates.id
            WHERE votes.user_id = %s
            """,
            (session["user_id"],)
        )

        vote_details = cur.fetchone()

    finally:
        cur.close()
        conn.close()

    if not vote_details:

        flash("You have not submitted your vote yet.", "error")

        return redirect(url_for("voter_dashboard"))

    return render_template(
        "confirmation.html",
        vote=vote_details
    )


# =====================================================
# MY VOTE PAGE
# =====================================================

@app.route("/my-vote")
@login_required("voter")
def my_vote():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                candidates.name,
                candidates.party
            FROM votes
            JOIN candidates
            ON votes.candidate_id = candidates.id
            WHERE votes.user_id = %s
            """,
            (session["user_id"],)
        )

        vote_details = cur.fetchone()

    finally:
        cur.close()
        conn.close()

    return render_template(
        "my_vote.html",
        vote=vote_details
    )


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route("/admin")
@login_required("admin")
def admin_dashboard():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                c.id,
                c.name,
                c.party,
                COUNT(v.id) AS total_votes
            FROM candidates c
            LEFT JOIN votes v
            ON c.id = v.candidate_id
            GROUP BY c.id, c.name, c.party
            ORDER BY total_votes DESC, c.name
            """
        )

        candidates = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) AS total FROM users WHERE role='voter'"
        )

        voter_count = cur.fetchone()["total"]

        cur.execute(
            "SELECT COUNT(*) AS total FROM votes"
        )

        vote_count = cur.fetchone()["total"]

    finally:
        cur.close()
        conn.close()

    return render_template(
        "admin.html",
        candidates=candidates,
        voter_count=voter_count,
        vote_count=vote_count
    )


# =====================================================
# MANAGE CANDIDATES PAGE
# =====================================================

@app.route("/admin/manage-candidates")
@login_required("admin")
def manage_candidates():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                c.id,
                c.name,
                c.party,
                COUNT(v.id) AS total_votes
            FROM candidates c
            LEFT JOIN votes v
            ON c.id = v.candidate_id
            GROUP BY c.id, c.name, c.party
            ORDER BY c.name
            """
        )

        candidates = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    return render_template(
        "manage_candidates.html",
        candidates=candidates
    )


# =====================================================
# ADD CANDIDATE
# =====================================================

@app.route("/admin/candidates", methods=["POST"])
@login_required("admin")
def add_candidate():

    name = request.form.get("name", "").strip()
    party = request.form.get("party", "").strip()

    if not name or not party:

        flash(
            "Candidate name and party are required.",
            "error"
        )

    else:

        conn = get_db()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO candidates (name, party)
                VALUES (%s, %s)
                """,
                (name, party)
            )

            conn.commit()

            flash("Candidate added successfully.", "success")

        finally:
            cur.close()
            conn.close()

    return redirect(url_for("manage_candidates"))


# =====================================================
# DELETE CANDIDATE
# =====================================================

@app.route(
    "/admin/candidates/delete/<int:candidate_id>",
    methods=["POST"]
)
@login_required("admin")
def delete_candidate(candidate_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute(
            "SELECT COUNT(*) FROM votes WHERE candidate_id=%s",
            (candidate_id,)
        )

        has_votes = cur.fetchone()[0] > 0

        if has_votes:

            flash(
                "A candidate with recorded votes cannot be deleted.",
                "error"
            )

        else:

            cur.execute(
                "DELETE FROM candidates WHERE id=%s",
                (candidate_id,)
            )

            conn.commit()

            flash("Candidate deleted successfully.", "success")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("manage_candidates"))


# =====================================================
# VOTING RESULTS PAGE
# =====================================================

@app.route("/admin/results")
@login_required("admin")
def voting_results():

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                c.name,
                c.party,
                COUNT(v.id) AS total_votes
            FROM candidates c
            LEFT JOIN votes v
            ON c.id = v.candidate_id
            GROUP BY c.id, c.name, c.party
            ORDER BY total_votes DESC
            """
        )

        results = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) AS total FROM votes"
        )

        total_votes = cur.fetchone()["total"]

    finally:
        cur.close()
        conn.close()

    return render_template(
        "results.html",
        results=results,
        total_votes=total_votes
    )

# ==========================================
# REPORTS PAGE
# ==========================================

@app.route('/admin/reports')
@login_required(role='admin')
def reports():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_voters
        FROM users
        WHERE role = 'voter'
    """)
    total_voters = cursor.fetchone()['total_voters']

    cursor.execute("""
        SELECT COUNT(*) AS total_votes
        FROM votes
    """)
    total_votes = cursor.fetchone()['total_votes']

    cursor.execute("""
        SELECT c.name, c.party, COUNT(v.id) AS total_votes
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        GROUP BY c.id, c.name, c.party
        ORDER BY total_votes DESC
    """)
    results = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'reports.html',
        total_voters=total_voters,
        total_votes=total_votes,
        results=results
    )


# ==========================================
# PDF REPORT DOWNLOAD
# ==========================================

@app.route('/admin/reports/pdf')
@login_required(role='admin')
def download_pdf():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_voters
        FROM users WHERE role='voter'
    """)
    total_voters = cursor.fetchone()['total_voters']

    cursor.execute("SELECT COUNT(*) AS total_votes FROM votes")
    total_votes = cursor.fetchone()['total_votes']

    cursor.execute("""
        SELECT c.name, c.party, COUNT(v.id) AS total_votes
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        GROUP BY c.id, c.name, c.party
        ORDER BY total_votes DESC
    """)
    results = cursor.fetchall()

    cursor.close()
    db.close()

    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("ONLINE VOTING SYSTEM", styles['Title']))
    content.append(Paragraph("Voting Report", styles['Heading2']))
    content.append(Spacer(1, 20))

    content.append(Paragraph(
        f"Total Registered Voters: {total_voters}",
        styles['Normal']
    ))

    content.append(Paragraph(
        f"Total Votes: {total_votes}",
        styles['Normal']
    ))

    content.append(Spacer(1, 20))

    data = [['Candidate Name', 'Party', 'Total Votes']]

    for r in results:
        data.append([
            r['name'],
            r['party'],
            r['total_votes']
        ])

    table = Table(data, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))

    content.append(table)

    pdf.build(content)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name='Voting_Report.pdf',
        mimetype='application/pdf'
    )


# ==========================================
# EXCEL REPORT DOWNLOAD
# ==========================================

@app.route('/admin/reports/excel')
@login_required(role='admin')
def download_excel():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total_voters
        FROM users WHERE role='voter'
    """)
    total_voters = cursor.fetchone()['total_voters']

    cursor.execute("SELECT COUNT(*) AS total_votes FROM votes")
    total_votes = cursor.fetchone()['total_votes']

    cursor.execute("""
        SELECT c.name, c.party, COUNT(v.id) AS total_votes
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        GROUP BY c.id, c.name, c.party
        ORDER BY total_votes DESC
    """)
    results = cursor.fetchall()

    cursor.close()
    db.close()

    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Voting Report"

    sheet.append(["ONLINE VOTING SYSTEM REPORT"])
    sheet.append(["Total Registered Voters", total_voters])
    sheet.append(["Total Votes", total_votes])
    sheet.append([])
    sheet.append(["Candidate Name", "Party", "Total Votes"])

    for r in results:
        sheet.append([
            r['name'],
            r['party'],
            r['total_votes']
        ])

    for cell in sheet[5]:
        cell.font = __import__('openpyxl').styles.Font(
            bold=True,
            color="FFFFFF"
        )
        cell.fill = __import__('openpyxl').styles.PatternFill(
            fill_type="solid",
            fgColor="087B58"
        )

    sheet.column_dimensions['A'].width = 30
    sheet.column_dimensions['B'].width = 25
    sheet.column_dimensions['C'].width = 18

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name='Voting_Report.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == "__main__":

    app.run(debug=True)
