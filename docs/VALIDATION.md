# Validation

Verified on 6 October 2026 using Python 3.14 on Windows.

## Version 2 checks

The expanded integration suite passes 19 checks. Added coverage verifies country-specific required fields and allowed choices, curriculum-specific levels, administrator account linking, department permission boundaries, disabled account/session rejection, student data scope, idempotent daily self check-in, teacher attendance, retention of existing staff-marked student statuses, legacy database migration, and rejection of a mismatched login workspace.

Node.js syntax checks pass for both JavaScript files. Template checks execute rendering functions for all 22 pages plus the dynamic student-field and student/teacher check-in controls. These are source-level rendering checks; interactive browser layout, keyboard behavior, and downloads remain visually unverified.

The automated suite creates a disposable SQLite database and exercises the actual HTTP handler over loopback. It covers:

1. Anonymous request rejection, session login/logout, and CSRF enforcement.
2. Parent student scoping and rejected cross-role mutations.
3. Daily attendance upsert without duplicate student/date records.
4. Invoice balances, partial payments, negative amount rejection, and overpayment rejection.
5. Student creation, activation, deletion, and linked-history deletion protection.
6. Timetable conflict rejection and out-of-range grade rejection.
7. Nurse health entry, teacher health-data exclusion, and administrator audit visibility.
8. Successful HTML, JavaScript, and stylesheet delivery with response security policy.
9. Password length validation, password change, and rejection of the old password.
10. Class capacity enforcement.
11. Concurrent payment requests: one succeeds and the other is rejected when their combined amount would overpay.

Command: `python -m unittest discover -s tests -v`.

The server source also passes Python compilation. The browser automation tool could not connect to the loopback preview in this environment, so responsive visual rendering, JavaScript execution, keyboard navigation, and browser download behavior have not been visually verified. The delivered browser source and CSS were inspected, but that does not substitute for browser QA. Run the application locally and complete that review before operational use.

No production deployment or school-specific compliance certification was performed. See ADMIN_GUIDE.md for operating limits.
