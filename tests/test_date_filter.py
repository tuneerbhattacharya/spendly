from datetime import date

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


def add_expense(user_id, amount, category, day_iso, description="x"):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day_iso, description),
        )
        conn.commit()
    finally:
        conn.close()


def login(client, user_id=1):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def day(n):
    """ISO date for day n of the current month (matches how seed_db builds dates)."""
    return date.today().replace(day=n).isoformat()


# Seed expenses by day of month:
#  1 Food 450.00 | 4 Transport 120.50 | 6 Bills 1800.00 | 9 Health 650.00
# 13 Entertainment 499.00 | 17 Shopping 2299.00 | 21 Other 200.00 | 25 Food 320.75


# ---------------------------- unit tests ---------------------------- #

def test_summary_stats_subset(app):
    stats = queries.get_summary_stats(1, day(4), day(13))
    assert stats["transaction_count"] == 4
    assert stats["total_spent"] == pytest.approx(120.50 + 1800.00 + 650.00 + 499.00)
    assert stats["top_category"] == "Bills"


def test_bounds_are_inclusive(app):
    stats = queries.get_summary_stats(1, day(4), day(4))
    assert stats["transaction_count"] == 1
    assert stats["total_spent"] == pytest.approx(120.50)
    txns = queries.get_recent_transactions(1, date_from=day(21), date_to=day(25))
    assert [t["amount"] for t in txns] == [320.75, 200.00]


def test_only_date_from(app):
    stats = queries.get_summary_stats(1, date_from=day(17))
    assert stats["transaction_count"] == 3
    assert stats["total_spent"] == pytest.approx(2299.00 + 200.00 + 320.75)


def test_only_date_to(app):
    stats = queries.get_summary_stats(1, date_to=day(4))
    assert stats["transaction_count"] == 2
    assert stats["total_spent"] == pytest.approx(450.00 + 120.50)


def test_empty_range(app):
    assert queries.get_summary_stats(1, day(2), day(3)) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }
    assert queries.get_recent_transactions(1, date_from=day(2), date_to=day(3)) == []
    assert queries.get_category_breakdown(1, day(2), day(3)) == []


def test_filtered_category_breakdown_sums_to_100(app):
    cats = queries.get_category_breakdown(1, day(1), day(17))
    assert {c["name"] for c in cats} == {
        "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping",
    }
    assert sum(c["pct"] for c in cats) == 100


def test_filter_never_includes_other_users(app):
    other = make_user()
    add_expense(other, 9999.00, "Other", day(5))
    stats = queries.get_summary_stats(1, day(1), day(30))
    assert stats["total_spent"] < 9999.00
    assert queries.get_summary_stats(other, day(1), day(30))["total_spent"] == pytest.approx(9999.00)


def test_no_filter_matches_unfiltered(app):
    assert queries.get_summary_stats(1, None, None) == queries.get_summary_stats(1)
    assert queries.get_category_breakdown(1, None, None) == queries.get_category_breakdown(1)


# ----------------------------- route tests ----------------------------- #

def test_profile_requires_login_with_params(client):
    resp = client.get(f"/profile?from={day(1)}")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_without_params_is_unfiltered(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "6,339.25" in html
    assert "Apply" in html and "Clear" in html


def test_profile_with_valid_range(client):
    login(client)
    html = client.get(f"/profile?from={day(4)}&to={day(13)}").get_data(as_text=True)
    assert "3,069.50" in html  # 120.50 + 1800 + 650 + 499
    assert "Metro card recharge" in html
    assert "Groceries" not in html
    assert "New shoes" not in html
    assert f'value="{day(4)}"' in html
    assert f'value="{day(13)}"' in html


def test_profile_with_empty_range(client):
    login(client)
    resp = client.get(f"/profile?from={day(2)}&to={day(3)}")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "No expenses in this date range." in html


def test_profile_invalid_date_falls_back(client):
    login(client)
    resp = client.get("/profile?from=not-a-date")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Please enter valid dates." in html
    assert "6,339.25" in html


def test_profile_from_after_to_falls_back(client):
    login(client)
    resp = client.get(f"/profile?from={day(20)}&to={day(10)}")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "start date must be on or before the end date" in html
    assert "6,339.25" in html
