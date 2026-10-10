"""Country/curriculum configuration and connected account integration checks."""
import json
import sqlite3
from pathlib import Path
from contextlib import closing
import unittest
import test_system as base

class ConnectedTests(unittest.TestCase):
 setUpClass=classmethod(base.SystemTests.setUpClass.__func__)
 tearDownClass=classmethod(base.SystemTests.tearDownClass.__func__)
 client=base.SystemTests.client
 request=base.SystemTests.request
 def account(self,admin,username,role,**links):
  result=self.request(admin,'accounts',{'username':username,'role':role,'password':base.PASSWORD,**links})
  self.assertEqual(result[0],200,result[1]);return result[1]['id']
 def test_student_login_scope_checkin_and_no_impersonation(self):
  admin=self.client();self.account(admin,'student.one','student',student_id=1)
  student=self.client('student.one');status,data=self.request(student,'data')
  self.assertEqual([s['id'] for s in data['students']],[1])
  self.assertEqual(data['staff'],[]);self.assertEqual(data['health'],[])
  self.assertEqual(self.request(student,'accounts')[0],403)
  self.assertEqual(self.request(student,'checkin',{'student_id':2})[0],400)
  self.assertEqual(self.request(student,'checkin',{'day':'2020-01-01'})[0],400)
  result=self.request(student,'checkin',{})
  self.assertEqual(result[0],200,result[1])
  self.assertFalse(result[1]['already_checked_in'])
  self.assertTrue(self.request(student,'checkin',{})[1]['already_checked_in'])
  self.assertEqual(len(self.request(student,'data')[1]['checkins']),1)
  shared=self.request(admin,'data')[1]
  self.assertTrue(any(c['username']=='student.one' for c in shared['checkins']))
  self.assertTrue(any(a['student_id']==1 and a['day']==shared['school_day'] for a in shared['attendance']))
 def test_teacher_checkin_and_protected_existing_student_status(self):
  teacher=self.client('teacher');self.assertEqual(self.request(teacher,'checkin',{})[0],200)
  admin=self.client();self.account(admin,'student.two','student',student_id=2)
  day=self.request(admin,'data')[1]['school_day']
  self.request(teacher,'attendance',{'day':day,'entries':[{'student_id':2,'status':'Absent'}]})
  student=self.client('student.two');self.assertEqual(self.request(student,'checkin',{})[0],200)
  record=next(a for a in self.request(admin,'data')[1]['attendance'] if a['day']==day and a['student_id']==2)
  self.assertEqual(record['status'],'Absent')
 def test_department_permissions_accounts_and_disable(self):
  admin=self.client()
  self.assertEqual(self.request(admin,'departments',{'name':'Library department','read_modules':'library','write_modules':'library'})[0],200)
  dep=next(d for d in self.request(admin,'data')[1]['departments'] if d['name']=='Library department')
  uid=self.account(admin,'library.team','department',department_id=dep['id'])
  department=self.client('library.team');data=self.request(department,'data')[1]
  self.assertEqual(data['permissions'],['library']);self.assertEqual(data['students'],[])
  self.assertEqual(self.request(department,'library',{'name':'New book','author':'Demo','status':'Available'})[0],200)
  self.assertEqual(self.request(department,'students',{'name':'Blocked'})[0],403)
  self.assertEqual(self.request(admin,'accounts',{'id':uid,'username':'library.team','role':'department','department_id':dep['id'],'active':0})[0],200)
  self.assertEqual(self.request(department,'data')[0],401)
  self.assertEqual(self.request(admin,'departments',{'name':'Bad department','read_modules':'accounts','write_modules':'settings'})[0],400)
 def test_country_fields_validation_and_preservation(self):
  admin=self.client()
  settings=self.request(admin,'data')[1]['settings']
  body={'name':'Local test profile','country_code':'XX','student_fields':'region|Region|text|yes\ntrack|Learning track|select|no|General,Vocational'}
  self.assertEqual(self.request(admin,'country_profiles',body)[0],200)
  profile=next(p for p in self.request(admin,'data')[1]['country_profiles'] if p['name']==body['name'])
  updated={**settings,'education_levels':'\n'.join(json.loads(settings['education_levels'])),'country_profile_id':profile['id']}
  self.assertEqual(self.request(admin,'settings',updated)[0],200)
  student=next(s for s in self.request(admin,'data')[1]['students'] if s['id']==3)
  self.assertEqual(self.request(admin,'students',student)[0],400)
  student['custom_fields']={'region':'Example region','track':'General'}
  self.assertEqual(self.request(admin,'students',student)[0],200)
  student['custom_fields']['track']='Unknown'
  self.assertEqual(self.request(admin,'students',student)[0],400)
  saved=next(s for s in self.request(admin,'data')[1]['students'] if s['id']==3)
  self.assertEqual(saved['custom_fields']['region'],'Example region')
  restore={**settings,'education_levels':'\n'.join(json.loads(settings['education_levels']))}
  self.assertEqual(self.request(admin,'settings',restore)[0],200)
 def test_curriculum_levels_and_account_link_validation(self):
  admin=self.client()
  self.assertEqual(self.request(admin,'curricula',{'name':'Flexible programme','country':'Custom','levels':'Foundation\nDiploma','subjects':'Workshop\nApplied study','grading':'Competency and percentage','description':''})[0],200)
  curriculum=next(r for r in self.request(admin,'data')[1]['curricula'] if r['name']=='Flexible programme')
  cl={'name':'Diploma A','level':'Diploma','curriculum_id':curriculum['id'],'teacher':'Demo','room':'D-1','capacity':20}
  self.assertEqual(self.request(admin,'classes',cl)[0],200)
  cl['name']='Bad level';cl['level']='Unknown'
  self.assertEqual(self.request(admin,'classes',cl)[0],400)
  self.assertEqual(self.request(admin,'accounts',{'username':'student.bad','role':'student','student_id':99999,'password':base.PASSWORD})[0],400)
  records=self.request(admin,'accounts')[1]
  self.assertTrue(all('password' not in a for a in records))
  self.assertEqual(self.request(admin,'accounts',{'id':1,'username':'admin','role':'admin','active':0})[0],400)
 def test_legacy_migration_preserves_accounts_and_records(self):
  import server
  with closing(sqlite3.connect(Path(self.temp.name)/'legacy.db')) as c:
   c.row_factory=sqlite3.Row
   c.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT,role TEXT,student_id INTEGER); CREATE TABLE records(id INTEGER PRIMARY KEY,module TEXT,data TEXT); CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT); INSERT INTO users VALUES(1,'existing','preserved-hash','admin',NULL); INSERT INTO records VALUES(1,'students','{\"name\":\"Existing learner\"}');")
   server.config_support.migrate(c);server.config_support.seed_profiles(c)
   server.config_support.migrate(c);server.config_support.seed_profiles(c)
   row=c.execute('SELECT * FROM users WHERE id=1').fetchone()
   self.assertEqual(row['password'],'preserved-hash');self.assertEqual(row['active'],1)
   self.assertEqual(json.loads(c.execute('SELECT data FROM records WHERE id=1').fetchone()[0])['name'],'Existing learner')
   self.assertEqual(c.execute("SELECT count(*) FROM records WHERE module='curricula'").fetchone()[0],4)
 def test_login_workspace_cannot_grant_a_role(self):
  import urllib.request
  client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  self.assertEqual(self.request(client,'login',{'username':'teacher','password':base.PASSWORD,'portal':'admin'})[0],403)
  self.assertEqual(self.request(client,'login',{'username':'teacher','password':base.PASSWORD,'portal':'teacher'})[0],200)

if __name__=='__main__':unittest.main(verbosity=2)
