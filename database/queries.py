from datetime import datetime

from database.db import get_db


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
def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
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
def get_summary_stats(user_id):
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category LIMIT 1",
            (user_id,),
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
def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY SUM(amount) DESC, category",
            (user_id,),
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
