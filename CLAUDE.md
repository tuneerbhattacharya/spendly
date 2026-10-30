# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly is a Flask + SQLite personal expense tracker (amounts in ₹). It is a step-by-step learning project: the UI is mostly built, while the backend features are placeholders to be implemented in numbered steps.

## Commands

Windows machine: `python3` is a Microsoft Store stub and the `venv` activation does not persist between shell calls. Call the venv's tools by path.

```
venv/Scripts/pip install -r requirements.txt
venv/Scripts/python app.py                 # dev server, debug on, http://127.0.0.1:5001
venv/Scripts/python -m pytest              # pytest + pytest-flask are installed; no tests exist yet
venv/Scripts/python -m pytest path/to/test_file.py::test_name   # single test
```

No linter or build step is configured.

## Architecture

- `app.py` — single Flask app with all routes. Real routes only render templates (`/`, `/register`, `/login`, `/terms`, `/privacy`). The rest (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) return placeholder strings labelled with the step that implements them (Steps 3, 4, 7, 8, 9). Steps 2, 5 and 6 are not yet represented in the code.
- `register`/`login` forms exist but their routes only accept GET, so submitting returns 405 until POST handling is added.
- `database/db.py` — only comments so far; it is to hold `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS`) and `seed_db()`. The DB file is `spendly.db`, which is gitignored.
- `templates/` — Jinja2 pages all extend `base.html` (navbar, Google Fonts, `css/style.css`, `{% block head %}` for page-specific assets). `landing.html` additionally loads `css/landing.css`; the landing page is the most actively developed part (hero, YouTube modal).
- `static/css/style.css` is the shared stylesheet; `static/css/landing.css` is landing-only; `static/js/main.js` is currently empty.

## Conventions

- Commits to date use a `landing: ...` style prefix for landing-page work.
- `claude.exe*` and `.claude/plans/` are gitignored; do not commit the stray `claude.exe` binaries in the project root.
