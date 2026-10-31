# Spec: Date Filter for Profile Page

## Overview
Step 6 lets a logged-in user narrow the profile page to a date range. Step 5 wired the summary stats, transaction history and category breakdown to live data, but they always cover every expense the user has ever recorded. This step adds an optional `from` / `to` date filter to `GET /profile`, submitted as query parameters, so all three sections (and the total) reflect only expenses inside the chosen range. With no filter, the page behaves exactly as it does today.

## Depends on
- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4: Profile page static UI
- Step 5: Backend connection (`database/queries.py` helpers and the `/profile` view)

## Routes
No new routes. The existing `GET /profile` accepts two optional query parameters:
- `from` — start date, inclusive, `YYYY-MM-DD`
- `to` — end date, inclusive, `YYYY-MM-DD`

Access level stays logged-in. Either parameter may be given alone (open-ended range). A blank value means "no bound". Invalid dates, or `from` later than `to`, must not raise an error: the page renders unfiltered results and shows an inline error message next to the filter form.

## Database changes
No database changes. `expenses.date` is already an ISO `YYYY-MM-DD` string, so range comparison with `date >= ? AND date <= ?` sorts correctly. No new index is required at this stage.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter form above the stat grid: two `<input type="date">` fields (From, To), an "Apply" submit button, and a "Clear" link back to `/profile`. The form uses `method="get"`.
  - Pre-fill the inputs with the currently applied values.
  - Show the validation error message when present.
  - Change the transaction panel title/empty state so it reads sensibly when filtered (e.g. "No expenses in this date range.").

## Files to change
- `app.py` — parse and validate `from` / `to` in `profile()`, pass them to the query helpers, and pass `date_from`, `date_to` and `filter_error` to the template
- `database/queries.py` — add optional `date_from=None, date_to=None` parameters to `get_summary_stats`, `get_recent_transactions` and `get_category_breakdown`
- `templates/profile.html` — filter form and messages as above
- `static/css/style.css` — styles for the filter form, using existing CSS variables

## Files to create
- `tests/test_date_filter.py` — tests for the filtered query helpers and the `/profile` route

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — build the optional `AND date >= ?` / `AND date <= ?` clauses from fixed strings and pass the values as parameters; never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency always displays as ₹
- Validate dates server-side with `datetime.strptime(value, "%Y-%m-%d")`; do not trust the browser's date input
- New parameters on the query helpers must default to `None` so existing callers and the Step 5 tests keep working
- The filter applies to all three sections consistently: stats, transaction list and category breakdown
- `pct` values in the category breakdown must still sum to 100 for the filtered set
- A range with no matching expenses returns zeros and empty lists, never an exception
- The filter only ever applies to the logged-in user's own expenses (`user_id = ?` stays in every query)

## Tests to write
File: `tests/test_date_filter.py`

| Case | Expected |
|---|---|
| `get_summary_stats` with `date_from` and `date_to` covering a subset | totals and count only include that subset |
| Range bounds are inclusive | an expense dated exactly on `from` or `to` is counted |
| Only `date_from` given | everything on or after it |
| Only `date_to` given | everything on or before it |
| Range with no expenses | zeros, `"—"`, empty lists |
| Filtered category breakdown | `pct` sums to 100 |
| `GET /profile` with no params | same output as Step 5 |
| `GET /profile?from=…&to=…` as seed user | 200, only in-range rows shown, totals match |
| `GET /profile?from=not-a-date` | 200, unfiltered data plus an error message |
| `GET /profile?from=2026-02-01&to=2026-01-01` | 200, unfiltered data plus an error message |
| Another user's expenses | never appear in filtered results |
| Unauthenticated `GET /profile?from=…` | 302 to `/login` |

## Definition of done
- [ ] `/profile` shows From and To date inputs, an Apply button and a Clear link
- [ ] Submitting a range updates the URL to `/profile?from=YYYY-MM-DD&to=YYYY-MM-DD` and the inputs stay filled in
- [ ] Total spent, transaction count, top category, the transaction list and the category breakdown all reflect only the chosen range
- [ ] Expenses dated exactly on the From and To days are included
- [ ] Setting only From, or only To, works as an open-ended range
- [ ] A range with no expenses shows ₹0.00, 0 transactions and the empty-state messages, with no errors
- [ ] An invalid date or a From later than To shows an error message and falls back to unfiltered results (no 500)
- [ ] Clicking Clear returns to the full, unfiltered profile
- [ ] Category percentages in a filtered view still add up to 100 %
- [ ] Visiting `/profile` with no query parameters looks and behaves exactly as before
- [ ] Logged-out users are still redirected to `/login`
