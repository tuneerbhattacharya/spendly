# Spec: Login and Logout

## Overview
Make sign-in work. `/login` renders a form but accepts only GET, so submitting returns 405, and `/logout` is a placeholder string. This step adds POST handling that checks the email and password against the `users` table and stores the user in a Flask session, plus a working logout that clears it. The navbar then reflects whether someone is signed in. Registration (Step 2) creates accounts, and every later page (profile, expenses) needs to know who is signed in, so this step provides that identity.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`).
- Step 2 — Registration (users can be created; `login()` already shows the `registered` notice).

## Routes
- `GET /login` — render the sign-in form; if already signed in, redirect to `/profile` — public (already exists, gains the redirect)
- `POST /login` — verify credentials, start a session, redirect to `/profile`; on failure re-render the form with an error — public
- `GET /register` — if already signed in, redirect to `/profile` instead of showing the form — public (already exists)
- `GET /logout` — clear the session and redirect to `/` — logged-in (harmless if not signed in)

`/profile` is still the Step 4 placeholder string. It is only the redirect target for now.

## Database changes
No database changes. `users.email` and `users.password_hash` are all that is needed. Checked against `database/db.py`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/base.html` — the navbar shows "Sign in" and "Get started" when signed out. When signed in, it shows the user's name (linking to `profile`) and a "Sign out" link to `logout`.
  - `templates/login.html` — keep the typed email in the field after a failed attempt (never the password). The `error` and `registered` blocks already exist.

## Files to change
- `app.py` — secret key, `session` import, `login()` POST, `logout()`, redirect for signed-in users on `/login` and `/register`, and a context processor that supplies the current user to templates.
- `templates/base.html`
- `templates/login.html`
- `static/css/style.css` — only if the signed-in navbar needs a small style for the user name. It must use existing CSS variables.

## Files to create
None.

## New dependencies
No new dependencies. Use Flask's built-in `session` and `werkzeug.security.check_password_hash`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug; verify with `check_password_hash`, never compare hashes or plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Set `app.secret_key` from the `SECRET_KEY` environment variable, with a clearly marked development-only fallback so the app still starts locally. Never commit a real secret.
- Store only `user_id` in the session. Look up the name from the database when rendering, so a stale session cannot show old data.
- Email is trimmed and lowercased before the lookup, matching registration.
- Use one generic error for every failure, "Invalid email or password.", whether the email is unknown or the password is wrong. Do not reveal which one failed.
- Call `session.clear()` before setting `user_id` on login, so no old session data carries over.
- Logout clears the whole session with `session.clear()`.
- Close the DB connection in a `try`/`finally`, following `database/db.py` and `register()`.
- On error, return the form with HTTP 200 and the `error` variable. On success, use Post/Redirect/Get.
- If a `user_id` in the session no longer matches a row (for example the user was deleted), treat the visitor as signed out.
- Do not build the profile page or route protection decorators. Those belong to Step 4 and later. The `/register` flow itself still does not log the user in.

## Definition of done
- [ ] `GET /login` still renders the form (200) for a signed-out visitor.
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects to `/profile` (the Step 4 placeholder text appears).
- [ ] Signing in is case-insensitive on the email (`DEMO@Spendly.com` works).
- [ ] A wrong password and an unknown email both show exactly "Invalid email or password." with HTTP 200, and no session is created.
- [ ] After a failed attempt the email field keeps its value and the password field is empty.
- [ ] After sign-in the navbar shows the user's name and a "Sign out" link, and no longer shows "Sign in" or "Get started".
- [ ] Visiting `/login` or `/register` while signed in redirects to `/profile`.
- [ ] `GET /logout` redirects to `/`, and the navbar goes back to "Sign in" and "Get started".
- [ ] After logout, visiting `/login` shows the form again (the session is really gone).
- [ ] Registering a new user, then signing in with those credentials, works end to end.
- [ ] The app starts without errors, and `/`, `/terms` and `/privacy` still return 200 both signed in and signed out.
