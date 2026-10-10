"""End-to-end HTTP checks against a temporary database; never touches user data."""
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import threading
import unittest
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server
PASSWORD='Testing-only-password-2026'
USERNAME='admin'

class SystemTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(dir=ROOT,prefix='.test-')
  with socket.socket() as s:
   s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  cls.url=f'http://127.0.0.1:{port}'
  server.DB=Path(cls.temp.name)/'test.db'
  os.environ['CEDAR_INITIAL_PASSWORD']=PASSWORD
  os.environ['CEDAR_INITIAL_USERNAME']=USERNAME
  server.initialize()
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',port),server.Handler)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
  cls.thread.start()
 @classmethod
 def tearDownClass(cls):
  cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=5);cls.temp.cleanup()
 def client(self,role='admin'):
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  status,result=self.request(opener,'login',{'username':role,'password':PASSWORD})
  self.assertEqual(status,200)
  opener.csrf=result['csrf'];return opener
 def request(self,client,path,body=None,method=None,csrf=True):
  headers={'Content-Type':'application/json'}
  if csrf: headers['X-CSRF-Token']=getattr(client,'csrf','')
  req=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method or ('POST' if body is not None else 'GET'))
  try:
   with client.open(req,timeout=10) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   with e:return e.code,json.load(e)
 def test_authentication_and_csrf(self):
  anonymous=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  self.assertEqual(self.request(anonymous,'data')[0],401)
  admin=self.client()
  self.assertEqual(self.request(admin,'notices',{'name':'Blocked','audience':'Everyone'},csrf=False)[0],403)
  self.assertEqual(self.request(admin,'logout',{})[0],200)
  self.assertEqual(self.request(admin,'data')[0],401)
 def test_education_settings(self):
  admin=self.client()
  current=self.request(admin,'data')[1]['settings']
  body={'school_name':current['school_name'],'education_system':'Local national system','term':current['term'],'currency':current['currency'],'education_levels':'Early years\nPrimary\nCollege / vocational\nUniversity'}
  self.assertEqual(self.request(admin,'settings',body)[0],200)
  settings=self.request(admin,'data')[1]['settings']
  self.assertEqual(settings['education_system'],'Local national system')
  self.assertEqual(json.loads(settings['education_levels']),['Early years','Primary','College / vocational','University'])
  body['education_levels']='Primary\nPrimary'
  self.assertEqual(self.request(admin,'settings',body)[0],400)
 def test_parent_scope_and_role_enforcement(self):
  parent=self.client('parent');status,data=self.request(parent,'data')
  self.assertEqual(status,200);self.assertEqual([r['id'] for r in data['students']],[1])
  self.assertTrue(all(r['student_id']==1 for r in data['invoices']))
  self.assertEqual(data['health'],[])
  self.assertEqual(self.request(parent,'students',{'name':'Unauthorized'})[0],403)
  teacher=self.client('teacher')
  self.assertEqual(self.request(teacher,'payments',{'invoice_id':8,'amount':100,'reference':'bad'})[0],403)
 def test_attendance_upsert(self):
  teacher=self.client('teacher')
  payload={'day':'2026-11-01','entries':[{'student_id':1,'status':'Absent'}]}
  self.assertEqual(self.request(teacher,'attendance',payload)[0],200)
  payload['entries'][0]['status']='Late'
  self.assertEqual(self.request(teacher,'attendance',payload)[0],200)
  records=self.request(teacher,'data')[1]['attendance']
  matches=[r for r in records if r['student_id']==1 and r['day']=='2026-11-01']
  self.assertEqual(len(matches),1);self.assertEqual(matches[0]['status'],'Late')
 def test_payment_balance_and_overpayment(self):
  bursar=self.client('bursar');data=self.request(bursar,'data')[1]
  invoice=next(i for i in data['invoices'] if i['student_id']==8)
  body={'invoice_id':invoice['id'],'amount':10000,'reference':'TEST-PAYMENT'}
  self.assertEqual(self.request(bursar,'payments',body)[0],200)
  data=self.request(bursar,'data')[1]
  paid=sum(p['amount'] for p in data['payments'] if p['invoice_id']==invoice['id'])
  self.assertEqual(invoice['amount']-paid,75000)
  body['amount']=75001
  self.assertEqual(self.request(bursar,'payments',body)[0],400)
  body['amount']=-1
  self.assertEqual(self.request(bursar,'payments',body)[0],400)
 def test_student_lifecycle_and_linked_deletion(self):
  admin=self.client()
  body={'name':'Test Student','class_name':'User-created class','guardian':'Test Guardian','phone':'','status':'Applicant'}
  self.assertEqual(self.request(admin,'students',body)[0],200)
  record=next(r for r in self.request(admin,'data')[1]['students'] if r['name']=='Test Student')
  body.update(id=record['id'],status='Active')
  self.assertEqual(self.request(admin,'students',body)[0],200)
  self.assertEqual(self.request(admin,'students/'+str(record['id']),method='DELETE')[0],200)
  self.assertEqual(self.request(admin,'students/1',method='DELETE')[0],400)
 def test_timetable_conflicts_and_grade_validation(self):
  admin=self.client()
  body={'name':'Conflicting lesson','class_name':'Year 7A','teacher':'Other teacher','room':'Other room','weekday':'Monday','start_time':'09:20','end_time':'10:20'}
  self.assertEqual(self.request(admin,'timetable',body)[0],400)
  teacher=self.client('teacher')
  self.assertEqual(self.request(teacher,'grades',{'student_id':1,'subject':'Math','term':'Term 3','score':120,'maximum':100})[0],400)
 def test_health_restriction_and_audit(self):
  nurse=self.client('nurse')
  self.assertEqual(self.request(nurse,'health',{'student_id':1,'category':'Care visit','description':'Fictional test note','record_date':'2026-10-06'})[0],200)
  self.assertEqual(self.request(self.client('teacher'),'data')[1]['health'],[])
  data=self.request(self.client(),'data')[1]
  self.assertTrue(any(r['target']=='health' for r in data['audit']))
 def test_static_assets(self):
  client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  for path in ('/','/app.js','/style.css','/extended.js'):
   with client.open(self.url+path) as response:
    self.assertEqual(response.status,200)
    self.assertGreater(len(response.read()),100)
    self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
 def test_password_change(self):
  client=self.client('registrar')
  self.assertEqual(self.request(client,'password',{'current':PASSWORD,'password':'tiny'})[0],400)
  self.assertEqual(self.request(client,'password',{'current':PASSWORD,'password':'New-testing-password-2026'})[0],200)
  anonymous=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  self.assertEqual(self.request(anonymous,'login',{'username':'registrar','password':PASSWORD})[0],401)
  self.assertEqual(self.request(anonymous,'login',{'username':'registrar','password':'New-testing-password-2026'})[0],200)
 def test_class_capacity(self):
  admin=self.client()
  body={'name':'Capacity Test','teacher':'Test','room':'Test','capacity':0}
  self.assertEqual(self.request(admin,'classes',body)[0],200)
  self.assertEqual(self.request(admin,'students',{'name':'No space','class_name':'Capacity Test','status':'Active'})[0],400)
 def test_concurrent_payment_limit(self):
  bursar=self.client('bursar');results=[]
  invoice=next(i for i in self.request(bursar,'data')[1]['invoices'] if i['student_id']==7)
  def pay():
   client=self.client('bursar')
   results.append(self.request(client,'payments',{'invoice_id':invoice['id'],'amount':60000,'reference':'CONCURRENT-TEST'})[0])
  threads=[threading.Thread(target=pay) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(sorted(results),[200,400])

if __name__=='__main__':unittest.main(verbosity=2)
