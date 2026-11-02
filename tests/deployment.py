"""Build and verify the app on the managed local Docker daemon, using disposable resources."""
import json, os, subprocess, sys, time, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENV=os.environ.copy()
for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'): ENV.pop(key,None)
ENV['BUILDX_CONFIG']=str(ROOT/'.runtime/buildx')
DOCKER=['docker','--host=unix:///var/run/docker.sock']
suffix=uuid.uuid4().hex[:10]
name='academy-check-'+suffix
volume='academy-check-data-'+suffix

def docker(*args,input=None):
    return subprocess.check_output(DOCKER+list(args),input=input,text=True,env=ENV,cwd=ROOT,stderr=subprocess.STDOUT)

def launch():
    docker('run','-d','--name',name,'--read-only','--tmpfs','/tmp','--security-opt','no-new-privileges:true','--health-interval=1s','--health-start-period=1s','--mount',f'type=volume,src={volume},dst=/data','aumentados-academy:qa')
    for _ in range(30):
        state=json.loads(docker('inspect',name))[0]['State']
        if state.get('Health',{}).get('Status')=='healthy': return
        if state['Status']=='exited': raise RuntimeError(docker('logs',name))
        time.sleep(.5)
    raise RuntimeError('El contenedor no alcanzó el estado saludable.')

INIT='''
import json,urllib.request,http.cookiejar
from pathlib import Path
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def post(path,body,csrf=''):
    request=urllib.request.Request('http://127.0.0.1:8000'+path,json.dumps(body).encode(),{'Content-Type':'application/json','X-CSRF-Token':csrf})
    return json.load(opener.open(request))
session=post('/api/setup',{'email':'deployment@example.test','password':'deployment-test-only-1234','name':'Deployment check','setupCode':Path('/data/setup-code.txt').read_text()})
module=post('/api/modules',{'title':'Persistencia comprobada'},session['csrf'])
assert module['id']
print('Setup y escritura en volumen: OK')
'''
RESTORE='''
import json,urllib.request,http.cookiejar
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
request=urllib.request.Request('http://127.0.0.1:8000/api/login',json.dumps({'email':'deployment@example.test','password':'deployment-test-only-1234'}).encode(),{'Content-Type':'application/json'})
assert json.load(opener.open(request))['user']['role']=='admin'
catalog=json.load(opener.open('http://127.0.0.1:8000/api/catalog'))
assert any(m['title']=='Persistencia comprobada' for m in catalog['modules'])
print('Cuenta y módulo conservados después de recrear el contenedor: OK')
'''

try:
    built=docker('build','-t','aumentados-academy:qa','.')
    print('Imagen Docker construida: OK',flush=True)
    docker('volume','create',volume)
    launch(); print('Arranque sin root, sistema de archivos de solo lectura y healthcheck: OK',flush=True)
    print(docker('exec',name,'python3','-c',INIT).strip(),flush=True)
    docker('stop','--time','5',name);docker('rm',name)
    launch();print(docker('exec',name,'python3','-c',RESTORE).strip(),flush=True)
    config_env=ENV.copy();config_env['ACADEMY_DOMAIN']='academy.example.test'
    subprocess.run(DOCKER+['compose','config','--quiet'],env=config_env,cwd=ROOT,check=True)
    caddy=docker('run','--rm','-i','-e','ACADEMY_DOMAIN=academy.example.test','caddy:2-alpine','caddy','validate','--adapter','caddyfile','--config','/dev/stdin',input=(ROOT/'Caddyfile').read_text())
    print('Compose y configuración de Caddy válidos: OK',flush=True)
    print('VALIDACIÓN DE DESPLIEGUE LOCAL COMPLETADA. No publica un dominio ni verifica certificados públicos.',flush=True)
except subprocess.CalledProcessError as e:
    print(e.output or str(e),file=sys.stderr);sys.exit(1)
finally:
    subprocess.run(DOCKER+['rm','-f',name],env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(DOCKER+['volume','rm',volume],env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
