# Spec: Registration

## Overview
Make the existing `/register` form work. Today the page renders but the route only accepts GET, so submitting the form returns 405. This step adds POST handling that validates the input, hashes the password, creates a row in `users`, and sends the new user to the login page. It is the first feature built on the Step 1 data layer and is required before login (Step 3) can have anyone to sign in.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`).

## Routes
- `GET /register` — render the registration form — public (already exists, unchanged)
- `POST /register` — validate the form, create the user, redirect to `/login` on success; re-render the form with an error message on failure — public

## Database changes
No database changes. The existing `users` table (`name`, `email` UNIQUE, `password_hash`, `created_at`) is sufficient.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — the form and the `{% if error %}` block already exist. Re-fill the `name` and `email` inputs from the submitted values on error (the password is never re-filled). Add a `minlength="8"` attribute to the password input.
  - `templates/login.html` — show a "Account created, please sign in" message when arriving after a successful registration. This needs `login()` to pass a `success` message, so check the template for an existing block to reuse before adding markup.

## Files to change
- `app.py` — `register()` accepts `GET` and `POST`, and `login()` accepts a registration notice. Import `request`, `redirect`, `url_for`, `sqlite3` and `generate_password_hash`.
- `templates/register.html`
- `templates/login.html`
- `static/css/style.css` — only if a success-message style is needed. It must reuse the existing CSS variables, for example `--accent-light` and `--accent`.

## Files to create
None.

## New dependencies
No new dependencies. Use `werkzeug.security` and the standard library `sqlite3`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validation, all server-side (the HTML `required` attributes are not enough):
  - `name` — trimmed, non-empty
  - `email` — trimmed, lowercased, non-empty, contains `@`
  - `password` — at least 8 characters
- Catch `sqlite3.IntegrityError` on insert and show "An account with this email already exists." Do not do a separate SELECT-then-INSERT check, because the UNIQUE constraint is the source of truth.
- Always close the DB connection (`try`/`finally`), following the pattern in `database/db.py`.
- On error, return the form with HTTP 200 and the `error` variable, which the template already supports.
- On success, use the Post/Redirect/Get pattern: `redirect(url_for("login"))`.
- Do not log the user in. Sessions and login belong to Step 3.
- `/register` stays a plain function route. Do not add Flask-WTF or any other form library.

## Definition of done
- [ ] `GET /register` still renders the form (200).
- [ ] Submitting valid details creates a row in `users` with a hashed password. `password_hash` is not the plain text, and `check_password_hash` accepts the original password.
- [ ] After a successful registration the browser lands on `/login`.
- [ ] Submitting an email that already exists (for example `demo@spendly.com`) shows "An account with this email already exists." and creates no new row.
- [ ] Registering `Test@Example.com` and then `test@example.com` is treated as a duplicate (email is lowercased).
- [ ] A password shorter than 8 characters shows an error and creates no row.
- [ ] An empty or whitespace-only name or email shows an error and creates no row.
- [ ] On any error, the name and email fields keep what the user typed and the password field is empty.
- [ ] The app starts without errors and `/`, `/login`, `/terms` and `/privacy` still return 200.
