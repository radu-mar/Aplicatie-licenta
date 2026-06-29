from flask import Flask, render_template, Response, jsonify, redirect, url_for, request, session, flash
import json
import time
import re
import pandas as pd
from pathlib import Path
from functools import wraps

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from live_processor import LiveRaceProcessor

PRE_RACE_CSV = r"D:\Licenta\AplicatieLucrareLicenta\date_f1\pre_race_lv_2023.csv"

app = Flask(__name__)
app.secret_key = "watchf1-secret-key-2024"

BASE_DIR = Path(__file__).resolve().parent
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'users.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


def is_valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


# --- Model User ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


with app.app_context():
    db.create_all()


# --- Decorator login required ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


live_service = LiveRaceProcessor()


# --- Auth routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("index"))
        flash("Adresă de email sau parolă incorectă.")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username or not email or not password:
            flash("Completează toate câmpurile.")
        elif not is_valid_email(email):
            flash("Adresa de email nu este validă.")
        elif password != confirm:
            flash("Parolele nu coincid.")
        elif User.query.filter_by(username=username).first():
            flash("Numele de utilizator este deja folosit.")
        elif User.query.filter_by(email=email).first():
            flash("Există deja un cont cu această adresă de email.")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Cont creat cu succes! Te poți autentifica acum.")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Main routes (protected) ---
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))


@app.route("/drivers")
@login_required
def drivers():
    return render_template("drivers.html", username=session.get("username"))


@app.route("/tracks")
@login_required
def tracks():
    return render_template("tracks.html", username=session.get("username"))


# --- API routes (protected) ---
@app.route("/api/live-data")
@login_required
def live_data():
    return jsonify(live_service.get_latest_payload())


@app.route("/api/live-events")
@login_required
def live_events():
    def event_stream():
        while True:
            payload = live_service.get_latest_payload()
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(2)
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/momentum")
@login_required
def momentum():
    try:
        df = pd.read_csv("date_f1/pre_race_lv_2023.csv")
        required_cols = ["code", "pilot_momentum_3"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            return jsonify({"error": f"Lipsesc coloanele: {missing}"}), 500
        top_momentum = (
            df[["code", "pilot_momentum_3"]]
            .dropna()
            .sort_values(by="pilot_momentum_3", ascending=False)
            .head(3)
            .reset_index(drop=True)
        )
        result = []
        for _, row in top_momentum.iterrows():
            result.append({"code": row["code"], "momentum": round(float(row["pilot_momentum_3"]), 3)})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drivers")
@login_required
def api_drivers():
    try:
        df = pd.read_csv(PRE_RACE_CSV)
        df = df[["driverId", "code", "rata_accidente_pilot", "pilot_momentum_3"]]
        df = df[df["code"].notna()]
        df = df.groupby("driverId").first().reset_index()
        df = df.sort_values(by="pilot_momentum_3", ascending=False).reset_index(drop=True)
        drivers_list = []
        for _, row in df.iterrows():
            drivers_list.append({
                "driverId": int(row["driverId"]),
                "code": row["code"],
                "rata_accidente_pilot": round(float(row["rata_accidente_pilot"]) * 100, 1),
                "pilot_momentum": round(float(row["pilot_momentum_3"]), 2)
            })
        return jsonify(drivers_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    live_service.start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)