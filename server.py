"""Cedar School — dependency-free, local school administration application."""
import config_support
import sys
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from datetime import date
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('CEDAR_DB', str(ROOT / 'data' / 'school.db')))
SESSIONS = {}
LOCK = threading.Lock()
MODULES = {
 'curricula': ['name','country','levels','subjects','grading','description'],
 'country_profiles': ['name','country_code','student_fields'],
 'departments': ['name','read_modules','write_modules'],
 'students': ['name','level','curriculum_id','class_name','guardian','phone','status'],
 'staff': ['name','role','email','phone','status'],
 'classes': ['name','level','curriculum_id','teacher','room','capacity'],
 'timetable': ['name','class_name','teacher','room','weekday','start_time','end_time'],
 'events': ['name','event_date','category','description'],
 'notices': ['name','audience','description'],
 'library': ['name','author','borrower','due_date','status'],
 'transport': ['name','driver','vehicle','capacity'],
 'boarding': ['name','warden','capacity','occupancy'],
 'health': ['student_id','category','description','record_date'],
 'conduct': ['student_id','category','description','record_date'],
 'grades': ['student_id','subject','term','score','maximum'],
}
DEFAULT_EDUCATION_LEVELS = ['Nursery / Early childhood','Primary','Lower secondary / O-Level','Upper secondary / A-Level','University / Tertiary']
WRITES = {
 'admin': set(MODULES) | {'attendance','invoices','payments','settings'},
 'registrar': {'students','classes','timetable','events','notices','library','transport','boarding'},
 'teacher': {'attendance','grades','conduct'},
 'bursar': {'invoices','payments'},
 'nurse': {'health'},
 'parent': set(),
 'student': set(),
 'department': set(),
}
READS = {
 'student': {'students','classes','curricula','events','notices','timetable','attendance','grades','invoices','payments'},
 'department': set(),
 'admin': set(MODULES)|{'attendance','invoices','payments','settings','audit'},
 'registrar': set(MODULES)-{'health','conduct','grades','departments','country_profiles'}|{'attendance'},
 'teacher': {'curricula','students','classes','timetable','events','notices','attendance','grades','conduct'},
 'bursar': {'students','classes','invoices','payments'},
 'nurse': {'students','health'},
 'parent': {'students','events','notices','attendance','grades','invoices','payments'},
}

@contextmanager
def connection():
 c = sqlite3.connect(DB, timeout=15)
 c.row_factory = sqlite3.Row
 c.execute('PRAGMA foreign_keys=ON')
 try:
  with c:
   yield c
 finally:
  c.close()

def hash_password(password, salt=None):
 salt = salt or secrets.token_hex(16)
 return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()

