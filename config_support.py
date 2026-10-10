"""Configurable education profiles, account provisioning and shared check-in."""
from datetime import datetime, timedelta, timezone
import json
import re

def school_day(c):
 offset=int(c.execute("SELECT value FROM settings WHERE key='utc_offset_minutes'").fetchone()[0])
 return datetime.now(timezone(timedelta(minutes=offset))).date().isoformat()

def fields(spec):
 result=[]
 for line in spec.splitlines():
  if not line.strip(): continue
  parts=line.strip().split('|')
  if len(parts)<2: raise ValueError('Student fields use key|Label|type|required|choices.')
  key,label=parts[:2];kind=parts[2] if len(parts)>2 and parts[2] else 'text'
  required=len(parts)>3 and parts[3].lower() in {'yes','true','required'}
  choices=parts[4].split(',') if len(parts)>4 and parts[4] else []
  if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',key) or not label or len(label)>100 or kind not in {'text','date','number','select'}: raise ValueError('Invalid student field definition.')
  if key in {r['key'] for r in result} or (kind=='select' and not choices): raise ValueError('Field keys must be unique; selects require choices.')
  result.append({'key':key,'label':label,'type':kind,'required':required,'options':choices})
 if len(result)>40: raise ValueError('Use at most 40 country-specific fields.')
 return result

def migrate(c):
 columns={r['name'] for r in c.execute('PRAGMA table_info(users)')}
 for name,definition in [('staff_id','INTEGER'),('department_id','INTEGER'),('active','INTEGER NOT NULL DEFAULT 1')]:
  if name not in columns:c.execute('ALTER TABLE users ADD COLUMN '+name+' '+definition)
 c.execute('CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),day TEXT NOT NULL,checked_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,day))')
 defaults={'country':'Custom / international','country_code':'XX','country_profile_id':'','utc_offset_minutes':'0'}
 for key,value in defaults.items():c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(key,value))

def seed_profiles(c):
 if not c.execute("SELECT 1 FROM records WHERE module='departments'").fetchone():
  for name,reads,writes in [('Admissions','students,classes,curricula','students'),('Finance','students,classes,invoices,payments','invoices,payments'),('Academics','students,classes,curricula,timetable,grades,attendance','grades,attendance'),('Library','library','library'),('Transport','transport','transport'),('Boarding','boarding','boarding'),('Health','students,health','health')]:
   c.execute('INSERT INTO records(module,data) VALUES(?,?)',('departments',json.dumps({'name':name,'read_modules':reads,'write_modules':writes})))
 if not c.execute("SELECT 1 FROM records WHERE module='curricula'").fetchone():
  for name,levels,subjects in [('Year-based starter','Early years\nPrimary\nSecondary\nSixth form','Language\nMathematics\nScience'),('Grade-based starter','Kindergarten\nElementary\nMiddle school\nHigh school','Language\nMathematics\nScience'),('Stage-based starter','Nursery\nPrimary\nLower secondary / O-Level\nUpper secondary / A-Level','Language\nMathematics\nScience'),('Tertiary / vocational starter','Certificate\nDiploma\nUndergraduate\nPostgraduate\nAdult learning','Configure institution-specific subjects')]:
   c.execute('INSERT INTO records(module,data) VALUES(?,?)',('curricula',json.dumps({'name':name,'country':'Adaptable starter','levels':levels,'subjects':subjects,'grading':'Set local assessment rules','description':'Illustrative structure; edit to match the approved local curriculum.'})))
 if not c.execute("SELECT 1 FROM records WHERE module='country_profiles'").fetchone():
  c.execute('INSERT INTO records(module,data) VALUES(?,?)',('country_profiles',json.dumps({'name':'Custom country student profile','country_code':'XX','student_fields':'learner_number|Local learner number|text|no\ndistrict|District / region|text|no\nhome_language|Home language|text|no'})))
  pid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  c.execute("UPDATE settings SET value=? WHERE key='country_profile_id'",(str(pid),))

def permissions(core,user):
 reads=set(core.READS[user['role']]);writes=set(core.WRITES[user['role']])
 if user['role']=='department':
  with core.connection() as c:
   row=c.execute("SELECT data FROM records WHERE module='departments' AND id=?",(user['department_id'],)).fetchone()
  if row:
   record=json.loads(row[0]);writes=set(x.strip() for x in record['write_modules'].split(',') if x.strip());reads=set(x.strip() for x in record['read_modules'].split(',') if x.strip())|writes
 if writes & {'students','classes'}:reads|={'curricula','classes'}
 return reads,writes

