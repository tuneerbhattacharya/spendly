import pytest

from database import db, queries


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


def make_user(name="New Person", email="new@example.com"):
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


def login(client, user_id=1):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


# ---------------------------- unit tests ---------------------------- #

def test_get_user_by_id_found(app):
    user = queries.get_user_by_id(1)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["initials"] == "DU"
    assert len(user["member_since"].split()) == 2


def test_get_user_by_id_missing(app):
    assert queries.get_user_by_id(9999) is None


def test_summary_stats_with_expenses(app):
    stats = queries.get_summary_stats(1)
    assert stats["total_spent"] == pytest.approx(6339.25)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_summary_stats_without_expenses(app):
    uid = make_user()
    assert queries.get_summary_stats(uid) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions_newest_first(app):
    txns = queries.get_recent_transactions(1)
    assert len(txns) == 8
    assert set(txns[0]) == {"date", "description", "category", "amount"}
    assert txns[0]["description"] == "Dinner out"
    assert txns[-1]["description"] == "Groceries"


def test_recent_transactions_limit(app):
    assert len(queries.get_recent_transactions(1, limit=3)) == 3


def test_recent_transactions_empty(app):
    assert queries.get_recent_transactions(make_user()) == []


def test_category_breakdown(app):
    cats = queries.get_category_breakdown(1)
    assert len(cats) == 7
    assert cats[0]["name"] == "Shopping"
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100
    assert all(c["bar"] % 5 == 0 for c in cats)


def test_category_breakdown_empty(app):
    assert queries.get_category_breakdown(make_user()) == []


def test_queries_scoped_to_user(app):
    uid = make_user()
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, 10, 'Food', '2026-01-01', 'Snack')",
            (uid,),
        )
        conn.commit()
    finally:
        conn.close()
    assert queries.get_summary_stats(uid)["transaction_count"] == 1
    assert queries.get_summary_stats(1)["transaction_count"] == 8


# ----------------------------- route tests ----------------------------- #

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_seed_user(client):
    login(client)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹" in html
    assert "6,339.25" in html
    assert "Shopping" in html
    assert html.index("Dinner out") < html.index("Groceries")
    for category in db.CATEGORIES:
        assert category in html


def test_profile_new_user_empty_state(client):
    login(client, make_user())
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "No expenses yet." in html
