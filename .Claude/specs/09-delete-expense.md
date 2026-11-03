# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense. Each row in the profile's transaction history gets a "Delete" button next to the existing "Edit" link. Clicking it asks the user to confirm, then submits a POST that deletes the row and returns the user to the profile page, where the total spent, transaction count and category breakdown update accordingly. The route replaces the `/expenses/<id>/delete` placeholder ("coming in Step 9"). Deletion is destructive, so it is POST-only (the placeholder's GET handler must go) and strictly scoped to the owner.

## Depends on
- Step 1: Database setup (`expenses` table in `database/db.py`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Backend connection (`database/queries.py` helpers)
- Step 8: Edit expense (the Actions cell in the profile transaction rows, `id` key in `get_recent_transactions`)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense, redirect to `/profile` — logged-in

Behaviour:
- Logged-out users are redirected to `/login` and nothing is deleted.
- If the expense does not exist **or belongs to another user**, return 404 (do not reveal that the id exists).
- GET is not allowed (405); deletion never happens from a link or a prefetch.
- On success, redirect to `/profile` (Post/Redirect/Get).

## Database changes
No database changes. Deleting a row from `expenses` needs no new columns or constraints; no other table references `expenses`. Verified against `database/db.py`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html`: in each transaction row's `txn-actions` cell, add a small `<form method="post" action="{{ url_for('delete_expense', id=t.id) }}">` containing a "Delete" submit button. Add an `onsubmit` / JS confirm ("Delete this expense?") so a misclick does not delete data.

## Files to change
- `app.py` — replace the placeholder `delete_expense(id)` with a `methods=["POST"]` route
- `database/queries.py` — add `delete_expense(expense_id, user_id)` returning the number of rows deleted
- `templates/profile.html` — Delete form/button per row
- `static/css/style.css` — style the Delete button (inline with the Edit link, danger colour), using existing CSS variables
- `static/js/main.js` — confirm-before-submit handler (currently empty), if not done with an inline `onsubmit`

## Files to create
- `tests/test_delete_expense.py` — tests for the query helper and the delete route

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
- The delete must include `user_id = ?` in the `WHERE` clause (`DELETE FROM expenses WHERE id = ? AND user_id = ?`); a user must never be able to delete another user's expense
- Use the `get_db()` / `try ... finally conn.close()` pattern already used in `queries.py`; commit after the `DELETE`
- Route accepts POST only; never delete on GET
- If `delete_expense` removes 0 rows, `abort(404)`
- Redirect after a successful POST; do not render the profile directly
- Keep the existing `get_recent_transactions` output unchanged
- Keep the Edit link and the filter form on the profile page working; the Delete form must not nest inside another form

## Tests to write
File: `tests/test_delete_expense.py`

| Case | Expected |
|---|---|
| `delete_expense` for own expense | returns 1, row gone |
| `delete_expense` for another user's expense | returns 0, row still exists |
| `delete_expense` for a missing id | returns 0 |
| `POST /expenses/<id>/delete` logged out | 302 to `/login`, row still exists |
| `POST /expenses/<id>/delete` as owner | 302 to `/profile`, row gone |
| `POST /expenses/<id>/delete` for another user's expense | 404, row still exists |
| `POST /expenses/99999/delete` | 404 |
| `GET /expenses/<id>/delete` | 405, row still exists |
| `GET /profile` | each transaction row has a delete form posting to its id |
| After delete, `GET /profile` | total spent and transaction count reflect the removal |

## Definition of done
- [ ] Every row in the profile transaction history has a Delete button beside Edit
- [ ] Clicking Delete shows a confirmation; cancelling leaves the expense in place
- [ ] Confirming removes the expense and redirects to `/profile`, where the row is gone and the total spent, transaction count and category breakdown are updated
- [ ] Deleting the last expense shows the empty state without errors
- [ ] Visiting `/expenses/<id>/delete` in the browser (GET) returns 405 and deletes nothing
- [ ] Submitting a delete for another user's expense, or a non-existent id, returns 404 and deletes nothing
- [ ] A delete request while logged out redirects to `/login` and deletes nothing
- [ ] The existing Edit link, date filter and add-expense flow still work unchanged
