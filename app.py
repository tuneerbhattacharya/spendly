import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

with app.app_context():
    init_db()
    seed_db()


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if user is None:
        session.clear()
    return user


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not name:
        error = "Please enter your name."
    elif not email or "@" not in email:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."

    if error is None:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
            return redirect(url_for("login", registered=1))
        except sqlite3.IntegrityError:
            error = "An account with this email already exists."
        finally:
            conn.close()

    return render_template("register.html", error=error, name=name, email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html", registered=request.args.get("registered") == "1")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email)

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not get_current_user():
        return redirect(url_for("login"))

    # Hardcoded placeholder data; Step 5 replaces this with real queries.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "January 2026",
        "initials": "DU",
    }
    stats = {
        "total_spent": 6339.25,
        "transaction_count": 8,
        "top_category": "Shopping",
    }
    transactions = [
        {"date": "25 Oct 2026", "description": "Dinner out", "category": "Food", "amount": 320.75},
        {"date": "21 Oct 2026", "description": "Gift", "category": "Other", "amount": 200.00},
        {"date": "17 Oct 2026", "description": "New shoes", "category": "Shopping", "amount": 2299.00},
        {"date": "13 Oct 2026", "description": "Movie night", "category": "Entertainment", "amount": 499.00},
        {"date": "09 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 650.00},
        {"date": "06 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 1800.00},
        {"date": "04 Oct 2026", "description": "Metro card recharge", "category": "Transport", "amount": 120.50},
        {"date": "01 Oct 2026", "description": "Groceries", "category": "Food", "amount": 450.00},
    ]
    # pct is rounded to a multiple of 5 so it maps onto the .bar-w-* classes.
    categories = [
        {"name": "Shopping", "total": 2299.00, "pct": 35},
        {"name": "Bills", "total": 1800.00, "pct": 30},
        {"name": "Food", "total": 770.75, "pct": 10},
        {"name": "Health", "total": 650.00, "pct": 10},
        {"name": "Entertainment", "total": 499.00, "pct": 10},
        {"name": "Other", "total": 200.00, "pct": 5},
        {"name": "Transport", "total": 120.50, "pct": 5},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
