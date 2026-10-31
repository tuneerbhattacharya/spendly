from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) restricting expenses.date to an inclusive range."""
    clause = ""
    params = []
    if date_from:
        clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clause += " AND date <= ?"
        params.append(date_to)
    return clause, params


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None

    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    initials = "".join(part[0] for part in row["name"].split()[:2]).upper()
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
        "initials": initials,
    }


# --- SECTION: transactions ---
def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": r["description"] or "",
            "category": r["category"],
            "amount": float(r["amount"]),
        }
        for r in rows
    ]
# --- END SECTION: transactions ---


# --- SECTION: summary ---
def get_summary_stats(user_id, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY SUM(amount) DESC, category LIMIT 1",
            (user_id, *params),
        ).fetchone()
    finally:
        conn.close()

    if totals["n"] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    return {
        "total_spent": float(totals["total"]),
        "transaction_count": totals["n"],
        "top_category": top["category"],
    }
# --- END SECTION: summary ---


# --- SECTION: categories ---
def get_category_breakdown(user_id, date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY SUM(amount) DESC, category",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()

    grand = sum(r["total"] or 0 for r in rows)
    if not rows or grand <= 0:
        return []

    result = []
    for r in rows:
        total = float(r["total"] or 0)
        result.append({
            "name": r["category"],
            "amount": round(total, 2),
            "pct": int(round(total * 100 / grand)),
        })
    diff = 100 - sum(c["pct"] for c in result)
    result[0]["pct"] += diff
    for c in result:
        c["bar"] = max(0, min(100, int(round(c["pct"] / 5.0)) * 5))
    return result
# --- END SECTION: categories ---
