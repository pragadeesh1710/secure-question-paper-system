import os
import io
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta
from functools import wraps

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

from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)


# ============================================================
# INDIA TIME - IST (UTC + 5:30)
# ============================================================

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


def current_time():
    """Return current Indian Standard Time."""
    return datetime.now(INDIA_TZ)


def current_time_string():
    """Return current Indian time as a string."""
    return current_time().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# FILE / DATABASE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Azure App Service provides persistent storage under /home.
# Locally, the project folder is used.
if os.path.exists("/home"):
    DATA_DIR = "/home"
else:
    DATA_DIR = BASE_DIR

DB = os.path.join(DATA_DIR, "database.db")

UPLOAD_DIR = os.path.join(
    DATA_DIR,
    "encrypted_files"
)

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    conn = db()

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # QUESTION PAPERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            exam_time TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # AUDIT LOG TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # CREATE DEFAULT USERS ONLY IF NO USERS EXIST
    user_count = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    if user_count == 0:

        users = [
            ("admin", "admin123", "Admin"),
            ("setter", "setter123", "Setter"),
            ("examiner", "examiner123", "Examiner")
        ]

        for username, password, role in users:

            conn.execute(
                """
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    role
                )
            )

    conn.commit()
    conn.close()


# ============================================================
# AUDIT LOGGING
# ============================================================

def log(action, details=""):

    try:

        conn = db()

        conn.execute(
            """
            INSERT INTO audit_logs
            (username, action, details, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                session.get(
                    "username",
                    "anonymous"
                ),
                action,
                details,
                current_time_string()
            )
        )

        conn.commit()
        conn.close()

    except Exception as e:

        print(
            "Audit log error:",
            e
        )


# ============================================================
# LOGIN REQUIRED
# ============================================================

