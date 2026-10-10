# Administrator guide

## Version 2 setup

See CONFIGURATION.md for curricula, country-specific student fields, department access, teacher/student login slots, and self check-in. Administrators can now provision, link, disable, and reset accounts in **Accounts & access**. Health and other modules can additionally be granted to a department through its administrator-defined permissions.

Existing databases migrate without resetting passwords. New student/parent accounts require student links; teachers require staff links; department logins require department links. Existing teachers without a staff link need an admin to add it before self check-in.

## Roles

| Role | Read access | Edit access |
| --- | --- | --- |
| Administrator | All modules, financial ledger, health, conduct, audit | All working modules and school settings |
| Registrar | Directories, timetable, events, notices, library, transport, boarding, attendance | Students, classes, timetable, events, notices, library, transport, boarding |
| Teacher | Student/class directory, timetable, events, notices, attendance, grades, conduct | Attendance, grades, conduct |
| Bursar | Student/class directory, invoices, payments | Invoices, payments |
| Nurse | Student directory, health | Health |
| Parent | Linked student, their attendance/grades/invoices/payments, school events, Everyone/Parents notices | None |
| Student | Own record, own attendance/results/fees, class timetable, curricula, events and student notices | Own current-day check-in only |
| Department | Administrator-defined department module set | Administrator-defined edit module set |

Registrar edits are exactly: students, classes, timetable, events, notices, library, transport, and boarding. Staff maintenance is administrator-only. Access checks run on the server for every request. Teachers currently have school-wide student/grade scope, not assigned-class scope. Nurses and bursars also have school-wide scope within their permitted modules. A parent account links to one student; multiple siblings require a future guardian enrollment model.

All roles can change their own password. Account provisioning and password resets are available to administrators in Accounts & access and through the local host utility.

## Provision accounts

From the extracted application directory:

```sh
python manage.py user school.registrar --role registrar
python manage.py user guardian.example --role parent --student-id 1
```

Enter and confirm the new password when prompted. Passwords never appear in command arguments. Reusing a username resets its password and role. Restart the server after a host-level account change to discard old sessions. Obtain the student ID from a student CSV export. Users and staff records are separate; creating a staff record does not automatically create a login.

Demo accounts all start with the same configured first-run password. Before operational use, reset each account to an individual secret or use distinct provisioned accounts. The administrator can configure the education system and one education level per line in Workspace settings. This supports local names such as nursery, primary, basic education, O-Level, A-Level, college, university, vocational, or equivalent stages without assuming one country's structure. During admission, class placement is intentionally left blank and can be assigned later by authorized school staff; timetable entries still use an existing class.

## Back up and restore

```sh
python manage.py backup backups/school-2026-10-06.db
```

The backup uses SQLite's online backup API and refuses to overwrite an existing file. Keep backups on protected storage outside the application machine as appropriate to your school's recovery plan. Test a copy before relying on it.

To restore: stop the server, preserve the current database, copy the chosen backup to `data/school.db`, then start the server again. Confirm student counts, recent payments, account access, and the chosen backup date. Restoring an old database also restores old password hashes. Exported CSVs are reports, not complete database backups.

## Configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `CEDAR_PORT` | `8765` | Local listening port |
| `CEDAR_DB` | `data/school.db` beside server.py | Alternative database path |
| `CEDAR_INITIAL_PASSWORD` | Randomly generated | First-run bootstrap only; intended for scripted evaluation |

Daily school dates use the configured UTC offset. The interface uses the browser's locale for display. Seeded events are dated October 2026. SQLite timestamps are UTC; adjust the school's offset when daylight-saving time changes. Production deployments should use an explicit IANA school timezone.

If port 8765 is occupied, set a different port and open the matching URL. If the Windows launcher cannot find `py`, install Python from its official distributor or run `python server.py` with the available interpreter.

## Security implemented

- Loopback-only binding.
- Salted PBKDF2 password hashing with 200,000 iterations.
- Cryptographically random, HttpOnly, SameSite=Strict session cookies.
- Session expiry and logout invalidation.
- CSRF token checks and Origin rejection on mutations.
- Server-side role checks and parent record filtering.
- Parameterized SQL for values, with table/module choices constrained by code.
- HTML escaping of record values; CSV formula-prefix neutralization.
- Positive amount checks, integer minor units, serializable payment mutation, overpayment checks.
- Linked student deletion protection and audit logging of record mutations.
- Content Security Policy, nosniff, no-store responses, and static path allowlist.

## Deployment limits

The standard-library server is suited to local evaluation on a trusted host. It does not supply HTTPS, distributed sessions, MFA, email/SMS delivery, external payment collection, attachment storage, hosted sign-in, brute-force rate limits, or production monitoring. The login delay is not a rate-limit system. Audit entries record account/action/module/time, not immutable field-level before-and-after versions.

Before exposing school records to other computers, use a production HTTP stack behind HTTPS, secure cookies, managed secrets, reviewed authentication and object-level access policies, scheduled tested backups, and appropriate monitoring. Also add staff/class references and safe deletion constraints: timetable and class teacher names are currently text values, so changing or deleting their directory records does not cascade. Verify privacy/retention/reporting requirements with the school's responsible team. No jurisdiction-specific compliance claim is made.

Health and conduct notes are free text. File uploads, medical decision support, sensitive-record consent flows, and emergency triage are not implemented. Parents receive read-only views of existing data; results have no draft/publication gate yet. Do not use the prototype to make automated admissions or disciplinary decisions.

## Extension architecture

Generic operational records use a JSON payload with per-module allowlisted fields. Attendance and financial transactions have dedicated relational tables and foreign keys. For production, normalize enrollment, academic terms, subjects, lessons, guardians, staff identities, book loans, transport assignments, and boarding assignments. Keep immutable receipt history and controlled adjustment/reversal workflows rather than editing or deleting posted payments.
