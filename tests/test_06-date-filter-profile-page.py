"""Tests for Step 6: Date filter on the profile page.

Seed expenses (user 1) are dated relative to the current month on days
1, 4, 6, 9, 13, 17, 21, 25.  Expected dates are built from date.today().
"""
from datetime import date

import pytest

from database import db, queries

ALL_DESCRIPTIONS = [
    "Groceries", "Metro card recharge", "Electricity bill", "Pharmacy",
    "Movie night", "New shoes", "Gift", "Dinner out",
]


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


def add_expense(user_id, amount, category, iso_date, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, iso_date, description),
        )
        conn.commit()
    finally:
        conn.close()


def login(client, user_id=1):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def day(n):
    return date.today().replace(day=n).isoformat()


def get_html(client, query=""):
    resp = client.get("/profile" + query)
    return resp, resp.get_data(as_text=True)


def assert_only_shown(html, shown):
    for desc in ALL_DESCRIPTIONS:
        if desc in shown:
            assert desc in html, f"Expected '{desc}' to be listed"
        else:
            assert desc not in html, f"Did not expect '{desc}' to be listed"


# --------------------- query helper tests: stats --------------------- #

def test_stats_range_subset_counts_only_subset(app):
    # days 6..17 -> Electricity 1800, Pharmacy 650, Movie 499, Shoes 2299
    stats = queries.get_summary_stats(1, date_from=day(6), date_to=day(17))
    assert stats["total_spent"] == pytest.approx(5248.00)
    assert stats["transaction_count"] == 4
    assert stats["top_category"] == "Shopping"


def test_stats_from_bound_is_inclusive(app):
    stats = queries.get_summary_stats(1, date_from=day(25), date_to=day(28))
    assert stats["transaction_count"] == 1
    assert stats["total_spent"] == pytest.approx(320.75)


def test_stats_to_bound_is_inclusive(app):
    stats = queries.get_summary_stats(1, date_from=day(1), date_to=day(1))
    assert stats["transaction_count"] == 1
    assert stats["total_spent"] == pytest.approx(450.00)


def test_stats_single_day_range_from_equals_to(app):
    stats = queries.get_summary_stats(1, date_from=day(13), date_to=day(13))
    assert stats["transaction_count"] == 1
    assert stats["top_category"] == "Entertainment"


def test_stats_only_date_from_is_open_ended(app):
    # on or after day 17: Shoes 2299, Gift 200, Dinner 320.75
    stats = queries.get_summary_stats(1, date_from=day(17))
    assert stats["transaction_count"] == 3
    assert stats["total_spent"] == pytest.approx(2819.75)


def test_stats_only_date_to_is_open_ended(app):
    # on or before day 4: Groceries 450, Metro 120.50
    stats = queries.get_summary_stats(1, date_to=day(4))
    assert stats["transaction_count"] == 2
    assert stats["total_spent"] == pytest.approx(570.50)


def test_stats_no_filter_matches_unfiltered(app):
    stats = queries.get_summary_stats(1, date_from=None, date_to=None)
    assert stats["transaction_count"] == 8
    assert stats["total_spent"] == pytest.approx(6339.25)


def test_stats_empty_range_returns_zeros(app):
    stats = queries.get_summary_stats(1, date_from="2000-01-01", date_to="2000-01-31")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


# ------------------ query helper tests: transactions ------------------ #

def test_transactions_range_only_in_range_rows(app):
    txns = queries.get_recent_transactions(1, date_from=day(6), date_to=day(17))
    assert {t["description"] for t in txns} == {
        "Electricity bill", "Pharmacy", "Movie night", "New shoes",
    }


def test_transactions_range_newest_first(app):
    txns = queries.get_recent_transactions(1, date_from=day(6), date_to=day(17))
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)


def test_transactions_bounds_inclusive(app):
    txns = queries.get_recent_transactions(1, date_from=day(6), date_to=day(17))
    descs = {t["description"] for t in txns}
    assert "Electricity bill" in descs, "Expense on 'from' day must be included"
    assert "New shoes" in descs, "Expense on 'to' day must be included"


def test_transactions_only_from(app):
    txns = queries.get_recent_transactions(1, date_from=day(21))
    assert {t["description"] for t in txns} == {"Gift", "Dinner out"}


def test_transactions_only_to(app):
    txns = queries.get_recent_transactions(1, date_to=day(1))
    assert {t["description"] for t in txns} == {"Groceries"}


def test_transactions_empty_range_returns_empty_list(app):
    assert queries.get_recent_transactions(
        1, date_from="2000-01-01", date_to="2000-01-31"
    ) == []


# ------------------- query helper tests: categories ------------------- #

def test_category_breakdown_filtered_only_in_range_categories(app):
    cats = queries.get_category_breakdown(1, date_from=day(6), date_to=day(17))
    assert {c["name"] for c in cats} == {"Bills", "Health", "Entertainment", "Shopping"}
    assert cats[0]["name"] == "Shopping"


def test_category_breakdown_filtered_pct_sums_to_100(app):
    cats = queries.get_category_breakdown(1, date_from=day(6), date_to=day(17))
    assert sum(c["pct"] for c in cats) == 100


