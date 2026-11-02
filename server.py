#!/usr/bin/env python3
"""Aumentados Academy. Python 3.12+, SQLite, no server dependencies."""
import argparse, csv, hashlib, hmac, io, ipaddress, json, mimetypes, os, re, secrets, sqlite3, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from threading import RLock

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('ACADEMY_DATA_DIR', ROOT / '.runtime'))
LOCK = RLock()
MAX_VIDEO = 2 * 1024**3
COOKIE_SECURE = os.environ.get('ACADEMY_SECURE_COOKIES') == '1'
TRUST_PROXY = os.environ.get('ACADEMY_TRUST_PROXY') == '1'

def request_ip(direct, forwarded='', trust_proxy=False):
    if trust_proxy and forwarded:
        try: return str(ipaddress.ip_address(forwarded.split(',')[-1].strip()))
        except ValueError: pass
    return direct

class Database(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

def db():
    c = sqlite3.connect(DATA / 'academy.sqlite', timeout=30, factory=Database)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()

def initialize():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    (DATA / 'media').mkdir(exist_ok=True)
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','editor','student')),created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS modules(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',position INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),mime TEXT NOT NULL,size INTEGER NOT NULL,received INTEGER NOT NULL DEFAULT 0,ready INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY,module_id TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',tags TEXT NOT NULL DEFAULT '',media_id TEXT REFERENCES media(id),duration REAL NOT NULL DEFAULT 0,trim_start REAL NOT NULL DEFAULT 0,trim_end REAL NOT NULL DEFAULT 0,captions TEXT NOT NULL DEFAULT '[]',published INTEGER NOT NULL DEFAULT 0,position INTEGER NOT NULL DEFAULT 0,author TEXT NOT NULL REFERENCES users(id),created REAL NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS progress(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,lesson_id TEXT REFERENCES lessons(id) ON DELETE CASCADE,position REAL NOT NULL DEFAULT 0,watched REAL NOT NULL DEFAULT 0,completed INTEGER NOT NULL DEFAULT 0,last_seen REAL NOT NULL,PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),lesson_id TEXT REFERENCES lessons(id) ON DELETE CASCADE,body TEXT NOT NULL,created REAL NOT NULL);
        ''')
        c.executescript("""
        CREATE INDEX IF NOT EXISTS lessons_module_order ON lessons(module_id,position,created);
        CREATE INDEX IF NOT EXISTS lessons_media_visibility ON lessons(media_id,published);
        CREATE INDEX IF NOT EXISTS comments_lesson_order ON comments(lesson_id,created);
        CREATE INDEX IF NOT EXISTS progress_lesson ON progress(lesson_id);
        CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
        """)
        if 'blocks' not in {row['name'] for row in c.execute('PRAGMA table_info(lessons)')}:
            c.execute("ALTER TABLE lessons ADD COLUMN blocks TEXT NOT NULL DEFAULT '[]'")
        if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            p = DATA / 'setup-code.txt'
            if not p.exists():
                p.write_text(secrets.token_urlsafe(32))
                p.chmod(0o600)

class APIError(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

def require(condition, message, status=400):
    if not condition: raise APIError(status, message)

def text_field(data, key, limit=200, required=True):
    value = data.get(key, '')
    require(isinstance(value, str), 'Campo inválido: ' + key)
    value = value.strip()
    require((bool(value) or not required) and len(value) <= limit, 'Revisa el campo: ' + key)
    return value

def number(data, key, default=0, maximum=86400):
    val = data.get(key, default)
    require(type(val) in (int, float) and 0 <= val <= maximum, 'Valor inválido: ' + key)
    return val

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(60)
    def log_message(self, fmt, *args):
        # Never log request bodies, cookies or tokens.
        pass

    def respond(self, data, status=200, headers=None):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        if status >= 400:
            self.send_header('Connection','close')
            self.close_connection=True
        self.security_headers()
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers()
        self.wfile.write(raw)

    def security_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        self.send_header('Permissions-Policy','camera=(self), microphone=(self), display-capture=(self)')

    def body(self, limit=1024*1024):
        require(self.headers.get('Transfer-Encoding') is None, 'Se requiere Content-Length')
        try: n = int(self.headers.get('Content-Length', '0'))
        except ValueError: raise APIError(400,'Longitud inválida')
        require(0 < n <= limit, 'Archivo o solicitud demasiado grande',413)
        raw = self.rfile.read(n)
        require(len(raw)==n,'Solicitud incompleta')
        return raw

    def json_body(self):
        if getattr(self,'cached_json',None) is not None: return self.cached_json
        require(self.headers.get('Content-Type','').split(';')[0]=='application/json','Se requiere JSON',415)
        try: obj = json.loads(self.body())
        except (ValueError,UnicodeError): raise APIError(400,'JSON inválido')
        require(isinstance(obj,dict),'Solicitud inválida')
        self.cached_json=obj
        return obj

    def identity(self, c):
        cookie = self.headers.get('Cookie','')
        match = re.search(r'(?:^|;\s*)academy_session=([A-Za-z0-9_-]+)', cookie)
        self.session = None
        if match:
            self.session = c.execute('SELECT s.token,s.csrf,u.id,u.email,u.name,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(hashlib.sha256(match[1].encode()).hexdigest(),time.time())).fetchone()
        return self.session

    def auth(self, roles=None):
        require(self.session is not None,'Inicia sesión para continuar',401)
        if roles: require(self.session['role'] in roles,'No tienes permiso para esta acción',403)
        return self.session

    def check_origin(self):
        origin = self.headers.get('Origin')
        if origin:
            require(urlparse(origin).netloc == self.headers.get('Host'), 'Origen no permitido',403)
        require(self.headers.get('Sec-Fetch-Site') != 'cross-site','Origen no permitido',403)

    def login(self, c, user):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,time.time()+86400*7))
        c.commit()
        cookie = f'academy_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800' + ('; Secure' if COOKIE_SECURE else '')
        self.respond({'user':{k:user[k] for k in ('id','name','email','role')},'csrf':csrf},headers={'Set-Cookie':cookie})

    def visible_lesson(self, c, lid):
        row = c.execute('SELECT * FROM lessons WHERE id=?',(lid,)).fetchone()
        require(row is not None and (row['published'] or self.session and self.session['role'] in ('admin','editor')), 'Lección no encontrada',404)
        return row

    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def do_PUT(self): self.dispatch()
    def do_PATCH(self): self.dispatch()
    def do_DELETE(self): self.dispatch()

    def dispatch(self):
        try:
            self.cached_json=None
            self.path_only = urlparse(self.path).path
            if self.path_only.startswith('/api/'):
                with db() as c:
                    self.identity(c)
                    if self.command != 'GET':
                        self.check_origin()
                        if self.session:
                            require(hmac.compare_digest(self.headers.get('X-CSRF-Token',''),self.session['csrf']),'La sesión cambió. Recarga la página.',403)
                        # Consume every JSON body, including empty finalize/logout payloads,
                        # before reusing an HTTP/1.1 connection for its next request.
                        if self.headers.get('Content-Type','').split(';')[0]=='application/json': self.json_body()
                    self.api(c)
            elif self.command=='GET': self.static()
            else: raise APIError(405,'Método no permitido')
        except APIError as e: self.respond({'error':e.message},e.status)
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e:
            print('Request failed:', type(e).__name__, flush=True)
            self.respond({'error':'No se pudo completar la solicitud'},500)

    def api(self, c):
        p, method, now = self.path_only, self.command, time.time()
        if p=='/api/health' and method=='GET':
            c.execute('SELECT id FROM modules LIMIT 1').fetchone()
            self.respond({'ok':True}); return
        if p=='/api/me' and method=='GET':
            user = {k:self.session[k] for k in ('id','name','email','role')} if self.session else None
            self.respond({'user':user,'csrf':self.session['csrf'] if self.session else None,'setupRequired':not bool(c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone())}); return
        if p in ('/api/login','/api/register','/api/setup') and method=='POST':
            # Per-client login/registration throttling, bounded in memory.
            key=request_ip(self.client_address[0],self.headers.get('X-Forwarded-For',''),TRUST_PROXY)
            with LOCK:
                rate=RATE.setdefault(key,[])
                rate[:]=[x for x in rate if x>now-300]
                require(len(rate)<20,'Demasiados intentos. Espera cinco minutos.',429)
                rate.append(now)
                if len(RATE)>10000: RATE.clear()
            d=self.json_body(); email=text_field(d,'email',254).lower(); password=text_field(d,'password',256)
            require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email),'Correo inválido')
            if p=='/api/login':
                u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                stored=u['password'] if u else password_hash('timing-placeholder')
                require(u is not None and hmac.compare_digest(stored,password_hash(password,stored.split(':')[0])),'Correo o contraseña incorrectos',401)
                self.login(c,u); return
            require(len(password)>=12,'Usa al menos 12 caracteres en tu contraseña')
            name=text_field(d,'name',100)
            role='student'
            if p=='/api/setup':
                with LOCK:
                    require(not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone(),'La administración ya está configurada',409)
                    token=text_field(d,'setupCode',100)
                    require(hmac.compare_digest(token,(DATA/'setup-code.txt').read_text().strip()),'Código de instalación incorrecto',403)
                    role='admin'
            require(not c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(),'Este correo ya tiene cuenta',409)
            uid=secrets.token_hex(16)
            with LOCK:
                if role=='admin':
                    c.execute('BEGIN IMMEDIATE')
                    require(not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone(),'La administración ya está configurada',409)
                c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,email,name,password_hash(password),role,now)); c.commit()
            if role=='admin': (DATA/'setup-code.txt').unlink(missing_ok=True)
            self.login(c,c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()); return
        if p=='/api/logout' and method=='POST':
            if self.session: c.execute('DELETE FROM sessions WHERE token=?',(self.session['token'],)); c.commit()
            self.respond({'ok':True},headers={'Set-Cookie':'academy_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'}); return
        if p=='/api/catalog' and method=='GET':
            team=self.session and self.session['role'] in ('admin','editor')
            lessons=[dict(x) for x in c.execute('SELECT l.*,u.name AS author_name FROM lessons l JOIN users u ON u.id=l.author '+('' if team else 'WHERE published=1 ')+'ORDER BY position,created')]
            modules=[dict(x) for x in c.execute('SELECT * FROM modules ORDER BY position,created')]
            progress=[dict(x) for x in c.execute('SELECT * FROM progress WHERE user_id=?',(self.session['id'],))] if self.session else []
            self.respond({'modules':modules,'lessons':lessons,'progress':progress}); return
        if p=='/api/modules' and method=='POST':
            self.auth(('admin','editor')); d=self.json_body(); mid=secrets.token_hex(16)
            c.execute('INSERT INTO modules VALUES(?,?,?,?,?)',(mid,text_field(d,'title'),text_field(d,'description',5000,False),number(d,'position',0,10000),now)); c.commit()
            self.respond({'id':mid},201); return
        if p=='/api/reorder' and method=='POST':
            self.auth(('admin','editor')); d=self.json_body()
            require(set(d) in ({'modules'},{'lessons'}),'Orden inválido')
            c.execute('BEGIN IMMEDIATE')
            mids={row['id'] for row in c.execute('SELECT id FROM modules')}
            if 'modules' in d:
                ids=d['modules']
                require(isinstance(ids,list) and all(isinstance(x,str) for x in ids),'Orden de módulos inválido')
                require(len(ids)==len(mids) and set(ids)==mids,'El contenido cambió. Recarga antes de ordenar.',409)
                c.executemany('UPDATE modules SET position=? WHERE id=?',[(i,id) for i,id in enumerate(ids)])
            else:
                rows=d['lessons']; require(isinstance(rows,list),'Orden de lecciones inválido')
                expected={row['id'] for row in c.execute('SELECT id FROM lessons')}; seen=set();positions=set();updates=[]
                for row in rows:
                    require(isinstance(row,dict),'Orden de lecciones inválido')
                    lid=text_field(row,'id',32);mid=text_field(row,'module_id',32);position=number(row,'position',0,10000)
                    require(lid not in seen and mid in mids and type(position)==int and (mid,position) not in positions,'Orden de lecciones inválido')
                    seen.add(lid);positions.add((mid,position));updates.append((mid,position,lid))
                require(seen==expected,'El contenido cambió. Recarga antes de ordenar.',409)
                c.executemany('UPDATE lessons SET module_id=?,position=? WHERE id=?',updates)
            c.commit();self.respond({'ok':True});return
        match=re.fullmatch(r'/api/modules/([a-f0-9]{32})',p)
        if match and method in ('PATCH','DELETE'):
            self.auth(('admin','editor')); mid=match[1]
            require(c.execute('SELECT 1 FROM modules WHERE id=?',(mid,)).fetchone(),'Módulo no encontrado',404)
            if method=='DELETE':
                require(not c.execute('SELECT 1 FROM lessons WHERE module_id=?',(mid,)).fetchone(),'Mueve o elimina las lecciones antes de borrar el módulo',409)
                c.execute('DELETE FROM modules WHERE id=?',(mid,))
            else:
                d=self.json_body(); c.execute('UPDATE modules SET title=?,description=?,position=? WHERE id=?',(text_field(d,'title'),text_field(d,'description',5000,False),number(d,'position',0,10000),mid))
            c.commit(); self.respond({'ok':True}); return
        if p=='/api/lessons' and method=='POST' or re.fullmatch(r'/api/lessons/[a-f0-9]{32}',p) and method=='PATCH':
            self.auth(('admin','editor')); d=self.json_body(); lid=p.rsplit('/',1)[1] if method=='PATCH' else secrets.token_hex(16)
            if method=='PATCH': require(c.execute('SELECT 1 FROM lessons WHERE id=?',(lid,)).fetchone(),'Lección no encontrada',404)
            mid=text_field(d,'module_id',32)
            require(c.execute('SELECT 1 FROM modules WHERE id=?',(mid,)).fetchone(),'Selecciona un módulo válido')
            media=d.get('media_id') or None
            if media: require(c.execute('SELECT 1 FROM media WHERE id=? AND ready=1',(media,)).fetchone(),'El video todavía no está disponible')
            published=1 if d.get('published') is True else 0
            raw_blocks=d.get('blocks')
            if raw_blocks is None:
                raw_blocks=([{'type':'video'}] if media else [])+([{'type':'paragraph','text':d.get('description','')}] if d.get('description') else [])
            require(isinstance(raw_blocks,list) and len(raw_blocks)<=200,'Se permiten hasta 200 bloques')
            blocks=[]
            for block in raw_blocks:
                require(isinstance(block,dict) and block.get('type') in ('paragraph','heading','callout','checklist','divider','video'),'Tipo de bloque inválido')
                b={'type':block['type']}
                if b['type'] not in ('video','divider'): b['text']=text_field(block,'text',10000,False)
                blocks.append(b)
            videos=sum(b['type']=='video' for b in blocks)
            require(videos<=1,'Cada lección admite un bloque de video. Crea otra lección para otro video.')
            if not videos: media=None
            has_text=any(b.get('text') for b in blocks if b['type'] not in ('video','divider'))
            require(not published or (videos and media) or (not videos and has_text),'Agrega el video del bloque o escribe el contenido antes de publicar')
            duration=number(d,'duration'); start=number(d,'trim_start'); end=number(d,'trim_end')
            if not videos: duration=start=end=0
            require(start<end<=duration if end else start<duration if duration else start==0,'El recorte debe estar dentro de la duración del video')
            require(not published or not videos or duration>0,'Se necesita una duración válida antes de publicar')
            captions=d.get('captions',[])
            require(isinstance(captions,list) and len(captions)<=10000,'Subtítulos inválidos')
            clean=[]
            for item in captions:
                require(isinstance(item,dict),'Subtítulos inválidos')
                a=number(item,'start'); b=number(item,'end'); require(b>a,'Intervalo de subtítulo inválido')
                clean.append({'start':a,'end':b,'text':text_field(item,'text',1000)})
            values=(mid,text_field(d,'title'),text_field(d,'description',50000,False),text_field(d,'tags',500,False),media,duration,start,end,json.dumps(clean),published,number(d,'position',0,10000),json.dumps(blocks))
            if method=='PATCH': c.execute('UPDATE lessons SET module_id=?,title=?,description=?,tags=?,media_id=?,duration=?,trim_start=?,trim_end=?,captions=?,published=?,position=?,blocks=?,updated=? WHERE id=?',values+(now,lid))
            else: c.execute('INSERT INTO lessons (id,module_id,title,description,tags,media_id,duration,trim_start,trim_end,captions,published,position,blocks,author,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(lid,)+values+(self.session['id'],now,now))
            c.commit(); self.respond({'id':lid},201 if method=='POST' else 200); return
        match=re.fullmatch(r'/api/lessons/([a-f0-9]{32})',p)
        if match and method=='DELETE':
            self.auth(('admin','editor')); c.execute('DELETE FROM lessons WHERE id=?',(match[1],)); c.commit(); self.respond({'ok':True}); return
        match=re.fullmatch(r'/api/lessons/([a-f0-9]{32})/(progress|comments)',p)
        if match:
            lesson=self.visible_lesson(c,match[1]); kind=match[2]
            if kind=='comments' and method=='GET':
                self.respond([dict(x) for x in c.execute('SELECT c.id,c.body,c.created,u.name,u.role FROM comments c JOIN users u ON u.id=c.user_id WHERE lesson_id=? ORDER BY c.created',(match[1],))]); return
            self.auth(); d=self.json_body()
            if kind=='comments' and method=='POST':
                c.execute('INSERT INTO comments VALUES(?,?,?,?,?)',(secrets.token_hex(16),self.session['id'],match[1],text_field(d,'body',3000),now)); c.commit(); self.respond({'ok':True},201); return
            if kind=='progress' and method=='POST':
                if not lesson['media_id']:
                    completed=1 if d.get('completed') is True else 0
                    c.execute('INSERT INTO progress VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,lesson_id) DO UPDATE SET completed=MAX(progress.completed,excluded.completed),last_seen=excluded.last_seen',(self.session['id'],match[1],0,0,completed,now));c.commit()
                    saved=c.execute('SELECT completed FROM progress WHERE user_id=? AND lesson_id=?',(self.session['id'],match[1])).fetchone()
                    self.respond({'completed':bool(saved['completed']),'watched':0});return
                position=number(d,'position'); watched=number(d,'watched',0,30)
                length=(lesson['trim_end'] or lesson['duration'])-lesson['trim_start']
                require(length>0,'No se conoce la duración de esta lección')
                # Serialize the read/credit/write cycle across concurrent heartbeats.
                c.execute('BEGIN IMMEDIATE')
                prior=c.execute('SELECT * FROM progress WHERE user_id=? AND lesson_id=?',(self.session['id'],match[1])).fetchone()
                # Bound credited playback to wall time between heartbeats; seeking alone earns no credit.
                allowed=min(30,max(0,now-prior['last_seen'])) if prior else 0
                total=min(length,(prior['watched'] if prior else 0)+min(watched,allowed))
                completed=bool(prior and prior['completed']) or total>=length*.9
                c.execute('INSERT INTO progress VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,lesson_id) DO UPDATE SET position=excluded.position,watched=excluded.watched,completed=excluded.completed,last_seen=excluded.last_seen',(self.session['id'],match[1],min(position,lesson['duration']),total,int(completed),now)); c.commit()
                self.respond({'completed':completed,'watched':total}); return
        if p=='/api/uploads' and method=='POST':
            self.auth(('admin','editor')); d=self.json_body(); size=number(d,'size',0,MAX_VIDEO)
            require(type(size) is int and size>0,'El tamaño del video debe ser un entero positivo')
            mime=text_field(d,'mime',100).split(';')[0]
            require(mime in ('video/webm','video/mp4','video/quicktime','video/ogg'),'Formato no compatible. Usa WebM, MP4, MOV u OGV.')
            # Reserve storage atomically so simultaneous uploads respect the limit.
            c.execute('BEGIN IMMEDIATE')
            usage=c.execute('SELECT COALESCE(SUM(size),0) FROM media').fetchone()[0]
            require(usage+size<=int(os.environ.get('ACADEMY_STORAGE_LIMIT',20*1024**3)),'Se alcanzó el límite de almacenamiento',413)
            uid=secrets.token_hex(16); c.execute('INSERT INTO media VALUES(?,?,?,?,?,?,?)',(uid,self.session['id'],mime,int(size),0,0,now)); c.commit()
            (DATA/'media'/uid).touch(); self.respond({'id':uid},201); return
        match=re.fullmatch(r'/api/uploads/([a-f0-9]{32})(/finish)?',p)
        if match:
            self.auth(('admin','editor')); uid=match[1]
            row=c.execute('SELECT * FROM media WHERE id=? AND owner=?',(uid,self.session['id'])).fetchone()
            require(row is not None,'Subida no encontrada',404); require(not row['ready'],'La subida ya terminó',409)
            if method=='PUT' and not match[2]:
                chunk=self.body(8*1024**2); offset=parse_qs(urlparse(self.path).query).get('offset',[''])[0]
                with LOCK:
                    c.execute('BEGIN IMMEDIATE')
                    row=c.execute('SELECT * FROM media WHERE id=?',(uid,)).fetchone()
                    require(offset==str(row['received']),'Posición de subida incorrecta',409)
                    require(row['received']+len(chunk)<=row['size'],'Tamaño de subida incorrecto')
                    with (DATA/'media'/uid).open('r+b') as f: f.seek(row['received']); f.write(chunk)
                    c.execute('UPDATE media SET received=received+? WHERE id=?',(len(chunk),uid)); c.commit()
                self.respond({'received':row['received']+len(chunk)}); return
            if method=='POST' and match[2]:
                require(row['received']==row['size'],'La subida está incompleta')
                with (DATA/'media'/uid).open('rb') as f: magic=f.read(64)
                valid=(row['mime']=='video/webm' and magic.startswith(b'\x1aE\xdf\xa3') or row['mime'] in ('video/mp4','video/quicktime') and b'ftyp' in magic[:32] or row['mime']=='video/ogg' and magic.startswith(b'OggS'))
                require(valid,'El contenido no corresponde a un video compatible')
                c.execute('UPDATE media SET ready=1 WHERE id=?',(uid,)); c.commit(); self.respond({'id':uid}); return
        match=re.fullmatch(r'/api/media/([a-f0-9]{32})',p)
        if match and method=='GET':
            uid=match[1]; row=c.execute('SELECT * FROM media WHERE id=? AND ready=1',(uid,)).fetchone()
            allowed=self.session and self.session['role'] in ('admin','editor') or c.execute('SELECT 1 FROM lessons WHERE media_id=? AND published=1',(uid,)).fetchone()
            require(row and allowed,'Video no encontrado',404)
            self.file(DATA/'media'/uid,row['mime'],ranges=True); return
        if p in ('/api/students','/api/students.csv') and method=='GET':
            self.auth(('admin','editor'))
            lessons=c.execute('SELECT COUNT(*) FROM lessons WHERE published=1').fetchone()[0]
            students=[dict(x) for x in c.execute("SELECT u.id,u.name,u.email,u.role,u.created,COUNT(CASE WHEN l.published=1 AND p.completed=1 THEN 1 END) AS completed,COALESCE(SUM(CASE WHEN l.published=1 THEN p.watched ELSE 0 END),0) AS watched,MAX(p.last_seen) AS last_seen FROM users u LEFT JOIN progress p ON p.user_id=u.id LEFT JOIN lessons l ON l.id=p.lesson_id GROUP BY u.id ORDER BY last_seen DESC,u.created DESC")]
            records=[dict(x) for x in c.execute('SELECT p.*,l.title,l.module_id FROM progress p JOIN lessons l ON l.id=p.lesson_id WHERE l.published=1 ORDER BY p.last_seen DESC')]
            if p.endswith('.csv'):
                stream=io.StringIO(); w=csv.writer(stream); w.writerow(['Nombre','Correo','Rol','Lecciones completadas','Total lecciones','Segundos vistos','Última actividad'])
                def safe(v): return "'"+v if isinstance(v,str) and v[:1] in '=+-@\t\r' else v
                for s in students: w.writerow([safe(s['name']),safe(s['email']),s['role'],s['completed'],lessons,round(s['watched']),time.strftime('%Y-%m-%d %H:%M',time.gmtime(s['last_seen'])) if s['last_seen'] else ''])
                raw=('\ufeff'+stream.getvalue()).encode(); self.send_response(200); self.send_header('Content-Type','text/csv; charset=utf-8'); self.send_header('Content-Disposition','attachment; filename="avances-aumentados.csv"'); self.send_header('Content-Length',str(len(raw))); self.security_headers(); self.end_headers(); self.wfile.write(raw); return
            self.respond({'students':students,'records':records,'totalLessons':lessons}); return
        match=re.fullmatch(r'/api/users/([a-f0-9]{32})/role',p)
        if match and method=='PATCH':
            self.auth(('admin',)); role=self.json_body().get('role'); require(role in ('admin','editor','student'),'Rol inválido')
            require(match[1]!=self.session['id'],'No puedes cambiar tu propio rol')
            require(c.execute('SELECT 1 FROM users WHERE id=?',(match[1],)).fetchone(),'Usuario no encontrado',404)
            c.execute('UPDATE users SET role=? WHERE id=?',(role,match[1])); c.commit(); self.respond({'ok':True}); return
        raise APIError(404,'Ruta no encontrada')

    def file(self, path, mime=None, ranges=False):
        require(path.is_file(),'Archivo no encontrado',404)
        stat=path.stat()
        size=stat.st_size; start,end=0,size-1; status=200
        # Revalidate public assets without resending the model/WASM on every visit.
        # Protected media always goes through authorization and bypasses this cache.
        etag=f'"{stat.st_mtime_ns:x}-{size:x}"' if not ranges else None
        if etag and self.headers.get('If-None-Match'):
            candidates=self.headers['If-None-Match'].split(',')
            if any(value.strip().removeprefix('W/') in (etag,'*') for value in candidates):
                self.send_response(304)
                self.send_header('ETag',etag)
                self.send_header('Cache-Control','no-cache')
                self.security_headers()
                self.end_headers()
                return
        range_header=self.headers.get('Range') if ranges else None
        if range_header:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            require(m and (m[1] or m[2]),'Rango inválido',416)
            if not m[1]: start=max(0,size-int(m[2]))
            else: start=int(m[1]); end=min(size-1,int(m[2])) if m[2] else size-1
            require(0<=start<=end<size,'Rango inválido',416); status=206
        self.send_response(status); self.send_header('Content-Type',mime or mimetypes.guess_type(path)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(end-start+1)); self.security_headers()
        self.send_header('Cache-Control','private, no-store' if ranges else 'no-cache')
        if etag: self.send_header('ETag',etag)
        if ranges: self.send_header('Accept-Ranges','bytes')
        if status==206: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if path.suffix=='.html': self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
        self.end_headers()
        with path.open('rb') as f:
            f.seek(start); remaining=end-start+1
            while remaining>0:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk: break
                self.wfile.write(chunk); remaining-=len(chunk)

    def static(self):
        path=(ROOT/'public'/self.path_only.lstrip('/')).resolve()
        require(path.is_relative_to(ROOT/'public'),'Ruta no permitida',403)
        if self.path_only=='/' or not Path(self.path_only).suffix: path=ROOT/'public/index.html'
        self.file(path)

RATE={}
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--host',default='127.0.0.1'); parser.add_argument('--port',type=int,default=8000); parser.add_argument('--open-browser',action='store_true'); args=parser.parse_args()
    initialize()
    server=ThreadingHTTPServer((args.host,args.port),Handler); server.daemon_threads=True
    print(f'Aumentados Academy: http://{args.host}:{args.port}',flush=True)
    if (DATA/'setup-code.txt').exists(): print(f'Primera instalación: consulta el código privado en {DATA / "setup-code.txt"}',flush=True)
    if args.open_browser: webbrowser.open(f'http://localhost:{args.port}')
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
