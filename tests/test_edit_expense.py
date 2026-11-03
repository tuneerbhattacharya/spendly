import pytest

from database import db
from database.queries import get_expense_by_id, get_recent_transactions, update_expense


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


def valid_form(**overrides):
    data = {
        "amount": "321.50",
        "category": "Transport",
        "date": "2026-02-02",
        "description": "Taxi",
    }
    data.update(overrides)
    return data


# --- query helpers ------------------------------------------------------

def test_get_expense_by_id_own(app):
    eid = make_expense(1, amount=55.5, description="Mine")
    row = get_expense_by_id(eid, 1)
    assert row["id"] == eid
    assert row["amount"] == 55.5
    assert row["description"] == "Mine"


def test_get_expense_by_id_other_user_or_missing(app):
    other = make_user()
    eid = make_expense(other)
    assert get_expense_by_id(eid, 1) is None
    assert get_expense_by_id(99999, 1) is None


def test_update_expense_own_keeps_owner_and_created_at(app):
    eid = make_expense(1)
    before = fetch_row(eid)
    assert update_expense(eid, 1, 9.99, "Bills", "2026-03-03", "New") == 1
    after = fetch_row(eid)
    assert (after["amount"], after["category"], after["date"], after["description"]) == (
        9.99, "Bills", "2026-03-03", "New",
    )
    assert after["user_id"] == before["user_id"]
    assert after["created_at"] == before["created_at"]


def test_update_expense_other_user_changes_nothing(app):
    other = make_user()
    eid = make_expense(other, amount=10.0)
    assert update_expense(eid, 1, 99.0, "Bills", "2026-03-03", "Hacked") == 0
    assert fetch_row(eid)["amount"] == 10.0


def test_recent_transactions_include_id(app):
    eid = make_expense(1)
    assert eid in [t["id"] for t in get_recent_transactions(1, limit=50)]


# --- GET ----------------------------------------------------------------

def test_get_requires_login(client):
    resp = client.get("/expenses/1/edit")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_prefilled_for_owner(client):
    eid = make_expense(1, amount=77.25, category="Health", date="2026-01-20", description="Pharmacy run")
    login(client)
    resp = client.get(f"/expenses/{eid}/edit")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Edit expense" in html
    assert 'value="77.25"' in html
    assert 'value="2026-01-20"' in html
    assert 'value="Pharmacy run"' in html
    assert 'value="Health" selected' in html


def test_get_other_users_expense_404(client):
    eid = make_expense(make_user())
    login(client)
    assert client.get(f"/expenses/{eid}/edit").status_code == 404


def test_get_missing_expense_404(client):
    login(client)
    assert client.get("/expenses/99999/edit").status_code == 404


# --- POST ---------------------------------------------------------------

def test_post_requires_login(client):
    eid = make_expense(1, amount=10.0)
    resp = client.post(f"/expenses/{eid}/edit", data=valid_form())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert fetch_row(eid)["amount"] == 10.0


def test_post_valid_updates_and_redirects(client):
    eid = make_expense(1)
    login(client)
    resp = client.post(f"/expenses/{eid}/edit", data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    row = fetch_row(eid)
    assert (row["amount"], row["category"], row["date"], row["description"]) == (
        321.5, "Transport", "2026-02-02", "Taxi",
    )


def test_post_blank_description_allowed(client):
    eid = make_expense(1)
    login(client)
    resp = client.post(f"/expenses/{eid}/edit", data=valid_form(description=""))
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "abc"},
        {"category": "Nonsense"},
        {"date": "not-a-date"},
    ],
)
def test_post_invalid_shows_error_and_saves_nothing(client, overrides):
    eid = make_expense(1, amount=10.0, category="Food", date="2026-01-10", description="Keep")
    login(client)
    resp = client.post(f"/expenses/{eid}/edit", data=valid_form(**overrides))
    assert resp.status_code == 200
    assert "auth-error" in resp.get_data(as_text=True)
    row = fetch_row(eid)
    assert (row["amount"], row["category"], row["date"], row["description"]) == (
        10.0, "Food", "2026-01-10", "Keep",
    )


def test_post_other_users_expense_404_unchanged(client):
    eid = make_expense(make_user(), amount=10.0)
    login(client)
    resp = client.post(f"/expenses/{eid}/edit", data=valid_form())
    assert resp.status_code == 404
    assert fetch_row(eid)["amount"] == 10.0


# --- profile ------------------------------------------------------------

def test_profile_shows_edit_link_per_row(client):
    eid = make_expense(1)
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert f"/expenses/{eid}/edit" in html
