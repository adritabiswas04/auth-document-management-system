import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "exp7_secret_key"

# --- MySQL Config ---
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "AdritaBiswas@04"
app.config["MYSQL_DB"] = "flask_dbms_lab"

mysql = MySQL(app)

# --- Upload Config ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required():
    return "user_id" in session

@app.route("/")
def home():
    return redirect(url_for("login"))

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required!", "danger")
            return redirect(url_for("signup"))

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password))
            )
            mysql.connection.commit()
            flash("Signup successful! Please login.", "success")
            return redirect(url_for("login"))
        except:
            mysql.connection.rollback()
            flash("Email already exists or DB error.", "danger")
        finally:
            cur.close()

    return render_template("signup.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, password_hash FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["name"] = user[1]
            session["email"] = email
            flash("Logged in!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out!", "info")
    return redirect(url_for("login"))

# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("dashboard.html", name=session.get("name"))

# ---------- UPDATE PROFILE ----------
@app.route("/update_profile", methods=["GET", "POST"])
def update_profile():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_email = request.form.get("email", "").strip().lower()

        if not new_name or not new_email:
            flash("Name and Email required.", "danger")
            return redirect(url_for("update_profile"))

        cur = mysql.connection.cursor()
        try:
            cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s",
                        (new_name, new_email, session["user_id"]))
            mysql.connection.commit()
            session["name"] = new_name
            session["email"] = new_email
            flash("Profile updated!", "success")
        except:
            mysql.connection.rollback()
            flash("Email already used.", "danger")
        finally:
            cur.close()

        return redirect(url_for("dashboard"))

    return render_template("update_profile.html", name=session.get("name"), email=session.get("email"))

# ---------- RESET PASSWORD ----------
@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        old_pass = request.form.get("old_password", "")
        new_pass = request.form.get("new_password", "")

        cur = mysql.connection.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=%s", (session["user_id"],))
        row = cur.fetchone()

        if not row or not check_password_hash(row[0], old_pass):
            cur.close()
            flash("Old password incorrect.", "danger")
            return redirect(url_for("reset_password"))

        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(new_pass), session["user_id"]))
        mysql.connection.commit()
        cur.close()

        flash("Password changed!", "success")
        return redirect(url_for("dashboard"))

    return render_template("reset_password.html")

# ---------- GRADES VIEW ----------
@app.route("/grades")
def grades():
    if not login_required():
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    cur.execute("SELECT subject, marks, grade FROM grades WHERE user_id=%s", (session["user_id"],))
    rows = cur.fetchall()
    cur.close()

    return render_template("grades.html", grades=rows)

# ---------- DOCUMENTS ----------
@app.route("/documents", methods=["GET", "POST"])
def documents():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Choose a file first.", "danger")
            return redirect(url_for("documents"))

        if not allowed_file(file.filename):
            flash("File type not allowed.", "danger")
            return redirect(url_for("documents"))

        filename = secure_filename(file.filename)
        stored_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{session['user_id']}_{filename}")
        file.save(stored_path)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO documents (owner_id, filename, stored_path) VALUES (%s, %s, %s)",
                    (session["user_id"], filename, stored_path))
        mysql.connection.commit()
        cur.close()

        flash("Uploaded successfully!", "success")
        return redirect(url_for("documents"))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, filename, uploaded_at FROM documents WHERE owner_id=%s", (session["user_id"],))
    my_docs = cur.fetchall()
    cur.close()

    return render_template("documents.html", my_docs=my_docs)

@app.route("/download/<int:doc_id>")
def download(doc_id):
    if not login_required():
        return redirect(url_for("login"))

    cur = mysql.connection.cursor()
    cur.execute("SELECT filename, stored_path, owner_id FROM documents WHERE id=%s", (doc_id,))
    doc = cur.fetchone()
    cur.close()

    if not doc or doc[2] != session["user_id"]:
        flash("Not authorized.", "danger")
        return redirect(url_for("documents"))

    filename, stored_path, _ = doc
    return send_from_directory(os.path.dirname(stored_path), os.path.basename(stored_path),
                               as_attachment=True, download_name=filename)

if __name__ == "__main__":
    app.run(debug=True)