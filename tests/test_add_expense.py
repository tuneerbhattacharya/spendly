from datetime import date

import pytest

from database import db


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


def expense_count(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def valid_form(**overrides):
    data = {
        "amount": "250.50",
        "category": "Food",
        "date": "2026-01-15",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


# --- auth ---------------------------------------------------------------

def test_get_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_requires_login_and_inserts_nothing(client):
    before = expense_count()
    resp = client.post("/expenses/add", data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert expense_count() == before


# --- GET ----------------------------------------------------------------

def test_get_renders_form(client):
    login(client)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for category in db.CATEGORIES:
        assert f'value="{category}"' in html
    assert date.today().isoformat() in html


# --- successful POST ----------------------------------------------------

def test_valid_post_inserts_and_redirects(client):
    login(client)
    before = expense_count(1)
    resp = client.post("/expenses/add", data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert expense_count(1) == before + 1

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["amount"] == 250.50
    assert row["category"] == "Food"
    assert row["date"] == "2026-01-15"
    assert row["description"] == "Lunch"


def test_new_expense_appears_on_profile(client):
    login(client)
    client.post("/expenses/add", data=valid_form(description="Unique snack"))
    html = client.get("/profile").get_data(as_text=True)
    assert "Unique snack" in html
    assert "₹250.50" in html


def test_empty_description_accepted(client):
    login(client)
    before = expense_count(1)
    resp = client.post("/expenses/add", data=valid_form(description=""))
    assert resp.status_code == 302
    assert expense_count(1) == before + 1


# --- validation failures ------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": ""},
        {"amount": "abc"},
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "nan"},
        {"amount": "inf"},
        {"category": "Gambling"},
        {"category": ""},
        {"date": ""},
        {"date": "abc"},
        {"date": "2026-13-45"},
        {"description": "x" * 201},
    ],
)
def test_invalid_input_rejected(client, overrides):
    login(client)
    before = expense_count()
    resp = client.post("/expenses/add", data=valid_form(**overrides))
    assert resp.status_code == 200
    assert 'class="auth-error"' in resp.get_data(as_text=True)
    assert expense_count() == before


def test_values_preserved_on_error(client):
    login(client)
    resp = client.post(
        "/expenses/add",
        data=valid_form(amount="-1", category="Health", description="Keep me"),
    )
    html = resp.get_data(as_text=True)
    assert 'value="-1"' in html
    assert 'value="2026-01-15"' in html
    assert 'value="Keep me"' in html
    assert 'value="Health" selected' in html


# --- security -----------------------------------------------------------

def test_forged_user_id_ignored(client):
    other = make_user()
    login(client, user_id=1)
    before_other = expense_count(other)
    client.post("/expenses/add", data=valid_form(user_id=str(other)))
    assert expense_count(other) == before_other


def test_sql_injection_description_stored_verbatim(client):
    login(client)
    payload = "x'); DROP TABLE expenses; --"
    client.post("/expenses/add", data=valid_form(description=payload))
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT description FROM expenses WHERE user_id = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["description"] == payload