@pytest.mark.parametrize("kwargs", [
    {"date_from": 1}, {"date_to": 1}, {"date_from": 1, "date_to": 2},
])
def test_category_breakdown_pct_sums_to_100_for_various_ranges(app, kwargs):
    resolved = {k: day(v if k == "date_from" else v + 20) for k, v in kwargs.items()}
    cats = queries.get_category_breakdown(1, **resolved)
    assert cats, "Expected at least one category in range"
    assert sum(c["pct"] for c in cats) == 100


def test_category_breakdown_filtered_amounts_match_range(app):
    cats = queries.get_category_breakdown(1, date_from=day(6), date_to=day(17))
    total = sum(c["amount"] for c in cats)
    assert total == pytest.approx(5248.00)


def test_category_breakdown_empty_range_returns_empty_list(app):
    assert queries.get_category_breakdown(
        1, date_from="2000-01-01", date_to="2000-01-31"
    ) == []


def test_helpers_params_default_to_none(app):
    # Existing callers (without the new params) must keep working.
    assert queries.get_summary_stats(1)["transaction_count"] == 8
    assert len(queries.get_recent_transactions(1)) == 8
    assert len(queries.get_category_breakdown(1)) == 7


# ----------------------- data isolation (helpers) ----------------------- #

def test_filtered_helpers_exclude_other_users_expenses(app):
    other = make_user()
    add_expense(other, 9999, "Food", day(10), "Other user secret")
    s = queries.get_summary_stats(1, date_from=day(6), date_to=day(17))
    assert s["transaction_count"] == 4
    assert s["total_spent"] == pytest.approx(5248.00)
    txns = queries.get_recent_transactions(1, date_from=day(6), date_to=day(17))
    assert all(t["description"] != "Other user secret" for t in txns)
    cats = queries.get_category_breakdown(1, date_from=day(6), date_to=day(17))
    assert "Food" not in {c["name"] for c in cats}


def test_filtered_helpers_for_other_user_exclude_seed_data(app):
    other = make_user()
    add_expense(other, 100, "Food", day(10), "Mine")
    s = queries.get_summary_stats(other, date_from=day(1), date_to=day(28))
    assert s["transaction_count"] == 1
    assert s["total_spent"] == pytest.approx(100)


# ----------------------------- route tests ----------------------------- #

class TestProfileAuthGuard:
    def test_unauthenticated_with_params_redirects_to_login(self, client):
        resp = client.get(f"/profile?from={day(1)}&to={day(28)}")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_with_invalid_params_redirects_to_login(self, client):
        resp = client.get("/profile?from=not-a-date")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestProfileNoFilter:
    def test_no_params_shows_all_expenses(self, client):
        login(client)
        resp, html = get_html(client)
        assert resp.status_code == 200
        assert "6,339.25" in html
        assert_only_shown(html, ALL_DESCRIPTIONS)

    def test_blank_params_treated_as_no_filter(self, client):
        login(client)
        resp, html = get_html(client, "?from=&to=")
        assert resp.status_code == 200
        assert "6,339.25" in html
        assert_only_shown(html, ALL_DESCRIPTIONS)

    def test_no_params_same_as_blank_params(self, client):
        login(client)
        _, plain = get_html(client)
        _, blank = get_html(client, "?from=&to=")
        assert plain == blank


class TestProfileFilterForm:
    def test_form_has_date_inputs_apply_and_clear(self, client):
        login(client)
        _, html = get_html(client)
        assert 'type="date"' in html
        assert 'name="from"' in html
        assert 'name="to"' in html
        assert 'method="get"' in html.lower()
        assert "Apply" in html
        assert "Clear" in html

    def test_inputs_prefilled_with_applied_values(self, client):
        login(client)
        _, html = get_html(client, f"?from={day(6)}&to={day(17)}")
        assert f'value="{day(6)}"' in html
        assert f'value="{day(17)}"' in html

    def test_inputs_prefilled_only_from(self, client):
        login(client)
        _, html = get_html(client, f"?from={day(6)}")
        assert f'value="{day(6)}"' in html


class TestProfileFilterApplied:
    def test_range_shows_only_in_range_rows(self, client):
        login(client)
        resp, html = get_html(client, f"?from={day(6)}&to={day(17)}")
        assert resp.status_code == 200
        assert_only_shown(
            html, ["Electricity bill", "Pharmacy", "Movie night", "New shoes"]
        )

    def test_range_totals_match(self, client):
        login(client)
        _, html = get_html(client, f"?from={day(6)}&to={day(17)}")
        assert "5,248.00" in html, "Filtered total should be shown"
        assert "6,339.25" not in html, "Unfiltered total should not be shown"

    def test_range_bounds_inclusive_on_page(self, client):
        login(client)
        _, html = get_html(client, f"?from={day(9)}&to={day(13)}")
        assert "Pharmacy" in html
        assert "Movie night" in html
        assert "Electricity bill" not in html
        assert "New shoes" not in html

    def test_only_from_is_open_ended(self, client):
        login(client)
        resp, html = get_html(client, f"?from={day(21)}")
        assert resp.status_code == 200
        assert_only_shown(html, ["Gift", "Dinner out"])

    def test_only_to_is_open_ended(self, client):
        login(client)
        resp, html = get_html(client, f"?to={day(4)}")
        assert resp.status_code == 200
        assert_only_shown(html, ["Groceries", "Metro card recharge"])

    def test_category_breakdown_reflects_range(self, client):
        login(client)
        _, html = get_html(client, f"?from={day(1)}&to={day(1)}")
        assert "Food" in html
        assert_only_shown(html, ["Groceries"])