def validate(core,c,module,clean,payload):
 if module in {'curricula','departments','country_profiles'}:
  if module=='curricula' and not clean['levels'].strip():raise ValueError('Configure at least one curriculum level.')
  if module=='country_profiles':
   if not re.fullmatch('[A-Z]{2}',clean['country_code']):raise ValueError('Use a two-letter uppercase country code (XX for custom).')
   fields(clean['student_fields'])
  if module=='departments':
   allowed=(set(core.MODULES)|{'attendance','invoices','payments'})-{'departments','country_profiles'}
   for key in ('read_modules','write_modules'):
    chosen={s.strip() for s in clean[key].split(',') if s.strip()}
    if not chosen<=allowed:raise ValueError('Unknown or restricted department modules: '+', '.join(sorted(chosen-allowed)))
 if module in {'students','classes'}:
  curriculum_id=clean.get('curriculum_id')
  if curriculum_id:
   row=c.execute("SELECT data FROM records WHERE module='curricula' AND id=?",(int(curriculum_id),)).fetchone()
   if not row:raise ValueError('Curriculum not found.')
   clean['curriculum_id']=int(curriculum_id)
   levels=json.loads(row[0])['levels'].splitlines()
   if clean['level'] and clean['level'] not in levels:raise ValueError('Level must belong to the selected curriculum.')
 if module=='students':
  existing={}
  if payload.get('id'):
   row=c.execute("SELECT data FROM records WHERE module='students' AND id=?",(int(payload['id']),)).fetchone()
   if row:existing=json.loads(row[0]).get('custom_fields',{})
  values=payload.get('custom_fields',existing)
  if not isinstance(values,dict) or len(values)>100:raise ValueError('Invalid country-specific student details.')
  for key,value in values.items():
   if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',key) or not isinstance(value,str) or len(value)>2000:raise ValueError('Invalid student custom field.')
  pid=c.execute("SELECT value FROM settings WHERE key='country_profile_id'").fetchone()[0]
  row=c.execute("SELECT data FROM records WHERE module='country_profiles' AND id=?",(pid,)).fetchone() if pid else None
  for field in fields(json.loads(row[0])['student_fields']) if row else []:
   value=values.get(field['key'],'')
   if field['required'] and not value.strip():raise ValueError(field['label']+' is required.')
   if value:
    if field['type']=='date':datetime.strptime(value,'%Y-%m-%d')
    if field['type']=='number':
     import math
     if not math.isfinite(float(value)):raise ValueError('Invalid number.')
    if field['type']=='select' and value not in field['options']:raise ValueError('Invalid '+field['label'])
  clean['custom_fields']={**existing,**values}

def route(core,handler,path,method,user):
 if path not in {'/api/accounts','/api/checkin'}:return False
 with core.connection() as c:
  if path=='/api/accounts':
   if user['role']!='admin':handler.respond({'error':'Administrator access required.'},403);return True
   if method=='GET':
    handler.respond([dict(r) for r in c.execute('SELECT id,username,role,student_id,staff_id,department_id,active FROM users ORDER BY username')]);return True
   if method!='POST':handler.respond({'error':'Method not allowed.'},405);return True
   c.execute('BEGIN IMMEDIATE');body=handler.body();rid=int(body.get('id') or 0)
   username=str(body['username']).strip();role=body['role'];password=body.get('password','')
   if not re.fullmatch(r'[A-Za-z0-9_.-]{3,80}',username) or role not in core.WRITES:raise ValueError('Choose a valid username and role.')
   old=c.execute('SELECT * FROM users WHERE id=?',(rid,)).fetchone() if rid else None
   if rid and not old:raise ValueError('Account not found.')
   if (not old or password) and len(password)<12:raise ValueError('New accounts and password resets need at least 12 characters.')
   links={k:int(body[k]) if body.get(k) else None for k in ('student_id','staff_id','department_id')}
   for role_set,key,module in [({'student','parent'},'student_id','students'),({'teacher'},'staff_id','staff'),({'department'},'department_id','departments')]:
    if role in role_set:
     if not links[key] or not c.execute('SELECT 1 FROM records WHERE module=? AND id=?',(module,links[key])).fetchone():raise ValueError('Link this account to an existing '+module+' record.')
    else:links[key]=None
   active=0 if str(body.get('active',1))=='0' else 1
   if old and old['role']=='admin' and (role!='admin' or not active) and c.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:raise ValueError('Keep at least one active administrator.')
   if rid==user['id'] and (role!='admin' or not active):raise ValueError('You cannot disable or demote your own administrator account.')
   encoded=core.hash_password(password) if password else old['password']
   if old:
    c.execute('UPDATE users SET username=?,password=?,role=?,student_id=?,staff_id=?,department_id=?,active=? WHERE id=?',(username,encoded,role,links['student_id'],links['staff_id'],links['department_id'],active,rid))
   else:rid=c.execute('INSERT INTO users(username,password,role,student_id,staff_id,department_id,active) VALUES(?,?,?,?,?,?,?)',(username,encoded,role,links['student_id'],links['staff_id'],links['department_id'],active)).lastrowid
   c.execute('INSERT INTO audit(username,action,target) VALUES(?,?,?)',(user['username'],'ACCOUNT_UPDATE',username))
   c.commit()
   with core.LOCK:
    for token in list(core.SESSIONS):
     if core.SESSIONS[token]['id']==rid:core.SESSIONS.pop(token)
   handler.respond({'ok':True,'id':rid});return True
  if method!='POST':handler.respond({'error':'Method not allowed.'},405);return True
  if user['role'] not in {'teacher','student'}:handler.respond({'error':'Student or teacher login required.'},403);return True
  body=handler.body()
  if any(key in body for key in ('student_id','staff_id','user_id','day')):raise ValueError('Self check-in uses your own account and today only.')
  link='student_id' if user['role']=='student' else 'staff_id';module='students' if user['role']=='student' else 'staff'
  row=c.execute('SELECT data FROM records WHERE id=? AND module=?',(user.get(link),module)).fetchone()
  if not row or json.loads(row[0]).get('status')!='Active':raise ValueError('An active linked '+module+' record is required.')
  c.execute('BEGIN IMMEDIATE');day=school_day(c)
  inserted=c.execute('INSERT OR IGNORE INTO checkins(user_id,day) VALUES(?,?)',(user['id'],day)).rowcount
  if user['role']=='student':c.execute('INSERT OR IGNORE INTO attendance(student_id,day,status) VALUES(?,?,?)',(user['student_id'],day,'Present'))
  if inserted:c.execute('INSERT INTO audit(username,action,target) VALUES(?,?,?)',(user['username'],'SELF_CHECKIN',day))
  c.commit()
  handler.respond({'ok':True,'day':day,'already_checked_in':not bool(inserted),'message':'Check-in recorded. Existing teacher-marked attendance is retained.'})
 return True
