
import os
import json
import sqlite3
import secrets
from pathlib import Path
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    abort,
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from ai_agent import analyze_idea


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

app.config["SECRET_KEY"] = (
    os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DB_PATH = BASE_DIR / "startup_validator.db"


# --------------------------------------------------
# Database
# --------------------------------------------------

def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT '',
                experience TEXT DEFAULT '',
                goal TEXT DEFAULT '',
                onboarding_complete INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                idea TEXT NOT NULL,
                industry TEXT DEFAULT '',
                customers TEXT DEFAULT '',
                analysis TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        user_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        optional_user_columns = {
            "role": "TEXT DEFAULT ''",
            "experience": "TEXT DEFAULT ''",
            "goal": "TEXT DEFAULT ''",
            "onboarding_complete": "INTEGER DEFAULT 0",
        }

        for column, definition in optional_user_columns.items():
            if column not in user_columns:
                db.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )

        report_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(reports)"
            ).fetchall()
        }

        optional_report_columns = {
            "industry": "TEXT DEFAULT ''",
            "customers": "TEXT DEFAULT ''",
        }

        for column, definition in optional_report_columns.items():
            if column not in report_columns:
                db.execute(
                    f"ALTER TABLE reports ADD COLUMN {column} {definition}"
                )


def save_report(user_id, idea, industry, customers, analysis):
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO reports
                (user_id, idea, industry, customers, analysis)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                idea,
                industry,
                customers,
                json.dumps(analysis, ensure_ascii=False),
            ),
        )
        return cursor.lastrowid


# --------------------------------------------------
# Authentication helpers
# --------------------------------------------------

def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    with get_db() as db:
        return db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def onboarding_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()

        if user is None:
            session.clear()
            return redirect(url_for("login"))

        if not user["onboarding_complete"]:
            return redirect(url_for("onboarding"))

        return view(*args, **kwargs)

    return wrapped_view


# --------------------------------------------------
# Home
# --------------------------------------------------

@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_current_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if not user["onboarding_complete"]:
        return redirect(url_for("onboarding"))

    return redirect(url_for("dashboard"))


# --------------------------------------------------
# Registration
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash(
                "Your password must contain at least 8 characters.",
                "error",
            )
            return render_template("register.html")

        try:
            with get_db() as db:
                cursor = db.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (?, ?, ?)
                    """,
                    (
                        name,
                        email,
                        generate_password_hash(password),
                    ),
                )
                user_id = cursor.lastrowid

            session.clear()
            session["user_id"] = user_id

            return redirect(url_for("onboarding"))

        except sqlite3.IntegrityError:
            flash(
                "An account with this email already exists.",
                "error",
            )

    return render_template("register.html")


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["user_id"] = user["id"]

            if not user["onboarding_complete"]:
                return redirect(url_for("onboarding"))

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# --------------------------------------------------
# Logout
# --------------------------------------------------

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------
# Onboarding
# --------------------------------------------------

@app.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    user = get_current_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        experience = request.form.get("experience", "").strip()
        goal = request.form.get("goal", "").strip()

        with get_db() as db:
            db.execute(
                """
                UPDATE users
                SET role = ?,
                    experience = ?,
                    goal = ?,
                    onboarding_complete = 1
                WHERE id = ?
                """,
                (role, experience, goal, user["id"]),
            )

        return redirect(url_for("dashboard"))

    return render_template("onboarding.html", user=user)


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/dashboard")
@login_required
@onboarding_required
def dashboard():
    user = get_current_user()

    with get_db() as db:
        reports = db.execute(
            """
            SELECT id, idea, industry, customers, created_at
            FROM reports
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user["id"],),
        ).fetchall()

    return render_template(
        "dashboard.html",
        user=user,
        reports=reports,
    )


# --------------------------------------------------
# New startup idea page
# Supports both endpoint names used by templates.
# --------------------------------------------------

@app.route("/new", endpoint="new_report")
@app.route("/new", endpoint="new_idea")
@login_required
@onboarding_required
def new_idea():
    user = get_current_user()
    return render_template("index.html", user=user)


# --------------------------------------------------
# Validate startup idea using Groq only
# --------------------------------------------------

@app.route("/validate", methods=["POST"])
@login_required
@onboarding_required
def validate():
    user = get_current_user()

    if user is None:
        session.clear()
        return jsonify({
            "success": False,
            "message": "Your session has expired. Please log in again.",
        }), 401

    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    idea = str(data.get("idea", "")).strip()
    industry = str(data.get("industry", "")).strip()
    customers = str(data.get("customers", "")).strip()

    if not idea:
        return jsonify({
            "success": False,
            "message": "Please describe your startup idea.",
        }), 400

    if len(idea) > 10000:
        return jsonify({
            "success": False,
            "message": (
                "Please keep your idea description under "
                "10,000 characters."
            ),
        }), 400

    if len(industry) > 200 or len(customers) > 500:
        return jsonify({
            "success": False,
            "message": (
                "Please shorten the industry or customer description."
            ),
        }), 400

    try:
        analysis = analyze_idea(
            idea=idea,
            industry=industry,
            customers=customers,
        )

        if not isinstance(analysis, dict):
            raise ValueError("The AI returned an invalid report.")

        analysis["research_status"] = (
            "AI analysis only. Live web research was not performed. "
            "Verify market statistics, competitors, government schemes, "
            "legal requirements, and cost estimates using reliable sources."
        )

        report_id = save_report(
            user_id=user["id"],
            idea=idea,
            industry=industry,
            customers=customers,
            analysis=analysis,
        )

        return jsonify({
            "success": True,
            "report_id": report_id,
            "analysis": analysis,
            "message": "Your startup validation report is ready.",
        })

    except Exception:
        app.logger.exception("Startup idea validation failed.")

        return jsonify({
            "success": False,
            "message": (
                "We couldn't generate the report. Check your Groq API key, "
                "internet connection, API limits, and terminal error."
            ),
        }), 500


# --------------------------------------------------
# View a saved report
# --------------------------------------------------

@app.route("/reports/<int:report_id>")
@login_required
@onboarding_required
def view_report(report_id):
    user = get_current_user()

    with get_db() as db:
        report = db.execute(
            """
            SELECT *
            FROM reports
            WHERE id = ? AND user_id = ?
            """,
            (report_id, user["id"]),
        ).fetchone()

    if report is None:
        abort(404)

    try:
        analysis = json.loads(report["analysis"])
    except (json.JSONDecodeError, TypeError):
        analysis = {}

    return render_template(
        "report.html",
        user=user,
        report=report,
        analysis=analysis,
    )


# --------------------------------------------------
# Delete a saved report
# --------------------------------------------------

@app.route("/reports/<int:report_id>/delete", methods=["POST"])
@login_required
@onboarding_required
def delete_report(report_id):
    user = get_current_user()

    with get_db() as db:
        cursor = db.execute(
            """
            DELETE FROM reports
            WHERE id = ? AND user_id = ?
            """,
            (report_id, user["id"]),
        )

    if cursor.rowcount == 0:
        abort(404)

    flash("Report deleted successfully.", "success")
    return redirect(url_for("dashboard"))


# --------------------------------------------------
# Error pages
# --------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html"), 404


# --------------------------------------------------
# Start application
# --------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