class TestProfileEmptyRange:
    def test_empty_range_shows_zero_and_empty_state(self, client):
        login(client)
        resp, html = get_html(client, "?from=2000-01-01&to=2000-01-31")
        assert resp.status_code == 200
        assert "₹0.00" in html
        assert "No expenses in this date range." in html
        assert_only_shown(html, [])

    def test_empty_range_hides_unfiltered_total(self, client):
        login(client)
        _, html = get_html(client, "?from=2000-01-01&to=2000-01-31")
        assert "6,339.25" not in html

    def test_no_expenses_user_unfiltered_keeps_original_empty_state(self, client):
        login(client, make_user())
        _, html = get_html(client)
        assert "No expenses yet." in html
        assert "₹0.00" in html


class TestProfileInvalidInput:
    @pytest.mark.parametrize("query", [
        "?from=not-a-date",
        "?to=not-a-date",
        "?from=2026-13-45",
        "?from=2026-02-30",
        "?from=01/02/2026&to=2026-03-01",
        "?from=2026-1-1",
        "?from=%27%3B+DROP+TABLE+expenses%3B--",
        "?from=2026-01-01%27+OR+%271%27%3D%271",
    ])
    def test_invalid_date_returns_200_with_unfiltered_data(self, client, query):
        login(client)
        resp, html = get_html(client, query)
        assert resp.status_code == 200, "Invalid date must not cause an error"
        assert "6,339.25" in html, "Unfiltered total expected on invalid input"
        assert_only_shown(html, ALL_DESCRIPTIONS)

    def test_invalid_date_shows_error_message(self, client):
        login(client)
        _, baseline = get_html(client)
        _, html = get_html(client, "?from=not-a-date")
        assert len(html) > len(baseline), "Expected an inline error message"

    def test_from_later_than_to_returns_200_with_unfiltered_data(self, client):
        login(client)
        resp, html = get_html(client, "?from=2026-02-01&to=2026-01-01")
        assert resp.status_code == 200
        assert "6,339.25" in html
        assert_only_shown(html, ALL_DESCRIPTIONS)

    def test_from_later_than_to_shows_error_message(self, client):
        login(client)
        _, baseline = get_html(client)
        _, html = get_html(client, "?from=2026-02-01&to=2026-01-01")
        assert len(html) > len(baseline), "Expected an inline error message"

    def test_from_later_than_to_current_month_dates(self, client):
        login(client)
        resp, html = get_html(client, f"?from={day(17)}&to={day(6)}")
        assert resp.status_code == 200
        assert "6,339.25" in html
        assert_only_shown(html, ALL_DESCRIPTIONS)

    def test_valid_range_has_no_error_message(self, client):
        login(client)
        _, bad = get_html(client, "?from=not-a-date")
        _, good = get_html(client, f"?from={day(6)}&to={day(17)}")
        # The error text appears only in the invalid response; find what was added.
        _, baseline = get_html(client)
        added = [line for line in bad.splitlines() if line not in baseline.splitlines()]
        assert added, "Expected error markup in invalid response"
        for line in added:
            if line.strip():
                assert line not in good.splitlines(), (
                    "Error markup must not appear for a valid range"
                )

    def test_invalid_date_does_not_modify_data(self, client):
        login(client)
        get_html(client, "?from=%27%3B+DROP+TABLE+expenses%3B--")
        assert queries.get_summary_stats(1)["transaction_count"] == 8


class TestProfileDataIsolation:
    def test_other_users_expenses_never_in_seed_user_filtered_page(self, client):
        other = make_user()
        add_expense(other, 7777, "Food", day(10), "Other user secret")
        login(client)
        _, html = get_html(client, f"?from={day(1)}&to={day(28)}")
        assert "Other user secret" not in html
        assert "7,777" not in html

    def test_other_user_sees_only_own_filtered_expenses(self, client):
        other = make_user()
        add_expense(other, 111, "Food", day(10), "Mine only")
        login(client, other)
        _, html = get_html(client, f"?from={day(1)}&to={day(28)}")
        assert "Mine only" in html
        assert "111.00" in html
        for desc in ALL_DESCRIPTIONS:
            assert desc not in html, f"Seed user's '{desc}' leaked to another user"

    def test_other_user_range_outside_own_expenses_is_empty(self, client):
        other = make_user()
        add_expense(other, 111, "Food", day(10), "Mine only")
        login(client, other)
        _, html = get_html(client, f"?from={day(20)}&to={day(28)}")
        assert "Mine only" not in html
        assert "No expenses in this date range." in html
