# Spec: Add Expense

## Overview
Step 7 lets a logged-in user record a new expense. The `/expenses/add` route currently returns a placeholder string, so the profile page can only ever show seeded data. This step turns it into a real form (GET) and a handler (POST) that validates the input, inserts a row into `expenses` for the current user, and redirects back to `/profile` where the new expense appears in the transaction list, stats and category breakdown. It is the first write path for expenses and sets the validation pattern that Step 8 (edit) will reuse.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` in `database/db.py`)
- Step 3: Login / Logout (`session["user_id"]`, `get_current_user()`)
- Step 4: Profile page (where the user lands after saving)
- Step 5: Backend connection (profile reads live data via `database/queries.py`)

## Routes
- `GET /expenses/add` — render the empty add-expense form (date defaults to today) — logged-in
- `POST /expenses/add` — validate and insert the expense, then redirect to `/profile` — logged-in

Logged-out users are redirected to `/login` for both methods. On validation failure the form is re-rendered with status 200, an error message, and the submitted values preserved. No new route names: the existing `add_expense` endpoint gains `methods=["GET", "POST"]`.

## Database changes
No database changes. The existing `expenses` table (`user_id`, `amount`, `category`, `date`, `description`, `created_at`) already holds everything needed. Categories come from the existing `CATEGORIES` list in `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with Amount (number, step 0.01, min 0.01), Category (select built from `categories`), Date (`type="date"`), and Description (optional text). Submit button plus a Cancel link to `/profile`. Shows `error` in the same `auth-error` style used by login/register.
- **Modify:** `templates/profile.html` — add an "Add expense" link/button to `url_for('add_expense')` near the transactions panel header, and make the empty state point to it.

## Files to change
- `app.py` — implement `add_expense()` for GET and POST; import `CATEGORIES`
- `database/queries.py` — add `create_expense(user_id, amount, category, date, description)` using a parameterised `INSERT`
- `templates/profile.html` — "Add expense" entry point
- `static/css/style.css` — styles for the add-expense form and the profile button, reusing existing `form-group` / `form-input` / `btn-submit` classes where possible

## Files to create
- `templates/add_expense.html`
- `tests/test_add_expense.py` — tests for the route and `create_expense`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency always displays as ₹
- Validate server-side; do not trust the browser's `required`, `min` or `<select>` constraints:
  - `amount` must parse as a number, be finite (reject `nan`/`inf`) and be greater than 0; round to 2 decimals
  - `category` must be one of `CATEGORIES`
  - `date` must parse with `datetime.strptime(value, "%Y-%m-%d")`; store it as that `YYYY-MM-DD` string
  - `description` is optional, stripped, and capped at a sensible length (e.g. 200 chars); store `NULL`/empty consistently with the seed data
- `user_id` comes from the session only — never from the form
- Redirect after a successful POST (Post/Redirect/Get); do not render the profile from the POST
- Close the DB connection in a `finally` block, matching the existing routes
- Jinja autoescaping stays on; do not use `|safe` on user-supplied values
- Keep the `edit_expense` and `delete_expense` placeholders untouched (Steps 8 and 9)

## Tests to write
File: `tests/test_add_expense.py`

| Case | Expected |
|---|---|
| Unauthenticated `GET /expenses/add` | 302 to `/login` |
| Unauthenticated `POST /expenses/add` | 302 to `/login`, no row inserted |
| Logged-in `GET /expenses/add` | 200, form with all categories and today's date prefilled |
| Valid POST | 302 to `/profile`, one new row for that user with the submitted values |
| New expense appears on `/profile` | total and transaction count increase |
| Missing / non-numeric amount | 200, error shown, nothing inserted |
| Zero, negative, `nan` or `inf` amount | 200, error shown, nothing inserted |
| Category not in `CATEGORIES` | 200, error shown, nothing inserted |
| Missing or malformed date (`2026-13-45`, `abc`) | 200, error shown, nothing inserted |
| Empty description | accepted |
| Submitted values preserved on error | form re-renders with the entered amount, category, date, description |
| Forged `user_id` field in the POST | ignored; row belongs to the session user |
| SQL-injection-style description | stored verbatim as text, table intact |

## Definition of done
- [ ] Logged-in user sees an "Add expense" button on `/profile` that opens `/expenses/add`
- [ ] `/expenses/add` shows Amount, Category (all 7 categories), Date (defaulting to today) and Description fields
- [ ] Submitting a valid expense redirects to `/profile` and the expense appears in the transaction list, total spent and category breakdown
- [ ] Amount of 0, negative, blank or non-numeric re-shows the form with an error and saves nothing
- [ ] An invalid date or category re-shows the form with an error and saves nothing
- [ ] After a validation error the previously entered values are still in the form
- [ ] Description is optional
- [ ] Cancel returns to `/profile` without saving
- [ ] Logged-out users visiting `/expenses/add` are redirected to `/login`
- [ ] The new expense belongs to the logged-in user and never appears for another account
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` still show their placeholders
- [ ] `pytest tests/test_add_expense.py` passes