def initialize():
 DB.parent.mkdir(parents=True, exist_ok=True)
 with connection() as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, student_id INTEGER);
  CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, module TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES records(id), day TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(student_id,day));
  CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES records(id), term TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), due_date TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id), amount INTEGER NOT NULL CHECK(amount>0), reference TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  ''')
  for key,value in [('school_name','Cedar School'),('term','Term 3 · 2026'),('currency','USD'),('education_system','Custom / international'),('education_levels',json.dumps(DEFAULT_EDUCATION_LEVELS))]:
   c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))
  config_support.migrate(c)
  if c.execute('SELECT count(*) FROM users').fetchone()[0]:
   config_support.seed_profiles(c)
   return
  password = os.environ.get('CEDAR_INITIAL_PASSWORD') or 'cedar-school01'
  for role in ('admin','registrar','teacher','bursar','nurse','parent'):
   username = os.environ.get('CEDAR_INITIAL_USERNAME', 'cedar-school') if role == 'admin' else role
   c.execute('INSERT INTO users(username,password,role,student_id) VALUES(?,?,?,?)',(username,hash_password(password),role,1 if role=='parent' else None))
  print('\nFIRST RUN — admin username: cedar-school; demo account usernames: cedar-school, registrar, teacher, bursar, nurse, parent')
  print('Initial password for these accounts:', password)
  print('Save this password. Each account can change it after sign-in.\n', flush=True)
  def add(module, **data):
   return c.execute('INSERT INTO records(module,data) VALUES(?,?)',(module,json.dumps(data))).lastrowid
  students = [('Amara Reed','Primary','Year 7A','Robin Reed'),('Jonah Vale','Primary','Year 7A','Ellis Vale'),('Maya Brooks','Primary','Year 8A','Avery Brooks'),('Theo Hart','Primary','Year 8A','Morgan Hart'),('Nia Stone','Primary','Year 9A','Casey Stone'),('Leo Finch','Primary','Year 7A','Jamie Finch'),('Isla Rowan','Primary','Year 9A','Taylor Rowan'),('Noah Lake','Primary','Year 8A','Alex Lake')]
  for name,level,cl,guardian in students: add('students',name=name,level=level,class_name=cl,guardian=guardian,phone='Demo contact',status='Active')
  for name,role in [('Avery Cole','Head teacher'),('Jordan Elm','Mathematics'),('Riley Ash','Science'),('Morgan Pine','Registrar')]: add('staff',name=name,role=role,email=name.split()[0].lower()+'@example.invalid',phone='Demo contact',status='Active')
  for name,teacher,room in [('Year 7A','Jordan Elm','A-101'),('Year 8A','Riley Ash','A-102'),('Year 9A','Avery Cole','B-201')]: add('classes',name=name,level='Primary',teacher=teacher,room=room,capacity=30)
  add('timetable',name='Mathematics',class_name='Year 7A',teacher='Jordan Elm',room='A-101',weekday='Monday',start_time='09:00',end_time='09:50')
  add('timetable',name='Science',class_name='Year 8A',teacher='Riley Ash',room='A-102',weekday='Monday',start_time='10:00',end_time='10:50')
  for name,d,cat in [('Term planning','2026-10-06','Academic'),('Science exhibition','2026-10-15','Event'),('Family conference','2026-10-22','Meeting'),('Mid-term break','2026-10-26','Holiday')]: add('events',name=name,event_date=d,category=cat,description='Fictional demonstration event.')
  add('notices',name='Welcome to Cedar School',audience='Everyone',description='This is a demonstration workspace. All names and records are fictional.')
  add('library',name='The Curious Classroom',author='A. Example',borrower='',due_date='',status='Available')
  add('transport',name='North route',driver='Sam Birch',vehicle='DEMO-01',capacity=24)
  add('boarding',name='Oak House',warden='Quinn Grove',capacity=40,occupancy=18)
  c.execute("UPDATE users SET staff_id=(SELECT id FROM records WHERE module='staff' ORDER BY id LIMIT 1) WHERE role='teacher'")
  for sid in range(1,9):
   c.execute('INSERT INTO attendance(student_id,day,status) VALUES(?,?,?)',(sid,date.today().isoformat(),'Absent' if sid==4 else 'Present'))
   inv=c.execute('INSERT INTO invoices(student_id,term,amount,due_date) VALUES(?,?,?,?)',(sid,'Term 3 · 2026',85000,'2026-10-30')).lastrowid
   if sid<6: c.execute('INSERT INTO payments(invoice_id,amount,reference) VALUES(?,?,?)',(inv,85000 if sid<4 else 42500,'DEMO-'+str(sid)))
   add('grades',student_id=sid,subject='Mathematics',term='Term 3 · 2026',score=65+sid*3,maximum=100)
  config_support.seed_profiles(c)

def rows(c, table): return [dict(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY id DESC')]

class Handler(BaseHTTPRequestHandler):
 def log_message(self, *_): pass
 def respond(self, data, status=200, mime='application/json', headers=None):
  raw = (json.dumps(data).encode() if mime=='application/json' else data.encode() if isinstance(data,str) else data)
  self.send_response(status)
  self.send_header('Content-Type',mime+'; charset=utf-8')
  self.send_header('Content-Length',str(len(raw)))
  self.send_header('Cache-Control','no-store')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
  for k,v in (headers or {}).items(): self.send_header(k,v)
  self.end_headers()
  self.wfile.write(raw)
 def user(self):
  cookie=dict(part.strip().split('=',1) for part in self.headers.get('Cookie','').split(';') if '=' in part)
  token=cookie.get('cedar_session','')
  with LOCK: session=SESSIONS.get(token)
  if not session or session['expires']<time.time(): return None,None
  with connection() as c:
   current=c.execute('SELECT id,username,role,student_id,staff_id,department_id,active FROM users WHERE id=?',(session['id'],)).fetchone()
  if not current or not current['active']:return None,None
  session.update(dict(current))
  return session,token
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>100000: raise ValueError('Request is too large.')
  return json.loads(self.rfile.read(n) or '{}')
 def do_GET(self): self.handle_request('GET')
 def do_POST(self): self.handle_request('POST')
 def do_DELETE(self): self.handle_request('DELETE')
 def handle_request(self, method):
  try: self.route(method)
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e: self.respond({'error':str(e)},400)
  except sqlite3.IntegrityError: self.respond({'error':'This change conflicts with an existing or linked record.'},409)
  except Exception:
   self.respond({'error':'The request could not be completed.'},500)
 def route(self, method):
  path=urlparse(self.path).path
  if not path.startswith('/api/'):
   if method!='GET': return self.respond({'error':'Method not allowed'},405)
   files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/extended.js':'extended.js'}
   if path not in files: return self.respond({'error':'Not found'},404)
   mime={'/':'text/html','/app.js':'text/javascript','/style.css':'text/css','/extended.js':'text/javascript'}[path]
   return self.respond((ROOT/'public'/files[path]).read_bytes(),mime=mime)
  if method!='GET':
   origin=self.headers.get('Origin')
   if origin and origin != 'http://'+self.headers.get('Host',''): return self.respond({'error':'Cross-origin request rejected'},403)
  if path=='/api/login' and method=='POST':
   data=self.body()
   time.sleep(.3)
   with connection() as c: row=c.execute('SELECT * FROM users WHERE username=?',(data.get('username'),)).fetchone()
   if not row or not row['active'] or not hmac.compare_digest(hash_password(data.get('password',''),row['password'].split(':')[0]),row['password']): return self.respond({'error':'Incorrect username or password.'},401)
   if data.get('portal') and data['portal']!=row['role']:return self.respond({'error':'This account belongs to a different login workspace.'},403)
   token=secrets.token_urlsafe(32)
   session={k:row[k] for k in ('id','username','role','student_id','staff_id','department_id')}
   session.update(csrf=secrets.token_urlsafe(24),expires=time.time()+28800)
   with LOCK: SESSIONS[token]=session
   return self.respond(session,headers={'Set-Cookie':f'cedar_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
  user,token=self.user()
  if not user: return self.respond({'error':'Please sign in.'},401)
  if method!='GET' and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),user['csrf']): return self.respond({'error':'Invalid session token.'},403)
  if config_support.route(sys.modules[__name__],self,path,method,user):return
  allowed_reads,allowed_writes=config_support.permissions(sys.modules[__name__],user)
  if path=='/api/me': return self.respond(user)
  if path=='/api/logout' and method=='POST':
   with LOCK: SESSIONS.pop(token,None)
   return self.respond({'ok':True},headers={'Set-Cookie':'cedar_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/api/password' and method=='POST':
   data=self.body()
   if len(data.get('password',''))<12: raise ValueError('Use at least 12 characters.')
   with connection() as c:
    row=c.execute('SELECT password FROM users WHERE id=?',(user['id'],)).fetchone()
    if not hmac.compare_digest(hash_password(data.get('current',''),row[0].split(':')[0]),row[0]): raise ValueError('Current password is incorrect.')
    c.execute('UPDATE users SET password=? WHERE id=?',(hash_password(data['password']),user['id']))
   with LOCK:
    for key in list(SESSIONS):
     if SESSIONS[key]['id']==user['id'] and key!=token: SESSIONS.pop(key)
   return self.respond({'ok':True})
  if path=='/api/data' and method=='GET':
   with connection() as c:
    result={m:[] for m in MODULES}
    for row in c.execute('SELECT * FROM records ORDER BY id'):
     m=row['module']
     if m not in allowed_reads: continue
     data=json.loads(row['data']); data['id']=row['id']
     if user['role'] in {'parent','student'} and m not in {'events','notices','classes','timetable','curricula'} and (data.get('student_id',data['id'])!=user['student_id']): continue
     if user['role']=='student' and m in {'classes','timetable'}:
      student=c.execute("SELECT data FROM records WHERE module='students' AND id=?",(user['student_id'],)).fetchone()
      cl=json.loads(student[0]).get('class_name') if student else None
      if (data.get('name') if m=='classes' else data.get('class_name'))!=cl:continue
     if user['role']=='parent' and m=='notices' and data.get('audience') not in {'Everyone','Parents'}: continue
     if user['role']=='student' and m=='notices' and data.get('audience') not in {'Everyone','Students'}:continue
     result[m].append(data)
    for table in ('attendance','invoices','payments','audit'):
     result[table]=rows(c,table) if table in allowed_reads else []
    if user['role'] in {'parent','student'}:
     for table in ('attendance','invoices'): result[table]=[r for r in result[table] if r['student_id']==user['student_id']]
     invoice_ids={r['id'] for r in result['invoices']}
     result['payments']=[r for r in result['payments'] if r['invoice_id'] in invoice_ids]
    result['settings']={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}
    result['permissions']=sorted(allowed_writes);result['readable']=sorted(allowed_reads)
    result['school_day']=config_support.school_day(c)
    result['checkins']=[dict(r) for r in c.execute('SELECT ch.*,u.username,u.role,u.student_id,u.staff_id FROM checkins ch JOIN users u ON u.id=ch.user_id ORDER BY ch.id DESC') if user['role']=='admin' or r['user_id']==user['id']]
    result['account_roles']=list(WRITES) if user['role']=='admin' else []
    result['student_field_schema']=[]
    pid=result['settings'].get('country_profile_id')
    profile=c.execute("SELECT data FROM records WHERE module='country_profiles' AND id=?",(pid,)).fetchone() if pid else None
    if profile and 'students' in allowed_writes:result['student_field_schema']=config_support.fields(json.loads(profile[0])['student_fields'])
    if user['role'] not in {'admin','registrar','student','parent'} and 'students' not in allowed_writes:
     for student in result['students']:student.pop('custom_fields',None)
   return self.respond(result)
  parts=path.split('/'); module=parts[2]
  if module not in allowed_writes: return self.respond({'error':'Your role cannot make this change.'},403)
  with connection() as c:
   c.execute('BEGIN IMMEDIATE')
   if method=='DELETE':
    if module not in MODULES: raise ValueError('Deletion is unavailable for this record type.')
    rid=int(parts[3])
    if module in {'students','staff','departments'} and c.execute('SELECT 1 FROM users WHERE '+{'students':'student_id','staff':'staff_id','departments':'department_id'}[module]+'=?',(rid,)).fetchone():raise ValueError('This record is linked to a login account. Disable the account and retain the record.')
    if module=='country_profiles' and c.execute("SELECT value FROM settings WHERE key='country_profile_id'").fetchone()[0]==str(rid):raise ValueError('Choose another school country profile before deleting this one.')
    if module=='curricula' and any(str(json.loads(r[0]).get('curriculum_id'))==str(rid) for r in c.execute("SELECT data FROM records WHERE module IN ('students','classes')")):raise ValueError('This curriculum is in use.')
    if module=='students':
     linked=c.execute('SELECT 1 FROM attendance WHERE student_id=? UNION SELECT 1 FROM invoices WHERE student_id=?',(rid,rid)).fetchone()
     if linked or any(json.loads(r[0]).get('student_id')==rid for r in c.execute("SELECT data FROM records WHERE module IN ('grades','health','conduct')")): raise ValueError('This student has linked records. Change their status to Withdrawn instead.')
    if not c.execute('DELETE FROM records WHERE id=? AND module=?',(rid,module)).rowcount: raise ValueError('Record not found.')
   elif method=='POST':
    data=self.body()
    if module in MODULES:
     clean={k:data.get(k,'') for k in MODULES[module]}
     for k,v in clean.items():
      if not isinstance(v,(str,int,float)) or len(str(v))>2000: raise ValueError('Invalid field: '+k)
     required=MODULES[module][0]
     if not str(clean[required]).strip(): raise ValueError('A '+required.replace('_',' ')+' is required.')
     if module=='students' and clean['status'] not in {'Applicant','Active','Withdrawn','Graduated'}: raise ValueError('Choose a valid student status.')
     levels=json.loads(c.execute("SELECT value FROM settings WHERE key='education_levels'").fetchone()[0])
     if clean.get('level') and not clean.get('curriculum_id') and clean['level'] not in levels: raise ValueError('Choose a configured education level.')
     if module=='students' and clean['class_name'] and clean['status']=='Active':
      classes=[json.loads(r[0]) for r in c.execute("SELECT data FROM records WHERE module='classes'")]
      selected=next((r for r in classes if r['name']==clean['class_name']),None)
      if selected:
       occupied=sum(1 for r in c.execute("SELECT id,data FROM records WHERE module='students'") if r['id']!=int(data.get('id') or 0) and json.loads(r['data']).get('class_name')==clean['class_name'] and json.loads(r['data']).get('status')=='Active')
       if occupied>=int(selected['capacity']): raise ValueError('This class is at capacity.')
     if module=='timetable':
      classes=[json.loads(r[0]) for r in c.execute("SELECT data FROM records WHERE module='classes'")]
      selected=next((r for r in classes if r['name']==clean['class_name']),None)
      if not selected: raise ValueError('Choose an existing class.')
      from datetime import time as clock_time
      clock_time.fromisoformat(clean['start_time']);clock_time.fromisoformat(clean['end_time'])
      if clean['weekday'] not in {'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'} or clean['start_time']>=clean['end_time']: raise ValueError('Choose a valid day and an end time after the start.')
      for r in c.execute("SELECT id,data FROM records WHERE module='timetable'"):
       item=json.loads(r['data'])
       if r['id']!=int(data.get('id') or 0) and item['weekday']==clean['weekday'] and item['start_time']<clean['end_time'] and item['end_time']>clean['start_time'] and any(item[k]==clean[k] for k in ('class_name','teacher','room')): raise ValueError('Schedule conflict: class, teacher, or room is already booked.')
     if module in {'grades','health','conduct'}:
      clean['student_id']=int(clean['student_id'])
      if not c.execute("SELECT 1 FROM records WHERE id=? AND module='students'",(clean['student_id'],)).fetchone(): raise ValueError('Student not found.')
     for k in ('capacity','occupancy'):
      if k in clean:
       clean[k]=int(clean[k])
       if clean[k]<0: raise ValueError(k+' must be nonnegative.')
     if module=='boarding' and clean['occupancy']>clean['capacity']: raise ValueError('Occupancy exceeds capacity.')
     if module=='grades':
      clean['score']=float(clean['score']);clean['maximum']=float(clean['maximum'])
      if clean['maximum']<=0 or not 0<=clean['score']<=clean['maximum']: raise ValueError('Score must be between zero and the maximum.')
     for k in ('event_date','record_date','due_date'):
      if clean.get(k): date.fromisoformat(clean[k])
     config_support.validate(sys.modules[__name__],c,module,clean,data)
     if data.get('id'):
      if not c.execute('UPDATE records SET data=? WHERE id=? AND module=?',(json.dumps(clean),int(data['id']),module)).rowcount: raise ValueError('Record not found.')
     else: c.execute('INSERT INTO records(module,data) VALUES(?,?)',(module,json.dumps(clean)))
    elif module=='attendance':
     day=data['day'];date.fromisoformat(day)
     for item in data['entries']:
      if item['status'] not in {'Present','Absent','Late','Excused'}: raise ValueError('Invalid attendance status.')
      if not c.execute("SELECT 1 FROM records WHERE id=? AND module='students'",(int(item['student_id']),)).fetchone(): raise ValueError('Student not found.')
      c.execute('INSERT INTO attendance(student_id,day,status) VALUES(?,?,?) ON CONFLICT(student_id,day) DO UPDATE SET status=excluded.status',(int(item['student_id']),day,item['status']))
    elif module=='invoices':
     amount=int(data['amount']);date.fromisoformat(data['due_date'])
     if amount<=0 or not str(data['term']).strip(): raise ValueError('A positive amount and term are required.')
     if not c.execute("SELECT 1 FROM records WHERE id=? AND module='students'",(int(data['student_id']),)).fetchone(): raise ValueError('Student not found.')
     c.execute('INSERT INTO invoices(student_id,term,amount,due_date) VALUES(?,?,?,?)',(int(data['student_id']),data['term'],amount,data['due_date']))
    elif module=='payments':
     inv=int(data['invoice_id']);amount=int(data['amount'])
     row=c.execute('SELECT amount-(SELECT coalesce(sum(amount),0) FROM payments WHERE invoice_id=invoices.id) AS balance FROM invoices WHERE id=?',(inv,)).fetchone()
     if not row or not 0<amount<=row['balance'] or not str(data['reference']).strip(): raise ValueError('Enter a reference and an amount within the remaining balance.')
     c.execute('INSERT INTO payments(invoice_id,amount,reference) VALUES(?,?,?)',(inv,amount,data['reference']))
    elif module=='settings':
     for k in ('school_name','term','currency','education_system'):
      value=str(data[k]).strip()
      if not value or len(value)>120: raise ValueError('Invalid '+k)
      if k=='currency' and (len(value)!=3 or not value.isalpha()): raise ValueError('Use a three-letter currency code.')
      c.execute('UPDATE settings SET value=? WHERE key=?',(value,k))
     for k in ('country','country_code','country_profile_id','utc_offset_minutes'):
      if k in data:
       value=str(data[k]).strip()
       if len(value)>120:raise ValueError('Invalid '+k)
       if k=='country_code' and (len(value)!=2 or not value.isalpha() or value!=value.upper()):raise ValueError('Use an uppercase two-letter country code.')
       if k=='utc_offset_minutes' and not -720<=int(value)<=840:raise ValueError('UTC offset must be between -720 and 840 minutes.')
       if k=='country_profile_id' and value and not c.execute("SELECT 1 FROM records WHERE module='country_profiles' AND id=?",(int(value),)).fetchone():raise ValueError('Country profile not found.')
       c.execute('UPDATE settings SET value=? WHERE key=?',(value,k))
     pid=c.execute("SELECT value FROM settings WHERE key='country_profile_id'").fetchone()[0]
     profile=c.execute("SELECT data FROM records WHERE module='country_profiles' AND id=?",(pid,)).fetchone() if pid else None
     code=c.execute("SELECT value FROM settings WHERE key='country_code'").fetchone()[0]
     if profile and json.loads(profile[0])['country_code']!=code:raise ValueError('The selected profile must match the school country code.')
     levels=[line.strip() for line in str(data['education_levels']).splitlines() if line.strip()]
     if not 1<=len(levels)<=30 or any(len(level)>120 for level in levels) or len(set(levels))!=len(levels): raise ValueError('Enter one unique education level per line.')
     c.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(levels),'education_levels'))
   else: return self.respond({'error':'Method not allowed'},405)
   c.execute('INSERT INTO audit(username,action,target) VALUES(?,?,?)',(user['username'],method,module))
  self.respond({'ok':True})

if __name__=='__main__':
 initialize()
 port=int(os.environ.get('CEDAR_PORT','8765'))
 print(f'Cedar School is running at http://127.0.0.1:{port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