def login_required(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return wrapper


# ============================================================
# ROLE REQUIRED
# ============================================================

def role_required(*roles):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):

            if session.get("role") not in roles:

                flash(
                    "You do not have permission for this action."
                )

                return redirect(
                    url_for("dashboard")
                )

            return f(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# FERNET ENCRYPTION
# ============================================================

def get_fernet():

    # First check environment variable.
    # This will be used later in Azure.
    key = os.environ.get("FERNET_KEY")

    if key:

        return Fernet(
            key.encode()
        )

    # Local development
    key_file = os.path.join(
        DATA_DIR,
        "fernet.key"
    )

    if os.path.exists(key_file):

        with open(
            key_file,
            "rb"
        ) as f:

            key = f.read().decode().strip()

    else:

        key = Fernet.generate_key().decode()

        with open(
            key_file,
            "w"
        ) as f:

            f.write(key)

        print(
            "New Fernet encryption key generated."
        )

    return Fernet(
        key.encode()
    )


# ============================================================
# AZURE BLOB STORAGE
# ============================================================

def get_blob_container_client():

    if BlobServiceClient is None:

        return None

    connection_string = os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    container_name = os.environ.get(
        "AZURE_CONTAINER",
        "question-papers"
    )

    # Azure connection string is not configured.
    # Local testing can continue without it.
    if not connection_string:

        return None

    service = BlobServiceClient.from_connection_string(
        connection_string
    )

    container_client = service.get_container_client(
        container_name
    )

    # Create container if it doesn't exist.
    try:

        container_client.create_container()

    except Exception:

        pass

    return container_client


# ============================================================
# UPLOAD TO AZURE BLOB
# ============================================================

def azure_upload(
    local_path,
    blob_name
):

    container_client = (
        get_blob_container_client()
    )

    if container_client is None:

        return False

    with open(
        local_path,
        "rb"
    ) as data:

        container_client.upload_blob(
            name=blob_name,
            data=data,
            overwrite=True
        )

    return True


# ============================================================
# DOWNLOAD FROM AZURE BLOB
# ============================================================

def azure_download(blob_name):

    container_client = (
        get_blob_container_client()
    )

    if container_client is None:

        return None

    blob_client = (
        container_client.get_blob_client(
            blob_name
        )
    )

    if not blob_client.exists():

        return None

    downloaded = (
        blob_client.download_blob()
    )

    return downloaded.readall()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    if "user_id" in session:

        return redirect(
            url_for("dashboard")
        )

    return redirect(
        url_for("login")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        conn = db()

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.update(
                user_id=user["id"],
                username=user["username"],
                role=user["role"]
            )

            log(
                "LOGIN_SUCCESS",
                f"Role: {user['role']}"
            )

            return redirect(
                url_for("dashboard")
            )

        log(
            "LOGIN_FAILED",
            username
        )

        flash(
            "Invalid username or password."
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    if "user_id" in session:

        log("LOGOUT")

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    conn = db()

    papers = conn.execute(
        """
        SELECT * FROM papers
        ORDER BY id DESC
        """
    ).fetchall()

    logs = conn.execute(
        """
        SELECT * FROM audit_logs
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        papers=papers,
        logs=logs
    )


# ============================================================
# UPLOAD QUESTION PAPER
# ADMIN + SETTER
# ============================================================

@app.route(
    "/upload",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "Admin",
    "Setter"
)
def upload():

    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        exam_time = request.form[
            "exam_time"
        ]

        uploaded = request.files[
            "paper"
        ]

        # Validate input
        if (
            not title
            or not uploaded
            or not uploaded.filename
        ):

            flash(
                "Enter a title and select a file."
            )

            return redirect(
                url_for("upload")
            )

        # ====================================================
        # ORIGINAL FILE
        # ====================================================

        original = os.path.basename(
            uploaded.filename
        )

        raw = uploaded.read()

        if not raw:

            flash(
                "The selected file is empty."
            )

            return redirect(
                url_for("upload")
            )

        # ====================================================
        # SHA-256 HASH
        # ====================================================

        file_hash = hashlib.sha256(
            raw
        ).hexdigest()

        # ====================================================
        # ENCRYPT FILE
        # ====================================================

        encrypted = get_fernet().encrypt(
            raw
        )

        # ====================================================
        # CREATE UNIQUE FILE NAME
        # ====================================================

        timestamp = current_time().strftime(
            "%Y%m%d%H%M%S"
        )

        stored_name = (
            f"{timestamp}_{original}.enc"
        )

        local_path = os.path.join(
            UPLOAD_DIR,
            stored_name
        )

        # ====================================================
        # SAVE ENCRYPTED FILE
        # ====================================================

        with open(
            local_path,
            "wb"
        ) as f:

            f.write(encrypted)

        # ====================================================
        # UPLOAD TO AZURE
        # ====================================================

        try:

            uploaded_to_azure = azure_upload(
                local_path,
                stored_name
            )

            if uploaded_to_azure:

                print(
                    "Encrypted paper uploaded to Azure Blob:",
                    stored_name
                )

            else:

                print(
                    "Azure Blob is not configured."
                )

        except Exception as e:

            print(
                "Azure Blob upload failed:",
                e
            )

            flash(
                "Azure storage upload failed."
            )

            return redirect(
                url_for("upload")
            )

        # ====================================================
        # SAVE DATABASE RECORD
        # ====================================================

        conn = db()

        conn.execute(
            """
            INSERT INTO papers
            (
                title,
                filename,
                stored_name,
                file_hash,
                exam_time,
                uploaded_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                original,
                stored_name,
                file_hash,
                exam_time,
                session["username"],
                current_time_string()
            )
        )

        conn.commit()
        conn.close()

        log(
            "UPLOAD",
            title
        )

        flash(
            "Question paper encrypted and uploaded successfully."
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "upload.html"
    )


# ============================================================
# DOWNLOAD QUESTION PAPER
# ADMIN + EXAMINER
# ============================================================

@app.route(
    "/download/<int:paper_id>"
)
@login_required
@role_required(
    "Admin",
    "Examiner"
)
def download(paper_id):

    # ========================================================
    # GET PAPER
    # ========================================================

    conn = db()

    paper = conn.execute(
        """
        SELECT * FROM papers
        WHERE id = ?
        """,
        (paper_id,)
    ).fetchone()

    conn.close()

    if not paper:

        flash(
            "Paper not found."
        )

        return redirect(
            url_for("dashboard")
        )

    # ========================================================
    # CHECK EXAM TIME
    # ========================================================

    try:

        exam_time = datetime.strptime(
            paper["exam_time"],
            "%Y-%m-%dT%H:%M"
        )

        # Treat submitted time as IST.
        exam_time = exam_time.replace(
            tzinfo=INDIA_TZ
        )

        now = current_time()

        # Examiner is blocked before release time.
        # Admin can download anytime.

        if (
            now < exam_time
            and session.get("role") != "Admin"
        ):

            log(
                "BLOCKED_DOWNLOAD",
                paper["title"]
            )

            flash(
                "This question paper is locked until "
                "the scheduled exam time."
            )

            return redirect(
                url_for("dashboard")
            )

    except ValueError:

        flash(
            "Invalid exam time format."
        )

        return redirect(
            url_for("dashboard")
        )

    # ========================================================
    # GET ENCRYPTED FILE
    # ========================================================

    encrypted = None

    # First try Azure Blob Storage.
    try:

        encrypted = azure_download(
            paper["stored_name"]
        )

    except Exception as e:

        print(
            "Azure Blob download failed:",
            e
        )

    # ========================================================
    # LOCAL FALLBACK
    # ========================================================

    if encrypted is None:

        local_path = os.path.join(
            UPLOAD_DIR,
            paper["stored_name"]
        )

        if os.path.exists(
            local_path
        ):

            with open(
                local_path,
                "rb"
            ) as f:

                encrypted = f.read()

        else:

            flash(
                "Encrypted file is missing."
            )

            return redirect(
                url_for("dashboard")
            )

    # ========================================================
    # DECRYPT
    # ========================================================

    try:

        raw = get_fernet().decrypt(
            encrypted
        )

    except Exception as e:

        print(
            "Decryption error:",
            e
        )

        log(
            "DECRYPTION_FAILURE",
            paper["title"]
        )

        flash(
            "Unable to decrypt the question paper."
        )

        return redirect(
            url_for("dashboard")
        )

    # ========================================================
    # SHA-256 INTEGRITY CHECK
    # ========================================================

    calculated_hash = hashlib.sha256(
        raw
    ).hexdigest()

    if (
        calculated_hash
        != paper["file_hash"]
    ):

        log(
            "INTEGRITY_FAILURE",
            paper["title"]
        )

        flash(
            "Integrity verification failed."
        )

        return redirect(
            url_for("dashboard")
        )

    # ========================================================
    # DOWNLOAD LOG
    # ========================================================

    log(
        "DOWNLOAD",
        paper["title"]
    )

    # ========================================================
    # SEND PDF
    # ========================================================

    return send_file(
        io.BytesIO(raw),
        as_attachment=True,
        download_name=paper["filename"],
        mimetype="application/pdf"
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

# This is outside the __main__ block so it also runs
# when Azure starts the application using Gunicorn.

init_db()


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )