"""Local administrator utilities. Run while signed into the trusted host account."""
import argparse
import getpass
from contextlib import closing
from pathlib import Path
import sqlite3
import server

parser=argparse.ArgumentParser(description='Cedar School administrator utilities')
commands=parser.add_subparsers(dest='command',required=True)
backup=commands.add_parser('backup',help='Create an online SQLite backup')
backup.add_argument('destination')
account=commands.add_parser('user',help='Create an account or reset its password and role')
account.add_argument('username')
account.add_argument('--role',required=True,choices=list(server.WRITES))
account.add_argument('--student-id',type=int)
account.add_argument('--staff-id',type=int)
account.add_argument('--department-id',type=int)
args=parser.parse_args()
if not server.DB.exists(): parser.error('Run server.py once to initialize the database.')
if args.command=='backup':
 target=Path(args.destination).resolve()
 if target.exists(): parser.error('Destination already exists. Choose a new backup filename.')
 if target==server.DB.resolve(): parser.error('Backup destination cannot be the source database.')
 target.parent.mkdir(parents=True,exist_ok=True)
 with server.connection() as source, closing(sqlite3.connect(target)) as dest:
  source.backup(dest)
 print('Backup saved:',target)
else:
 if args.role in {'parent','student'} and not args.student_id: parser.error('Parents and students need --student-id.')
 if args.role=='teacher' and not args.staff_id:parser.error('Teachers need --staff-id.')
 if args.role=='department' and not args.department_id:parser.error('Department accounts need --department-id.')
 password=getpass.getpass('New password (12+ characters): ')
 if len(password)<12: parser.error('Password must have at least 12 characters.')
 if password!=getpass.getpass('Confirm password: '): parser.error('Passwords do not match.')
 with server.connection() as c:
  server.config_support.migrate(c)
  if args.student_id and not c.execute("SELECT 1 FROM records WHERE id=? AND module='students'",(args.student_id,)).fetchone(): parser.error('Student ID not found.')
  for value,module in ((args.staff_id,'staff'),(args.department_id,'departments')):
   if value and not c.execute('SELECT 1 FROM records WHERE id=? AND module=?',(value,module)).fetchone():parser.error(module+' record not found.')
  c.execute('INSERT INTO users(username,password,role,student_id,staff_id,department_id,active) VALUES(?,?,?,?,?,?,1) ON CONFLICT(username) DO UPDATE SET password=excluded.password,role=excluded.role,student_id=excluded.student_id,staff_id=excluded.staff_id,department_id=excluded.department_id,active=1',(args.username,server.hash_password(password),args.role,args.student_id if args.role in {'parent','student'} else None,args.staff_id if args.role=='teacher' else None,args.department_id if args.role=='department' else None))
  c.execute('INSERT INTO audit(username,action,target) VALUES(?,?,?)',('local-admin','ACCOUNT_UPDATE',args.username))
 print('Account saved. Restart the server to invalidate existing sessions for this account.')
