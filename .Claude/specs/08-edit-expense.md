# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user correct an existing expense. Each row in the profile's transaction history gets an "Edit" link that opens a form pre-filled with that expense's amount, category, date and description. Submitting the form validates the input and updates the row, then returns the user to the profile page. The route replaces the `GET /expenses/<id>/edit` placeholder ("coming in Step 8"). It builds on Step 7 (add expense), whose form and validation this step reuses so adding and editing behave the same way.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` list in `database/db.py`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Backend connection (`database/queries.py` helpers)
- Step 7: Add expense (the expense form template and validation logic). Step 7 currently lives on `feature/add-expense` and is not merged to `main`. It must be merged, or its form/validation rebased in, before this step is implemented.

## Routes
- `GET /expenses/<int:id>/edit` — show the expense form pre-filled with the expense's current values — logged-in
- `POST /expenses/<int:id>/edit` — validate the submitted fields, update the expense, redirect to `/profile` — logged-in

Behaviour:
- Logged-out users are redirected to `/login`.
- If the expense does not exist **or belongs to another user**, return 404 (do not reveal that the id exists).
- On validation failure, re-render the form with an error message and the submitted values (status 200); nothing is saved.

## Database changes
No database changes. The existing `expenses` columns (`amount`, `category`, `date`, `description`) are all editable; `id`, `user_id` and `created_at` are never changed. Verified against `database/db.py`.

## Templates
- **Create:** none, if Step 7's shared expense form template is reused (expected name e.g. `templates/expense_form.html`; adjust to whatever Step 7 actually created)
- **Modify:**
  - Step 7's expense form template: make heading, submit label and form `action` depend on whether an existing expense is being edited ("Edit expense" / "Save changes" vs "Add expense")
  - `templates/profile.html`: add an "Edit" link in each transaction row (new column or action cell) pointing to `url_for('edit_expense', id=t.id)`; update the empty-state `colspan` to match the new column count

## Files to change
- `app.py` — implement `edit_expense(id)` for `GET` and `POST`; reuse Step 7's validation
- `database/queries.py` — add `id` to the dicts returned by `get_recent_transactions`; add `get_expense_by_id(expense_id, user_id)` and `update_expense(expense_id, user_id, amount, category, date, description)`
- `templates/profile.html` — Edit link per row
- The Step 7 expense form template — edit mode support
- `static/css/style.css` — style for the Edit link/action cell, using existing CSS variables

## Files to create
- `tests/test_edit_expense.py` — tests for the query helpers and the edit route

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
- Every read and write of an expense must include `user_id = ?` in the `WHERE` clause (`... WHERE id = ? AND user_id = ?`); a user must never be able to view or change another user's expense
- Validate server-side, same rules as Step 7: amount is a number greater than 0; category is one of `CATEGORIES`; date parses with `datetime.strptime(value, "%Y-%m-%d")`; description is optional and stripped
- Use the `get_db()` / `try ... finally conn.close()` pattern already used in `queries.py`; commit after the `UPDATE`
- Redirect after a successful POST (Post/Redirect/Get); do not render the profile directly
- Keep `get_recent_transactions` output backwards compatible: only add the `id` key, do not rename or remove existing keys, so existing tests keep passing
- Do not implement delete (Step 9) in this step

## Tests to write
File: `tests/test_edit_expense.py`

| Case | Expected |
|---|---|
| `get_expense_by_id` for own expense | returns the row |
| `get_expense_by_id` for another user's expense / missing id | returns `None` |
| `update_expense` for own expense | row changed, `user_id` and `created_at` unchanged |
| `update_expense` for another user's expense | no rows changed |
| `GET /expenses/<id>/edit` logged out | 302 to `/login` |
| `GET /expenses/<id>/edit` as owner | 200, fields pre-filled |
| `GET /expenses/<id>/edit` for another user's expense | 404 |
| `GET /expenses/99999/edit` | 404 |
| `POST` valid data as owner | 302 to `/profile`, values updated in DB |
| `POST` amount `0`, negative or non-numeric | 200, error shown, DB unchanged |
| `POST` category not in `CATEGORIES` | 200, error shown, DB unchanged |
| `POST` invalid date | 200, error shown, DB unchanged |
| `POST` to another user's expense | 404, DB unchanged |
| `GET /profile` | each transaction row has an Edit link to its id |

## Definition of done
- [ ] Every row in the profile transaction history has an Edit link
- [ ] Clicking Edit opens `/expenses/<id>/edit` with amount, category, date and description pre-filled and the page titled for editing
- [ ] Changing fields and submitting redirects to `/profile`, where the row, the total spent, and the category breakdown show the new values
- [ ] Clearing the description and saving works (description is optional)
- [ ] Submitting an amount of 0, a negative number or text shows an error, keeps the entered values, and saves nothing
- [ ] Submitting an invalid date or unknown category shows an error and saves nothing
- [ ] Visiting `/expenses/<id>/edit` for another user's expense, or a non-existent id, returns 404
- [ ] Visiting the edit URL while logged out redirects to `/login`
- [ ] Editing does not change the expense's owner or its created timestamp
- [ ] The existing profile page, date filter and add-expense flow still work unchanged
