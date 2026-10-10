-- Reference schema. server.py initializes the same tables automatically.
PRAGMA foreign_keys=ON;
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, student_id INTEGER, staff_id INTEGER, department_id INTEGER, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE records(id INTEGER PRIMARY KEY, module TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE attendance(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES records(id), day TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(student_id,day));
CREATE TABLE invoices(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES records(id), term TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), due_date TEXT NOT NULL);
CREATE TABLE payments(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id), amount INTEGER NOT NULL CHECK(amount>0), reference TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE checkins(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), day TEXT NOT NULL, checked_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,day));
