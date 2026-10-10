# Cedar School

An original school administration application inspired by the general dashboard structure in the supplied screenshot. The name, interface, CSS artwork, code, and fictional records were created for this project. No screenshot pixels, third-party logos, branding, or assets are included.

## Start

Requires Python 3.10+ and a modern web browser. No third-party packages, build tools, external fonts, or internet connection are needed.

1. Extract the ZIP.
2. On Windows, double-click `start.bat`. Alternatively run `python server.py` in this directory. On macOS/Linux, run `sh start.sh`.
3. Open `http://127.0.0.1:8765` in your browser.
4. On first start, use username `cedar-school` and password `cedar-school01`. Keep the terminal running.
5. Open Settings to change the account password and school details.

The six demo accounts are `cedar-school`, `registrar`, `teacher`, `bursar`, `nurse`, and `parent`. Each initially uses `cedar-school01`. The parent demo is linked to the first fictional student. Passwords are stored as salted PBKDF2 hashes. Sessions expire after eight hours and are cleared when the server stops.

The application creates `data/school.db` automatically and seeds fictional sample records on a fresh database. The downloadable ZIP deliberately excludes the preview database and credentials, so extracting it gives a fresh first-run setup.

## What works

- Configurable curricula and levels for early childhood through tertiary, vocational, and adult learning.
- Country profiles with administrator-defined student fields, validation, and a configurable school date offset.
- Individual department, teacher, student, and parent accounts connected to the same database.
- Administrator account creation, record linking, password reset, and account disabling.
- Teacher/student self check-in, shared admin history, and student attendance synchronization.

See [country and connected account setup](docs/CONFIGURATION.md) to configure these features. Curriculum templates are illustrative structures; official syllabi, grading policies, and reporting requirements must be configured and reviewed by the school.

- Dashboard with live summary cards, month navigation, event calendar, quick actions, and announcements.
- Student admission, search, class filter, editing, lifecycle status, and CSV export.
- Staff and class directories, class capacity checks, and timetable conflict detection.
- Daily attendance with Present, Absent, Late, and Excused states. Saving a visible class updates its marked students without duplicating the daily register.
- Assessment results with validated scores and downloadable student report cards grouped by term.
- Student invoices, partial payments, remaining balances, overpayment prevention, payment ledger, and text receipts.
- Events, notices, library records, transport routes, boarding houses, health notes, and conduct notes.
- Server-enforced roles; parent data scope; restricted health records; change audit.
- CSV reports, printable report overview, school settings, password changes, account provisioning, and online database backups.

Money is stored in integer minor units: 85000 means 850.00. The interface assumes a two-decimal currency. Set the currency before entering real invoices; changing its code does not perform conversion.

## Files

| File | Purpose |
| --- | --- |
| `server.py` | HTTP server, database initialization, APIs, authentication, permissions, validation |
| `config_support.py` | Database migration, country-field validation, accounts, self check-in |
| `public/extended.js` | Curriculum, country, department, account, and check-in interfaces |
| `docs/CONFIGURATION.md` | Country/curriculum setup and linked login workflows |
| `public/index.html` | Browser entry point |
| `public/style.css` | Original responsive navy, sage, and teal design |
| `public/app.js` | Dashboard, forms, tables, register, reporting, exports |
| `manage.py` | Local administrator account and backup utilities |
| `schema.sql` | Database structure reference |
| `tests/test_system.py` | HTTP integration checks using a disposable database |
| `docs/WORKFLOW.md` | Reference analysis and recommended operational workflow |
| `docs/ADMIN_GUIDE.md` | Access matrix, backups, configuration, and limitations |
| `docs/API.md` | API and data contracts |
| `docs/VALIDATION.md` | Verification results and browser QA limit |

## Validate

```sh
python -m unittest discover -s tests -v
```

Tests use a temporary database inside the project folder and remove it afterward. They never use the operational database.

## Operating boundary

This is a functioning local reference application for evaluation and extension, not a certified production student information service. It listens only on the local computer. Before school-wide use, complete the deployment, authorization, retention, accessibility, and recovery work described in `docs/ADMIN_GUIDE.md`.
