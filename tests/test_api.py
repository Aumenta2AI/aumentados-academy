"""Integration tests against a real HTTP server and an isolated SQLite database."""
import http.cookiejar, http.client, json, pathlib, tempfile, threading, time, unittest, urllib.error, urllib.request, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import server

class Client:
    def __init__(self,origin):
        self.origin=origin; self.csrf=''
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,path,method='GET',data=None,raw=None,headers=None):
        h={'Origin':self.origin,**(headers or {})}
        if self.csrf: h['X-CSRF-Token']=self.csrf
        if data is not None: raw=json.dumps(data).encode(); h['Content-Type']='application/json'
        try:
            r=self.opener.open(urllib.request.Request(self.origin+path,raw,h,method=method))
            body=r.read(); content=r.headers.get('Content-Type','')
            result=json.loads(body) if 'application/json' in content else body
            if isinstance(result,dict) and result.get('csrf'): self.csrf=result['csrf']
            return r.status,result,r.headers
        except urllib.error.HTTPError as e:
            return e.code,json.loads(e.read()),e.headers

class AcademyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); server.DATA=pathlib.Path(cls.tmp.name); server.initialize()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.origin='http://127.0.0.1:'+str(cls.http.server_port)
        cls.admin=Client(cls.origin); cls.student=Client(cls.origin); cls.guest=Client(cls.origin)
        code=(server.DATA/'setup-code.txt').read_text()
        status,cls.owner,_=cls.admin.request('/api/setup','POST',{'email':'owner@example.test','password':'a-test-password-123','name':'Academy Owner','setupCode':code})
        assert status==200,(status,cls.owner)
        status,cls.learner,_=cls.student.request('/api/register','POST',{'email':'student@example.test','password':'a-test-password-456','name':'Test Student','role':'admin'})
        assert status==200,(status,cls.learner)
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
    def module(self):
        status,d,_=self.admin.request('/api/modules','POST',{'title':'Módulo de prueba','description':'Contenido de prueba'})
        self.assertEqual(status,201);return d['id']
    def media(self):
        data=b'\x1aE\xdf\xa3'+b'\0'*100
        status,m,_=self.admin.request('/api/uploads','POST',{'size':len(data),'mime':'video/webm'})
        self.assertEqual(status,201)
        self.assertEqual(self.admin.request('/api/uploads/'+m['id']+'?offset=0','PUT',raw=data)[0],200)
        self.assertEqual(self.admin.request('/api/uploads/'+m['id']+'/finish','POST',{})[0],200)
        return m['id'],data
    def lesson(self,published=False):
        mid=self.module();media,data=self.media()
        body={'module_id':mid,'title':'Una lección','media_id':media,'duration':10,'published':published}
        status,l,_=self.admin.request('/api/lessons','POST',body)
        self.assertEqual(status,201,l);return l['id'],body,data
    def test_01_register_is_always_student(self):
        self.assertEqual(self.learner['user']['role'],'student')
        self.assertEqual(self.student.request('/api/modules','POST',{'title':'Forbidden'})[0],403)
        self.assertEqual(self.guest.request('/api/modules','POST',{'title':'Forbidden'})[0],401)
        self.assertEqual(self.student.request('/api/students')[0],403)
    def test_02_admin_setup_is_one_time(self):
        self.assertFalse((server.DATA/'setup-code.txt').exists())
        self.assertEqual(self.guest.request('/api/setup','POST',{'email':'bad@example.test','password':'a-test-password-789','name':'Bad','setupCode':'anything'})[0],409)
    def test_03_drafts_and_media_are_private(self):
        lid,body,_=self.lesson()
        catalog=self.guest.request('/api/catalog')[1]
        self.assertNotIn(lid,[l['id'] for l in catalog['lessons']])
        self.assertEqual(self.guest.request('/api/media/'+body['media_id'])[0],404)
        self.assertEqual(self.guest.request('/api/lessons/'+lid+'/comments')[0],404)
        body['published']=True
        self.assertEqual(self.admin.request('/api/lessons/'+lid,'PATCH',body)[0],200)
        self.assertIn(lid,[l['id'] for l in self.guest.request('/api/catalog')[1]['lessons']])
        status,raw,h=self.guest.request('/api/media/'+body['media_id'],headers={'Range':'bytes=0-3'})
        self.assertEqual(status,206);self.assertEqual(raw,b'\x1aE\xdf\xa3');self.assertTrue(h['Content-Range'].startswith('bytes 0-3/'))
    def test_04_progress_is_individual_and_bounded(self):
        lid,_,_=self.lesson(True)
        route='/api/lessons/'+lid+'/progress'
        self.assertEqual(self.guest.request(route,'POST',{'position':10,'watched':30})[0],401)
        result=self.student.request(route,'POST',{'position':10,'watched':30})[1]
        self.assertFalse(result['completed']);self.assertEqual(result['watched'],0)
        # A second heartbeat cannot instantly credit an entire lesson.
        result=self.student.request(route,'POST',{'position':10,'watched':30})[1]
        self.assertFalse(result['completed']);self.assertLess(result['watched'],1)
        with server.db() as c: c.execute('UPDATE progress SET last_seen=? WHERE user_id=? AND lesson_id=?',(time.time()-10,self.learner['user']['id'],lid));c.commit()
        result=self.student.request(route,'POST',{'position':10,'watched':10})[1]
        self.assertTrue(result['completed'])
        self.assertNotIn(lid,[p['lesson_id'] for p in self.admin.request('/api/catalog')[1]['progress']])
        report=self.admin.request('/api/students')[1]
        self.assertIn(lid,[r['lesson_id'] for r in report['records']])
    def test_05_csrf_and_cross_origin_are_rejected(self):
        old=self.admin.csrf;self.admin.csrf='wrong'
        self.assertEqual(self.admin.request('/api/modules','POST',{'title':'CSRF'})[0],403)
        self.admin.csrf=old
        self.assertEqual(self.admin.request('/api/modules','POST',{'title':'CSRF'},headers={'Origin':'https://attacker.invalid'})[0],403)
    def test_06_uploads_enforce_offsets_and_signature(self):
        status,m,_=self.admin.request('/api/uploads','POST',{'size':10,'mime':'video/mp4'})
        self.assertEqual(status,201)
        self.assertEqual(self.student.request('/api/uploads/'+m['id']+'?offset=0','PUT',raw=b'1234567890')[0],403)
        self.assertEqual(self.admin.request('/api/uploads/'+m['id']+'?offset=2','PUT',raw=b'1234567890')[0],409)
        self.assertEqual(self.admin.request('/api/uploads/'+m['id']+'?offset=0','PUT',raw=b'1234567890')[0],200)
        self.assertEqual(self.admin.request('/api/uploads/'+m['id']+'/finish','POST',{})[0],400)
    def test_07_roles_restricted_and_revoked_immediately(self):
        uid=self.learner['user']['id']
        path='/api/users/'+uid+'/role'
        self.assertEqual(self.student.request(path,'PATCH',{'role':'admin'})[0],403)
        self.assertEqual(self.admin.request(path,'PATCH',{'role':'editor'})[0],200)
        self.assertEqual(self.student.request('/api/students')[0],200)
        self.assertEqual(self.admin.request(path,'PATCH',{'role':'student'})[0],200)
        self.assertEqual(self.student.request('/api/students')[0],403)
    def test_08_trim_and_publication_validation(self):
        mid=self.module()
        self.assertEqual(self.admin.request('/api/lessons','POST',{'module_id':mid,'title':'Sin video','published':True})[0],400)
        lid,body,_=self.lesson()
        body.update(trim_start=9,trim_end=5)
        self.assertEqual(self.admin.request('/api/lessons/'+lid,'PATCH',body)[0],400)
        self.assertEqual(self.admin.request('/api/modules/'+mid,'DELETE')[0],200)
    def test_09_comments_and_csv(self):
        lid,_,_=self.lesson(True);p='/api/lessons/'+lid+'/comments'
        self.assertEqual(self.guest.request(p,'POST',{'body':'hello'})[0],401)
        self.assertEqual(self.student.request(p,'POST',{'body':'¿Cómo funciona?'})[0],201)
        self.assertEqual(self.guest.request(p)[1][0]['body'],'¿Cómo funciona?')
        status,data,h=self.admin.request('/api/students.csv')
        self.assertEqual(status,200);self.assertIn(b'student@example.test',data)
    def test_10_private_files_not_exposed(self):
        self.assertEqual(self.guest.request('/api/media/../../../server.py')[0],404)
        response=urllib.request.urlopen(self.origin+'/')
        self.assertEqual(response.status,200)
        self.assertIn('frame-ancestors',response.headers['Content-Security-Policy'])
    def test_11_json_is_consumed_on_persistent_connections(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        conn.request('POST','/api/login',json.dumps({'email':'student@example.test','password':'a-test-password-456'}),{'Content-Type':'application/json','Origin':self.origin})
        response=conn.getresponse();cookie=response.headers['Set-Cookie'].split(';')[0];csrf=json.loads(response.read())['csrf']
        conn.request('POST','/api/logout','{}',{'Content-Type':'application/json','Origin':self.origin,'Cookie':cookie,'X-CSRF-Token':csrf})
        response=conn.getresponse();self.assertEqual(response.status,200);response.read()
        conn.request('GET','/api/me');response=conn.getresponse();self.assertEqual(response.status,200);self.assertIsNone(json.loads(response.read())['user']);conn.close()
    def test_12_health_and_proxy_address(self):
        self.assertEqual(self.guest.request('/api/health')[1],{'ok':True})
        self.assertEqual(server.request_ip('127.0.0.1','203.0.113.9'), '127.0.0.1')
        self.assertEqual(server.request_ip('127.0.0.1','spoofed, 203.0.113.9',True), '203.0.113.9')
        self.assertEqual(server.request_ip('127.0.0.1','not-an-ip',True), '127.0.0.1')
        self.assertEqual(server.request_ip('127.0.0.1','2001:db8::1',True), '2001:db8::1')
    def test_13_consistent_private_backup(self):
        import maintenance, tarfile
        self.lesson(True)
        destination=server.DATA/'backups'/'snapshot.tar'
        count=maintenance.backup(destination)
        self.assertGreater(count,0)
        with tarfile.open(destination) as archive:
            names=archive.getnames()
            self.assertIn('academy.sqlite',names)
            self.assertEqual(len([n for n in names if n.startswith('media/')]),count)
            restored=server.DATA/'restored.sqlite'
            restored.write_bytes(archive.extractfile('academy.sqlite').read())
        with server.sqlite3.connect(restored) as c:
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM media WHERE ready=0').fetchone()[0],0)
            self.assertGreater(c.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
        self.assertEqual(destination.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError): maintenance.backup(destination)
        # Backup did not sign out the live administrator.
        self.assertEqual(self.admin.request('/api/me')[1]['user']['role'],'admin')
    def test_14_reorder_modules_and_move_lessons_atomically(self):
        target=self.module();lid,_,_=self.lesson(True)
        catalog=self.admin.request('/api/catalog')[1]
        ids=[m['id'] for m in reversed(catalog['modules'])]
        self.assertEqual(self.student.request('/api/reorder','POST',{'modules':ids})[0],403)
        self.assertEqual(self.admin.request('/api/reorder','POST',{'modules':ids})[0],200)
        self.assertEqual([m['id'] for m in self.admin.request('/api/catalog')[1]['modules']],ids)
        groups={m:[] for m in ids}
        for l in catalog['lessons']: groups[target if l['id']==lid else l['module_id']].append(l['id'])
        rows=[{'id':id,'module_id':mid,'position':i} for mid,ls in groups.items() for i,id in enumerate(ls)]
        self.assertEqual(self.admin.request('/api/reorder','POST',{'lessons':rows})[0],200)
        moved=next(l for l in self.admin.request('/api/catalog')[1]['lessons'] if l['id']==lid)
        self.assertEqual(moved['module_id'],target)
        self.assertEqual(self.admin.request('/api/reorder','POST',{'lessons':rows[:-1]})[0],409)
        self.assertEqual(self.admin.request('/api/reorder','POST',{'modules':ids+[ids[0]]})[0],409)
    def test_15_text_only_lessons_and_validated_blocks(self):
        mid=self.module();body={'module_id':mid,'title':'Guía escrita','published':True,'blocks':[{'type':'heading','text':'Primer paso'},{'type':'paragraph','text':'Instrucciones escritas.'},{'type':'checklist','text':'Paso uno\nPaso dos'}]}
        status,lesson,_=self.admin.request('/api/lessons','POST',body)
        self.assertEqual(status,201,lesson);lid=lesson['id']
        row=next(l for l in self.guest.request('/api/catalog')[1]['lessons'] if l['id']==lid)
        self.assertIsNone(row['media_id']);self.assertEqual(json.loads(row['blocks'])[0]['type'],'heading')
        path='/api/lessons/'+lid+'/progress'
        self.assertEqual(self.guest.request(path,'POST',{'completed':True})[0],401)
        self.assertFalse(self.student.request(path,'POST',{'completed':False})[1]['completed'])
        self.assertTrue(self.student.request(path,'POST',{'completed':True})[1]['completed'])
        self.assertTrue(self.student.request(path,'POST',{'completed':False})[1]['completed'])
        bad={**body,'blocks':[{'type':'script','text':'bad'}]}
        self.assertEqual(self.admin.request('/api/lessons/'+lid,'PATCH',bad)[0],400)
        bad={**body,'blocks':[{'type':'video'},{'type':'video'}]}
        self.assertEqual(self.admin.request('/api/lessons/'+lid,'PATCH',bad)[0],400)

    def test_16_static_cache_revalidation(self):
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        try:
            connection.request('GET','/studio.js')
            response=connection.getresponse();content=response.read();etag=response.getheader('ETag')
            self.assertEqual(response.status,200);self.assertTrue(etag);self.assertGreater(len(content),1000)
            for validator in (etag,'W/'+etag,'"obsolete", '+etag):
                connection.request('GET','/studio.js',headers={'If-None-Match':validator})
                response=connection.getresponse()
                self.assertEqual(response.status,304);self.assertEqual(response.read(),b'')
            connection.request('GET','/studio.js',headers={'If-None-Match':'"obsolete"'})
            response=connection.getresponse();self.assertEqual(response.status,200);self.assertEqual(response.read(),content)
            lid,body,_=self.lesson()
            self.assertEqual(self.guest.request('/api/media/'+body['media_id'],headers={'If-None-Match':'*'})[0],404)
        finally: connection.close()

    def test_17_concurrent_progress_does_not_duplicate_credit(self):
        from concurrent.futures import ThreadPoolExecutor
        lid,_,_=self.lesson(True);route='/api/lessons/'+lid+'/progress'
        self.student.request(route,'POST',{'position':0,'watched':0})
        with server.db() as c:
            c.execute('UPDATE progress SET last_seen=? WHERE user_id=? AND lesson_id=?',(time.time()-5,self.learner['user']['id'],lid));c.commit()
        gate=threading.Barrier(2)
        def heartbeat(_):
            gate.wait()
            return self.student.request(route,'POST',{'position':5,'watched':5})
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(heartbeat,range(2)))
        self.assertTrue(all(result[0]==200 for result in results))
        with server.db() as c: saved=c.execute('SELECT watched,completed FROM progress WHERE user_id=? AND lesson_id=?',(self.learner['user']['id'],lid)).fetchone()
        self.assertGreaterEqual(saved['watched'],5);self.assertLess(saved['watched'],6);self.assertFalse(saved['completed'])

    def test_18_upload_size_validation(self):
        for size in (1.5,True,0,-1):
            self.assertEqual(self.admin.request('/api/uploads','POST',{'size':size,'mime':'video/webm'})[0],400)
        self.assertEqual(self.admin.request('/api/uploads','POST',{'size':10,'mime':[]})[0],400)

if __name__=='__main__': unittest.main(verbosity=2)
