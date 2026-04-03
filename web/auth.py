"""Authentication module — Flask-Login + TOTP 2FA.

Provides:
- Password login with bcrypt hashing
- TOTP two-factor authentication (Google Authenticator / Authy)
- Session timeout (20 min inactivity)
- Account lockout after 5 failed attempts (15 min)
- Single-use backup codes for 2FA recovery
"""

import json
import secrets
from datetime import datetime, timedelta
from io import BytesIO
import base64

import bcrypt
import pyotp
import qrcode
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from db.init_db import get_connection

auth_bp = Blueprint("auth", __name__)

# Session timeout: 20 minutes
SESSION_TIMEOUT_MINUTES = 20
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


# ──────────────────────────────────────────────
# User model
# ──────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, id, username, password_hash, totp_secret=None,
                 totp_enabled=False, backup_codes=None, **kwargs):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.totp_secret = totp_secret
        self.totp_enabled = bool(totp_enabled)
        self.backup_codes = json.loads(backup_codes) if backup_codes else []


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM app_users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(**dict(row))
    return None


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM app_users WHERE username=?", (username,)).fetchone()
    conn.close()
    if row:
        return User(**dict(row))
    return None


# ──────────────────────────────────────────────
# Password hashing
# ──────────────────────────────────────────────

def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ──────────────────────────────────────────────
# Account lockout
# ──────────────────────────────────────────────

def is_account_locked(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT failed_attempts, locked_until FROM app_users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    if not row:
        return False
    if row["locked_until"]:
        locked = datetime.fromisoformat(row["locked_until"])
        if datetime.now() < locked:
            return True
        # Lockout expired — reset
        conn = get_connection()
        conn.execute(
            "UPDATE app_users SET failed_attempts=0, locked_until=NULL WHERE username=?",
            (username,),
        )
        conn.commit()
        conn.close()
    return False


def record_failed_attempt(username):
    conn = get_connection()
    conn.execute(
        "UPDATE app_users SET failed_attempts = failed_attempts + 1 WHERE username=?",
        (username,),
    )
    row = conn.execute(
        "SELECT failed_attempts FROM app_users WHERE username=?", (username,),
    ).fetchone()
    if row and row["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
        lock_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        conn.execute(
            "UPDATE app_users SET locked_until=? WHERE username=?",
            (lock_until, username),
        )
    conn.commit()
    conn.close()


def clear_failed_attempts(username):
    conn = get_connection()
    conn.execute(
        "UPDATE app_users SET failed_attempts=0, locked_until=NULL, last_login=datetime('now') WHERE username=?",
        (username,),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# TOTP 2FA
# ──────────────────────────────────────────────

def generate_totp_secret():
    return pyotp.random_base32()


def get_totp_qr_code(username, secret):
    """Generate a QR code image for Google Authenticator setup."""
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name="ASX Stock Picker"
    )
    img = qrcode.make(uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def verify_totp(secret, code):
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # Allow 30s window either side


def generate_backup_codes(count=10):
    """Generate single-use backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def use_backup_code(user_id, code):
    """Try to use a backup code. Returns True if valid."""
    conn = get_connection()
    row = conn.execute("SELECT backup_codes FROM app_users WHERE id=?", (user_id,)).fetchone()
    if not row or not row["backup_codes"]:
        conn.close()
        return False
    codes = json.loads(row["backup_codes"])
    code_upper = code.upper().strip()
    if code_upper in codes:
        codes.remove(code_upper)
        conn.execute(
            "UPDATE app_users SET backup_codes=? WHERE id=?",
            (json.dumps(codes), user_id),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


# ──────────────────────────────────────────────
# Setup: create first user
# ──────────────────────────────────────────────

def create_user(username, password):
    """Create a new user. Returns user ID."""
    conn = get_connection()
    pw_hash = hash_password(password)
    conn.execute(
        "INSERT INTO app_users (username, password_hash) VALUES (?, ?)",
        (username, pw_hash),
    )
    conn.commit()
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return user_id


def user_exists():
    """Check if any user account exists."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM app_users").fetchone()
    conn.close()
    return row["cnt"] > 0


# ──────────────────────────────────────────────
# Flask-Login setup
# ──────────────────────────────────────────────

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access the dashboard."


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))


# ──────────────────────────────────────────────
# Session timeout middleware
# ──────────────────────────────────────────────

