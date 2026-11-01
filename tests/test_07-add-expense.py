"""Tests for Step 7: Add Expense (GET/POST /expenses/add)."""
from datetime import date

import pytest

from database import db

SEED_TOTAL = 6339.25
SEED_COUNT = 8


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()

    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    return client


def make_user(name="Other Person", email="other@example.com"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, "x"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def all_expenses():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id")]
    finally:
        conn.close()


def count_expenses():
    return len(all_expenses())


def valid_form(**overrides):
    form = {
        "amount": "250.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Lunch",
    }
    form.update(overrides)
    return form


def post(client, **overrides):
    return client.post("/expenses/add", data=valid_form(**overrides))


def has_error(resp):
    return b"auth-error" in resp.data


# ------------------------------ auth guards ------------------------------ #

def test_get_logged_out_redirects_to_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_logged_out_redirects_and_inserts_nothing(client):
    resp = post(client)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert count_expenses() == SEED_COUNT, "No row may be inserted when logged out"


# ------------------------------ GET form ------------------------------ #

def test_get_logged_in_renders_form_with_fields(logged_in):
    resp = logged_in.get("/expenses/add")
    assert resp.status_code == 200
    for name in (b'name="amount"', b'name="category"', b'name="date"', b'name="description"'):
        assert name in resp.data, f"Missing field {name!r}"
    assert b"/profile" in resp.data, "Cancel link to /profile expected"


def test_get_lists_all_categories(logged_in):
    body = logged_in.get("/expenses/add").data.decode()
    for cat in db.CATEGORIES:
        assert cat in body, f"Category {cat} missing from form"
    assert len(db.CATEGORIES) == 7


def test_get_prefills_today_date(logged_in):
    body = logged_in.get("/expenses/add").data.decode()
    assert date.today().isoformat() in body


# ------------------------------ happy path ------------------------------ #

def test_valid_post_redirects_to_profile(logged_in):
    resp = post(logged_in)
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_valid_post_inserts_row_with_submitted_values(logged_in):
    post(logged_in, amount="250.50", category="Transport", date="2026-03-05",
         description="Cab")
    rows = all_expenses()
    assert len(rows) == SEED_COUNT + 1
    new = rows[-1]
    assert new["user_id"] == 1
    assert new["amount"] == pytest.approx(250.50)
    assert new["category"] == "Transport"
    assert new["date"] == "2026-03-05"
    assert new["description"] == "Cab"


def test_amount_rounded_to_two_decimals(logged_in):
    post(logged_in, amount="10.456")
    assert all_expenses()[-1]["amount"] == pytest.approx(10.46)


@pytest.mark.parametrize("category", ["Food", "Transport", "Bills", "Health",
                                      "Entertainment", "Shopping", "Other"])
def test_every_category_accepted(logged_in, category):
    resp = post(logged_in, category=category)
    assert resp.status_code == 302
    assert all_expenses()[-1]["category"] == category


def test_empty_description_accepted(logged_in):
    resp = post(logged_in, description="")
    assert resp.status_code == 302
    assert count_expenses() == SEED_COUNT + 1
    assert not all_expenses()[-1]["description"], "Empty description stored as NULL/empty"


def test_missing_description_field_accepted(logged_in):
    form = valid_form()
    del form["description"]
    resp = logged_in.post("/expenses/add", data=form)
    assert resp.status_code == 302
    assert count_expenses() == SEED_COUNT + 1


def test_description_is_stripped(logged_in):
    post(logged_in, description="   padded   ")
    assert all_expenses()[-1]["description"] == "padded"


def test_whitespace_only_description_accepted(logged_in):
    resp = post(logged_in, description="    ")
    assert resp.status_code == 302
    assert not all_expenses()[-1]["description"]


def test_follow_redirect_lands_on_profile(logged_in):
    resp = logged_in.post("/expenses/add", data=valid_form(), follow_redirects=True)
    assert resp.status_code == 200
    assert "₹".encode() in resp.data


# ------------------------------ profile reflection ------------------------------ #

def test_new_expense_appears_on_profile(logged_in):
    post(logged_in, amount="1000", category="Shopping", description="UniqueDescXyz")
    body = logged_in.get("/profile").data.decode()
    assert "UniqueDescXyz" in body
    assert f"{SEED_TOTAL + 1000:,.2f}" in body, "Total spent should include new expense"
    assert f">{SEED_COUNT + 1}<" in body.replace(" ", "").replace("\n", ""), \
        "Transaction count should increase"


# ------------------------------ validation errors ------------------------------ #

@pytest.mark.parametrize("amount", ["", "   ", "abc", "12abc", "1,5,5", "nan", "NaN",
                                    "inf", "-inf", "Infinity", "0", "0.00", "-5", "-0.01"])
def test_bad_amount_rejected(logged_in, amount):
    resp = post(logged_in, amount=amount)
    assert resp.status_code == 200
    assert has_error(resp), f"Error expected for amount {amount!r}"
    assert count_expenses() == SEED_COUNT


def test_missing_amount_field_rejected(logged_in):
    form = valid_form()
    del form["amount"]
    resp = logged_in.post("/expenses/add", data=form)
    assert resp.status_code == 200
    assert has_error(resp)
    assert count_expenses() == SEED_COUNT


@pytest.mark.parametrize("category", ["", "Groceries", "food", "FOOD", "Food; DROP TABLE expenses"])
def test_bad_category_rejected(logged_in, category):
    resp = post(logged_in, category=category)
    assert resp.status_code == 200
    assert has_error(resp)
    assert count_expenses() == SEED_COUNT


def test_missing_category_field_rejected(logged_in):
    form = valid_form()
    del form["category"]
    resp = logged_in.post("/expenses/add", data=form)
    assert resp.status_code == 200
    assert has_error(resp)
    assert count_expenses() == SEED_COUNT


@pytest.mark.parametrize("bad_date", ["", "abc", "2026-13-45", "2026-02-30",
                                      "05/03/2026", "2026-3-5x", "20260305"])
def test_bad_date_rejected(logged_in, bad_date):
    resp = post(logged_in, date=bad_date)
    assert resp.status_code == 200
    assert has_error(resp), f"Error expected for date {bad_date!r}"
    assert count_expenses() == SEED_COUNT


def test_missing_date_field_rejected(logged_in):
    form = valid_form()
    del form["date"]
    resp = logged_in.post("/expenses/add", data=form)
    assert resp.status_code == 200
    assert has_error(resp)
    assert count_expenses() == SEED_COUNT


def test_overlong_description_capped_or_rejected(logged_in):
    resp = post(logged_in, description="x" * 5000)
    assert resp.status_code in (200, 302)
    rows = all_expenses()
    if resp.status_code == 302:
        assert len(rows[-1]["description"]) <= 200, "Description must be capped (~200)"
    else:
        assert has_error(resp)
        assert len(rows) == SEED_COUNT


# ------------------------------ value preservation ------------------------------ #

def test_values_preserved_on_error(logged_in):
    resp = post(logged_in, amount="-3", category="Health", date="2026-04-09",
                description="Keep me please")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "-3" in body
    assert "2026-04-09" in body
    assert "Keep me please" in body
    assert "Health" in body


def test_values_preserved_on_bad_date(logged_in):
    resp = post(logged_in, amount="77.25", date="2026-13-45", description="Stay")
    body = resp.data.decode()
    assert "77.25" in body
    assert "2026-13-45" in body
    assert "Stay" in body


def test_preserved_category_is_selected(logged_in):
    resp = post(logged_in, amount="0", category="Bills")
    body = resp.data.decode()
    idx = body.index("Bills")
    # 'selected' should appear on the Bills option
    assert "selected" in body[max(0, idx - 80): idx + 40], "Bills option should be selected"


def test_preserved_values_are_escaped(logged_in):
    resp = post(logged_in, amount="0", description='"><script>alert(1)</script>')
    assert b"<script>alert(1)</script>" not in resp.data, "Output must be autoescaped"


# ------------------------------ ownership / security ------------------------------ #

def test_row_belongs_to_session_user(logged_in):
    other = make_user()
    with logged_in.session_transaction() as sess:
        sess["user_id"] = other
    post(logged_in)
    new = all_expenses()[-1]
    assert new["user_id"] == other


def test_forged_user_id_field_ignored(logged_in):
    other = make_user()
    resp = post(logged_in, user_id=str(other))
    assert resp.status_code == 302
    assert all_expenses()[-1]["user_id"] == 1, "user_id must come from session only"


def test_new_expense_not_visible_to_other_user(logged_in):
    other = make_user()
    post(logged_in, description="PrivateThing")
    with logged_in.session_transaction() as sess:
        sess["user_id"] = other
    body = logged_in.get("/profile").data.decode()
    assert "PrivateThing" not in body


def test_sql_injection_description_stored_verbatim(logged_in):
    payload = "x'); DROP TABLE expenses; --"
    resp = post(logged_in, description=payload)
    assert resp.status_code == 302
    rows = all_expenses()  # raises if table was dropped
    assert len(rows) == SEED_COUNT + 1
    assert rows[-1]["description"] == payload


def test_sql_injection_in_amount_rejected_and_table_intact(logged_in):
    resp = post(logged_in, amount="1; DROP TABLE expenses")
    assert resp.status_code == 200
    assert has_error(resp)
    assert count_expenses() == SEED_COUNT


# ------------------------------ untouched placeholders ------------------------------ #

def test_edit_placeholder_untouched(client):
    resp = client.get("/expenses/1/edit")
    assert resp.status_code == 200
    assert b"coming in Step 8" in resp.data


def test_delete_placeholder_untouched(client):
    resp = client.get("/expenses/1/delete")
    assert resp.status_code == 200
    assert b"coming in Step 9" in resp.data


# ------------------------------ profile entry point ------------------------------ #

def test_profile_has_add_expense_link(logged_in):
    body = logged_in.get("/profile").data.decode()
    assert "Add expense" in body
    assert "/expenses/add" in body
