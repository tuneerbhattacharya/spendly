import pytest

from database import db
from database.queries import delete_expense, get_summary_stats


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


def login(client, user_id=1):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def make_user(email="other@example.com"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other Person", email, "x"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def make_expense(user_id, amount=100.0, category="Food", date="2026-01-10", description="Test"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    finally:
        conn.close()


# --- query helper ---

def test_delete_expense_own(app):
    eid = make_expense(1)
    assert delete_expense(eid, 1) == 1
    assert fetch_row(eid) is None


def test_delete_expense_other_user(app):
    other = make_user()
    eid = make_expense(other)
    assert delete_expense(eid, 1) == 0
    assert fetch_row(eid) is not None


def test_delete_expense_missing(app):
    assert delete_expense(99999, 1) == 0


# --- route ---

def test_post_logged_out_redirects_to_login(client):
    eid = make_expense(1)
    resp = client.post(f"/expenses/{eid}/delete")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert fetch_row(eid) is not None


def test_post_as_owner_deletes_and_redirects(client):
    eid = make_expense(1)
    login(client)
    resp = client.post(f"/expenses/{eid}/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert fetch_row(eid) is None


def test_post_other_users_expense_404(client):
    other = make_user()
    eid = make_expense(other)
    login(client)
    assert client.post(f"/expenses/{eid}/delete").status_code == 404
    assert fetch_row(eid) is not None


def test_post_missing_id_404(client):
    login(client)
    assert client.post("/expenses/99999/delete").status_code == 404


def test_get_not_allowed(client):
    eid = make_expense(1)
    login(client)
    assert client.get(f"/expenses/{eid}/delete").status_code == 405
    assert fetch_row(eid) is not None


# --- profile ---

def test_profile_has_delete_form_per_row(client):
    eid = make_expense(1, description="Unique delete row")
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert f'action="/expenses/{eid}/delete"' in html


def test_profile_totals_update_after_delete(client):
    before = get_summary_stats(1)
    eid = make_expense(1, amount=250.0)
    assert get_summary_stats(1)["transaction_count"] == before["transaction_count"] + 1
    login(client)
    client.post(f"/expenses/{eid}/delete")
    after = get_summary_stats(1)
    assert after["transaction_count"] == before["transaction_count"]
    assert after["total_spent"] == before["total_spent"]
