import math
import os
import sqlite3
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import (
    create_expense,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    update_expense,
)

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


def parse_date_range(args):
    """Read the optional from/to query params. Returns (date_from, date_to, error)."""
    date_from = args.get("from", "").strip()
    date_to = args.get("to", "").strip()
    try:
        for value in (date_from, date_to):
            if value:
                datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, None, "Please enter valid dates."
    if date_from and date_to and date_from > date_to:
        return None, None, "The start date must be on or before the end date."
    return date_from or None, date_to or None, None


def validate_expense_form(form):
    """Validate the add-expense form. Returns (clean_values, error)."""
    raw_amount = form.get("amount", "").strip()
    category = form.get("category", "")
    date_value = form.get("date", "").strip()
    description = form.get("description", "").strip()

    try:
        amount = float(raw_amount)
    except ValueError:
        return None, "Please enter a valid amount."
    if not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be greater than zero."

    if category not in CATEGORIES:
        return None, "Please choose a category."

    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return None, "Please enter a valid date."

    if len(description) > 200:
        return None, "Description must be 200 characters or fewer."

    return {
        "amount": round(amount, 2),
        "category": category,
        "date": date_value,
        "description": description,
    }, None


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
    current = get_current_user()
    if not current:
        return redirect(url_for("login"))

    user_id = current["id"]
    date_from, date_to, filter_error = parse_date_range(request.args)
    return render_template(
        "profile.html",
        user=get_user_by_id(user_id),
        stats=get_summary_stats(user_id, date_from, date_to),
        transactions=get_recent_transactions(user_id, date_from=date_from, date_to=date_to),
        categories=get_category_breakdown(user_id, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        filter_error=filter_error,
    )


@app.route("/analytics")
def analytics():
    if not get_current_user():
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    current = get_current_user()
    if not current:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            form={"date": date.today().isoformat()},
        )

    clean, error = validate_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            form=request.form,
            error=error,
        )

    create_expense(
        current["id"],
        clean["amount"],
        clean["category"],
        clean["date"],
        clean["description"],
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    current = get_current_user()
    if not current:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, current["id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            form=expense,
            editing=True,
            expense_id=id,
        )

    clean, error = validate_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            form=request.form,
            error=error,
            editing=True,
            expense_id=id,
        )

    updated = update_expense(
        id,
        current["id"],
        clean["amount"],
        clean["category"],
        clean["date"],
        clean["description"],
    )
    if not updated:
        abort(404)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