def check_session_timeout():
    """Call this before each request to enforce session timeout."""
    if current_user.is_authenticated:
        last_active = session.get("last_active")
        if last_active:
            last_dt = datetime.fromisoformat(last_active)
            if datetime.now() - last_dt > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                logout_user()
                session.clear()
                flash("Session expired. Please log in again.")
                return redirect(url_for("auth.login"))
        session["last_active"] = datetime.now().isoformat()


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-time setup — create the admin account."""
    if user_exists():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if len(password) < 12:
            flash("Password must be at least 12 characters.")
            return render_template("auth/setup.html")
        if password != confirm:
            flash("Passwords don't match.")
            return render_template("auth/setup.html")

        user_id = create_user(username, password)

        # Generate TOTP secret
        totp_secret = generate_totp_secret()
        backup_codes = generate_backup_codes()
        conn = get_connection()
        conn.execute(
            "UPDATE app_users SET totp_secret=?, backup_codes=? WHERE id=?",
            (totp_secret, json.dumps(backup_codes), user_id),
        )
        conn.commit()
        conn.close()

        # Show QR code for authenticator setup
        qr_b64 = get_totp_qr_code(username, totp_secret)
        return render_template(
            "auth/setup_2fa.html",
            qr_code=qr_b64,
            secret=totp_secret,
            backup_codes=backup_codes,
            username=username,
        )

    return render_template("auth/setup.html")


@auth_bp.route("/setup/verify-2fa", methods=["POST"])
def setup_verify_2fa():
    """Verify TOTP code during setup to confirm authenticator is working."""
    username = request.form["username"]
    code = request.form["totp_code"].strip()

    user = get_user_by_username(username)
    if not user or not user.totp_secret:
        flash("Setup error. Please try again.")
        return redirect(url_for("auth.setup"))

    if verify_totp(user.totp_secret, code):
        conn = get_connection()
        conn.execute("UPDATE app_users SET totp_enabled=1 WHERE id=?", (user.id,))
        conn.commit()
        conn.close()
        flash("Account created with 2FA enabled. Please log in.")
        return redirect(url_for("auth.login"))
    else:
        flash("Invalid code. Make sure your authenticator is synced and try again.")
        qr_b64 = get_totp_qr_code(username, user.totp_secret)
        backup_codes = user.backup_codes
        return render_template(
            "auth/setup_2fa.html",
            qr_code=qr_b64,
            secret=user.totp_secret,
            backup_codes=backup_codes,
            username=username,
        )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page — password + optional TOTP."""
    if not user_exists():
        return redirect(url_for("auth.setup"))

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if is_account_locked(username):
            flash(f"Account locked. Try again in {LOCKOUT_MINUTES} minutes.")
            return render_template("auth/login.html")

        user = get_user_by_username(username)
        if not user or not check_password(password, user.password_hash):
            if user:
                record_failed_attempt(username)
            flash("Invalid username or password.")
            return render_template("auth/login.html")

        # If 2FA is enabled, ask for code
        if user.totp_enabled:
            session["pending_user_id"] = user.id
            return render_template("auth/totp.html")

        # No 2FA — log in directly
        clear_failed_attempts(username)
        login_user(user)
        session["last_active"] = datetime.now().isoformat()
        return redirect(url_for("dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/login/verify-2fa", methods=["POST"])
def login_verify_2fa():
    """Verify TOTP code during login."""
    user_id = session.get("pending_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    code = request.form["totp_code"].strip()

    # Try TOTP first
    if verify_totp(user.totp_secret, code):
        session.pop("pending_user_id", None)
        clear_failed_attempts(user.username)
        login_user(user)
        session["last_active"] = datetime.now().isoformat()
        return redirect(url_for("dashboard"))

    # Try backup code
    if use_backup_code(user.id, code):
        session.pop("pending_user_id", None)
        clear_failed_attempts(user.username)
        login_user(user)
        session["last_active"] = datetime.now().isoformat()
        flash("Backup code used. You have fewer backup codes remaining.")
        return redirect(url_for("dashboard"))

    record_failed_attempt(user.username)
    flash("Invalid 2FA code.")
    return render_template("auth/totp.html")


@auth_bp.route("/add-user", methods=["GET", "POST"])
@login_required
def add_user():
    """Create an additional user account (logged-in users only)."""
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(password) < 12:
            flash("Password must be at least 12 characters.")
            return render_template("auth/add_user.html")

        # Check username not taken
        if get_user_by_username(username):
            flash("Username already taken.")
            return render_template("auth/add_user.html")

        user_id = create_user(username, password)

        # Generate TOTP
        totp_secret = generate_totp_secret()
        backup_codes = generate_backup_codes()
        conn = get_connection()
        conn.execute(
            "UPDATE app_users SET totp_secret=?, backup_codes=? WHERE id=?",
            (totp_secret, json.dumps(backup_codes), user_id),
        )
        conn.commit()
        conn.close()

        qr_b64 = get_totp_qr_code(username, totp_secret)
        return render_template(
            "auth/setup_2fa.html",
            qr_code=qr_b64,
            secret=totp_secret,
            backup_codes=backup_codes,
            username=username,
        )

    return render_template("auth/add_user.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    flash("Logged out.")
    return redirect(url_for("auth.login"))
