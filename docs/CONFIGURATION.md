# Country, curriculum, department, and connected attendance setup

## Set up any school structure

This version supports configurable school systems. It does not contain every country's approved syllabus or automatically certify compliance with local education rules. The four supplied curriculum records are illustrative year-based, grade-based, stage-based, and tertiary/vocational structures. They are editable templates, not official national curricula.

1. Sign in as an administrator.
2. Open **Curricula & systems** and edit a starter or create a curriculum. Enter your school's approved curriculum name, country/scope, one level per line, subjects, and grading guidance. You may keep multiple curricula in the same school.
3. Open **Classes**. Create local classes or cohorts using any name, such as P1A, Grade 4 Blue, Year 10, Diploma 1, or Semester 2. Select a curriculum and one of its levels. Add teacher, room, and capacity.
4. Open **Students** and edit details, curriculum, level, class, guardian, and status. Levels attached to a curriculum are validated against that curriculum. Classes not attached to a curriculum use Settings' general levels.
5. Keep assessment scores and maximums appropriate to each subject. Curriculum grading guidance is descriptive; the report calculator still uses assessment percentages and their simple mean. Weighted scoring, competency outcomes, official transcripts, automatic grade bands, and a complete national syllabus catalogue require further institution-specific implementation.

Curriculum/class setup spans early childhood, primary, secondary, sixth-form equivalents, college, university, vocational, and adult learning through editable level names. Class naming and subject guidance are flexible; automated promotion, degree credits, and enrollment history remain future work.

## Configure country-specific student details

1. Open **Country student profiles**. Add the country profile your school needs.
2. Enter a two-letter uppercase country code; XX represents a custom/international setup. Use the same code in school Settings.
3. Define student fields, one per line, using:

```text
key|Label|type|required|choices
learner_number|Local learner number|text|yes
district|District / region|text|no
birth_date|Date of birth|date|no
learning_track|Learning track|select|no|General,Vocational
```

Supported types: text, date, number, select. `yes`, `true`, or `required` marks a mandatory field. Keys must use lowercase letters, digits, and underscores, starting with a letter. Select choices are comma-separated.

4. In **Settings**, enter the school country, code, matching profile, and school UTC offset in minutes. Save.
5. Reopen a student form. The active profile's fields appear under Local student details. Required fields and select choices are enforced by the server.

Existing custom values are retained when the active profile changes. A new required field is enforced when a student is next saved; configuration does not fabricate missing historical data. CSV exports include the custom field object as JSON. Select a custom profile for any country rather than assuming example fields satisfy government reporting requirements.

The date for self check-in is computed on the server using the school's configured offset. UTC+3 is 180 minutes; UTC-5 is -300. This is a fixed offset, not an IANA timezone with automatic daylight-saving transitions. Update it when the local offset changes.

## Department credentials and permissions

1. Open **Departments** and adapt the predefined Admissions, Finance, Academics, Library, Transport, Boarding, and Health departments, or create others.
2. Enter comma-separated read and edit module names. The form lists valid names. Edit permission includes read access. Departments cannot manage accounts, school settings, country profiles, or other department permission definitions.
3. Open **Accounts & access** and create a unique login with role **department**, a strong initial password, and the corresponding department link.
4. Give credentials to the authorized staff member through your school's normal secure process. The application does not send credentials by email.

Examples:

| Department | Read modules | Edit modules |
| --- | --- | --- |
| Finance | students, classes, invoices, payments | invoices, payments |
| Library | library | library |
| Transport | transport | transport |
| Academic office | students, classes, curricula, timetable, grades, attendance | grades, attendance |
| Admissions | students, classes, curricula | students |

Use individually named department accounts where several people work in a department; all may link to the same department. Do not share one person's password. Admins can edit roles, reset passwords, or disable accounts. Updated credentials invalidate existing sessions. Account lists never include password hashes.

## Teacher and student login slots

The sign-in screen has separate Teacher, Student, Department, Parent, and administrative workspace choices. All authenticate against the same users table and school database. Choosing a workspace does not grant its role; the server checks the account's actual role.

- **Teacher:** create an active staff record, then create a teacher account linked to that staff ID.
- **Student:** create an active student record, then create a student account linked to that student ID.
- **Parent:** link a parent account to its student record.

Only administrators provision accounts; students do not create anonymous accounts or choose their own record links. Student accounts see their own student record, attendance, assessment results, invoices, payments, and class timetable, plus relevant announcements. Parent scope remains linked to one student. Teachers retain the existing school-wide teaching scope; class-assignment permissions require a future enrollment/access model.

## Connected daily attendance

Students and teachers open **Daily check-in** and click **Register today's attendance**. The server uses the authenticated user and current school date; clients cannot supply another person or a historical date. The unique user/date key prevents repeated check-in from duplicating records.

Student check-in creates Present in the shared student register only when no register entry exists. Existing Present, Absent, Late, or Excused statuses marked by staff are retained for review. Check-in history and official register status are separate evidence. Teachers record their own daily check-in here and manage student class attendance under Attendance. Teacher check-ins do not mark every student present.

Administrators see teacher and student check-ins together. Students and teachers see only their own check-in history. Check-ins record authenticated actions, not independently verified physical presence; proximity checks, attendance approvals, device trust, biometrics, and arrival-time-based lateness rules are not implemented.

## Update an existing installation

Back up the existing SQLite database first. Replace source files with this version and start the server. It automatically adds account-link columns, active flags, the check-in table, country settings, and starter profiles without recreating existing accounts or student records. Existing passwords are retained. Existing teacher accounts without a staff link must be linked in Accounts & access before they can self check in.

The source ZIP excludes operational databases. To preserve your data, replace source files in the existing installation rather than discarding its data directory. This remains a local application; users on different devices need a reviewed shared-host deployment with HTTPS and production authentication infrastructure.
