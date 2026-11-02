#!/usr/bin/env python3
"""Build a self-contained, clearly labelled local UI demo; never changes real data."""
import argparse, base64, json, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--hosted-output',type=Path,help='Also generate the HTTPS demo with the recorder enabled.')
args=parser.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    video=Path(tmp)/'example.webm'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=0x8854c9:s=640x360:d=5','-vf','drawtext=text=VIDEO DE EJEMPLO:fontcolor=white:fontsize=28:x=(w-text_w)/2:y=(h-text_h)/2','-c:v','libvpx','-an','-y',str(video)],check=True)
    data='data:video/webm;base64,'+base64.b64encode(video.read_bytes()).decode()

prefix=r'''
const demoSample=__VIDEO__;
const demoIds={admin:'a'.repeat(32),editor:'e'.repeat(32),student:'b'.repeat(32)};
const demoUsers=[{id:demoIds.admin,name:'Equipo Aumentados · Demo',email:'equipo@example.test',role:'admin',created:Date.now()/1000},{id:demoIds.editor,name:'Editor · Demo',email:'editor@example.test',role:'editor',created:Date.now()/1000},{id:demoIds.student,name:'Estudiante · Demo',email:'estudiante@example.test',role:'student',created:Date.now()/1000}];
const demoSeed={modules:[{id:'1'.repeat(32),title:'Primeros pasos en Aumentados',description:'Contenido de ejemplo para revisar cómo se organizan las primeras lecciones.',position:0},{id:'2'.repeat(32),title:'Organiza tu conocimiento',description:'Revisa la navegación entre módulos, videos e instrucciones.',position:1},{id:'3'.repeat(32),title:'Soporte y ayuda',description:'Un espacio de ejemplo para resolver preguntas frecuentes.',position:2}],lessons:[],progress:[],comments:[]};
demoSeed.lessons=[['4','1','Bienvenido a tu academia',true],['5','1','Tu primera ruta de aprendizaje',true],['6','2','Encuentra el tutorial que necesitas',true],['7','3','Una respuesta, paso a paso',false]].map(([id,module,title,published],i)=>({id:id.repeat(32),module_id:module.repeat(32),title,description:'LECCIÓN DE EJEMPLO\n\nEste video breve sirve para probar el reproductor y el seguimiento. No es un tutorial real de la plataforma.\n\nPuedes editar este texto desde Contenido, cambiar el título y revisar cómo lo verá un estudiante.',tags:'ejemplo, demostración',media_id:'c'.repeat(32),duration:5,trim_start:0,trim_end:0,captions:JSON.stringify([{start:0,end:5,text:'Video de ejemplo para probar la academia.'}]),published:published?1:0,position:i,author:demoIds.admin,author_name:'Equipo Aumentados · Demo',created:Date.now()/1000,updated:Date.now()/1000}));
demoSeed.version=2;demoSeed.lessons.push({id:'8'.repeat(32),module_id:'3'.repeat(32),title:'Guía escrita: prepara tu aprendizaje',description:'Una lección de lectura para acompañar las cápsulas de video.',tags:'lectura, guía',media_id:null,duration:0,trim_start:0,trim_end:0,captions:'[]',published:1,position:4,author:demoIds.admin,author_name:'Equipo Aumentados · Demo',blocks:JSON.stringify([{type:'heading',text:'Antes de comenzar'},{type:'paragraph',text:'No todo necesita un video. En esta página puedes organizar las instrucciones que el estudiante necesita consultar a su ritmo.'},{type:'checklist',text:'Explora los módulos disponibles\nRevisa una lección de ejemplo\nMarca esta guía como leída'},{type:'callout',text:'Puedes mover estos bloques desde Contenido y combinar una explicación grabada con pasos escritos.'}])});
let demoData=structuredClone(demoSeed),demoRole='admin';
try{const saved=JSON.parse(localStorage.getItem('aumentados-ui-demo-v1'));if(saved?.data?.modules&&saved?.data?.lessons){demoData=saved.data;demoRole=saved.role||'admin'}}catch{}
if(!demoData.version){if(!demoData.lessons.some(l=>l.id==='8'.repeat(32)))demoData.lessons.push(structuredClone(demoSeed.lessons.at(-1)));demoData.version=2}
function demoWrite(){try{localStorage.setItem('aumentados-ui-demo-v1',JSON.stringify({data:demoData,role:demoRole}))}catch{}}
const demoUser=()=>demoRole==='guest'?null:demoUsers.find(u=>u.id===demoIds[demoRole]);
const demoMediaURL=id=>demoSample;
const demoId=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');
function demoStudents(){const total=demoData.lessons.filter(l=>l.published).length;return {totalLessons:total,students:demoUsers.map(u=>{const rows=demoData.progress.filter(p=>p.user_id===u.id);return {...u,completed:rows.filter(p=>p.completed&&demoData.lessons.some(l=>l.id===p.lesson_id&&l.published)).length,watched:rows.reduce((n,p)=>n+p.watched,0),last_seen:Math.max(0,...rows.map(p=>p.last_seen))}}),records:demoData.progress.map(p=>({...p,title:demoData.lessons.find(l=>l.id===p.lesson_id)?.title||''}))}}
function demoCSVURL(){const data=demoStudents();const csv='Nombre,Correo,Lecciones completadas,Total\n'+data.students.map(s=>[s.name,s.email,s.completed,data.totalLessons].map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\n');return URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}))}
async function demoAPI(path,options={}){
  const method=options.method||'GET',body=options.body||{},user=demoUser(),isTeam=user&&user.role!=='student';
  if(path==='/api/me')return {user,csrf:'local-demo-only',setupRequired:false};
  if(path==='/api/catalog')return {modules:structuredClone(demoData.modules).sort((a,b)=>a.position-b.position),lessons:structuredClone(demoData.lessons.filter(l=>l.published||isTeam)).sort((a,b)=>a.position-b.position),progress:structuredClone(demoData.progress.filter(p=>p.user_id===user?.id))};
  if(path==='/api/logout'){demoRole='guest';demoWrite();return {ok:true}}
  if(['/api/login','/api/register','/api/setup'].includes(path))throw Error('Esta demo no crea cuentas reales. Usa el selector de rol de la barra superior; no introduzcas contraseñas reales.');
  if(path==='/api/students'){if(!isTeam)throw Error('Espacio exclusivo del equipo');return demoStudents()}
  if(path.startsWith('/api/uploads'))throw Error('La subida de videos reales se prueba en la aplicación completa. En esta demo puedes editar las lecciones de ejemplo.');
  const match=path.match(/^\/api\/lessons\/([^/]+)\/(progress|comments)$/);
  if(match){const [_,id,kind]=match;const lesson=demoData.lessons.find(l=>l.id===id);if(!lesson||!lesson.published&&!isTeam)throw Error('Lección no encontrada');if(kind==='comments'&&method==='GET')return demoData.comments.filter(c=>c.lesson_id===id);if(!user)throw Error('Selecciona el rol Estudiante para guardar tu progreso de prueba');if(kind==='comments'){demoData.comments.push({id:demoId(),lesson_id:id,user_id:user.id,name:user.name,role:user.role,body:body.body,created:Date.now()/1000});demoWrite();return {ok:true}}let p=demoData.progress.find(p=>p.user_id===user.id&&p.lesson_id===id);if(!p){p={user_id:user.id,lesson_id:id,watched:0,completed:0};demoData.progress.push(p)}p.position=body.position;if(!lesson.media_id){p.watched=0;p.completed=p.completed||body.completed?1:0;p.last_seen=Date.now()/1000;demoWrite();return {completed:!!p.completed,watched:0}}p.watched=Math.min(lesson.duration,p.watched+Math.max(0,Number(body.watched)||0));p.completed=p.completed||p.watched>=lesson.duration*.9?1:0;p.last_seen=Date.now()/1000;demoWrite();return {completed:!!p.completed,watched:p.watched}}
  if(!isTeam)throw Error('Selecciona Administrador o Editor para probar esta acción');
  if(path==='/api/reorder'){if(body.modules)body.modules.forEach((id,position)=>{const m=demoData.modules.find(m=>m.id===id);if(m)m.position=position});if(body.lessons)body.lessons.forEach(row=>{const l=demoData.lessons.find(l=>l.id===row.id);if(l)Object.assign(l,{module_id:row.module_id,position:row.position})});demoWrite();return {ok:true}}
  if(path==='/api/modules'&&method==='POST'){const id=demoId();demoData.modules.push({...body,id,created:Date.now()/1000});demoWrite();return {id}}
  if(/^\/api\/modules\//.test(path)){const id=path.split('/')[3],m=demoData.modules.find(m=>m.id===id);if(!m)throw Error('Módulo no encontrado');if(method==='DELETE'){if(demoData.lessons.some(l=>l.module_id===id))throw Error('El módulo debe estar vacío');demoData.modules=demoData.modules.filter(m=>m.id!==id)}else Object.assign(m,body);demoWrite();return {ok:true}}
  if(path==='/api/lessons'||/^\/api\/lessons\/[^/]+$/.test(path)){const id=path.split('/')[3]||demoId();if(method==='DELETE'){demoData.lessons=demoData.lessons.filter(l=>l.id!==id);demoData.progress=demoData.progress.filter(p=>p.lesson_id!==id)}else{if(body.published&&(body.blocks?.some(b=>b.type==='video')?!body.media_id:!body.blocks?.some(b=>b.text?.trim())))throw Error('En esta demo utiliza las lecciones que ya tienen un video de ejemplo. La grabación y subida real están en la aplicación completa.');let l=demoData.lessons.find(l=>l.id===id);if(!l){l={id,author:user.id,author_name:user.name,created:Date.now()/1000};demoData.lessons.push(l)}Object.assign(l,body,{published:body.published?1:0,blocks:JSON.stringify(body.blocks||[]),captions:JSON.stringify(body.captions||[]),updated:Date.now()/1000})}demoWrite();return {id}}
  if(/^\/api\/users\//.test(path)){if(user.role!=='admin')throw Error('Solo el administrador puede cambiar roles');const u=demoUsers.find(u=>u.id===path.split('/')[3]);if(u)u.role=body.role;return {ok:true}}
  throw Error('Acción no disponible en la demo local');
}
'''.replace('__VIDEO__',json.dumps(data))
studio=(ROOT/'public/studio.js').read_text().replace('export async function mountStudio','async function mountFullStudio')
wrapper='''
async function mountStudio(root,options){const cleanup=await mountFullStudio(root,options);const note=document.createElement('div');note.className='notice';note.textContent='DEMO VISUAL DEL ESTUDIO. Para grabar tu pantalla, cámara y micrófono o probar fondos reales, utiliza la aplicación completa. Esta demo no solicita permisos ni sube archivos.';root.prepend(note);root.querySelector('#prepare-sources').disabled=true;root.querySelector('#camera-background').disabled=true;root.querySelector('#live-captions').disabled=true;return cleanup;}
'''
content=(ROOT/'public/content.js').read_text().replace('export function ','function ')
app=(ROOT/'public/app.js').read_text().replace("import { mountStudio } from './studio.js';",'').replace("import { lessonBlocks, renderLessonBlocks, mountBlockEditor, mountOrganizer } from './content.js';",'')
start=app.index('export async function api(');end=app.index('const team=',start)
app=app[:start]+'async function api(path,options={}){return demoAPI(path,options)}\n'+app[end:]
app=app.replace('export const ','const ').replace('export function ','function ').replace('export async function ','async function ')
app=app.replace('/api/media/${l.media_id}','${demoMediaURL(l.media_id)}').replace('/api/media/${mediaId}','${demoMediaURL(mediaId)}').replace('/api/media/${id}','${demoMediaURL(id)}')
app=app.replace('href="/api/students.csv"','href="${demoCSVURL()}" download="avances-demo.csv"')
suffix='''
const demoSelect=document.querySelector('#demo-role');demoSelect.value=demoRole;
async function demoRefresh(){await session();await refresh();location.hash='academy';await route();document.querySelector('#demo-role').value=demoRole}
demoSelect.onchange=async e=>{demoRole=e.target.value;demoWrite();await demoRefresh();toast('Vista de prueba actualizada. Todos los datos son de ejemplo.')};
document.querySelector('#demo-reset').onclick=async()=>{if(!confirm('¿Restablecer los datos de ejemplo de esta demo?'))return;demoData=structuredClone(demoSeed);demoRole='admin';demoWrite();await demoRefresh();toast('Demo restablecida')};
document.querySelector('#share-button').onclick=()=>toast('Puedes compartir este archivo HTML. No contiene cuentas ni datos reales.');
authModal=()=>toast('No necesitas registrarte en la demo. Elige Estudiante o Administrador en la barra superior. No introduzcas datos reales.');
'''
css=(ROOT/'public/style.css').read_text()+'''
body{padding-top:48px}.sidebar{top:48px}#demo-bar{position:fixed;inset:0 0 auto;z-index:100;height:48px;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:0 22px;background:#412864;color:#fff;font:11px Inter,Arial,sans-serif}#demo-bar strong{font-size:11px}#demo-bar span{opacity:.8}#demo-bar .demo-actions{display:flex;align-items:center;gap:12px}#demo-role{width:145px;padding:5px 8px;border:1px solid #ffffff40;background:#ffffff13;color:#fff;font-size:11px;border-radius:7px}#demo-role option{color:#342941;background:#fff}#demo-reset{color:#fff;font-size:10px;border:1px solid #ffffff40;border-radius:6px;padding:5px 9px}#demo-bar label{margin:0;font-size:10px;font-weight:400}@media(max-width:680px){#demo-bar{padding:0 10px;gap:5px;font-size:8px}#demo-bar strong{font-size:8px}#demo-bar span,#demo-bar label{display:none}#demo-bar .demo-actions{gap:5px}#demo-role{width:115px;font-size:9px}#demo-reset{font-size:8px;padding:5px}}
'''
html=(ROOT/'public/index.html').read_text()
favicon='data:image/svg+xml;base64,'+base64.b64encode((ROOT/'public/favicon.svg').read_bytes()).decode()
html=html.replace('href="/favicon.svg"',f'href="{favicon}"').replace('<link rel="stylesheet" href="/style.css">',f'<style>{css}</style>').replace('<script src="/app.js" type="module"></script>','')
bar='<div id="demo-bar"><div><strong>DEMO LOCAL · AUMENTADOS ACADEMY</strong> <span>— Datos de ejemplo; sin cuentas reales.</span></div><div class="demo-actions"><label for="demo-role">Vista:</label><select id="demo-role" aria-label="Elegir rol de demostración"><option value="admin">Administrador</option><option value="editor">Editor</option><option value="student">Estudiante</option><option value="guest">Visitante</option></select><button id="demo-reset">Reiniciar demo</button></div></div>'
html=html.replace('<body>','<body>'+bar).replace('<title>Aumentados Academy — Aprende sin límites</title>','<title>DEMO · Aumentados Academy</title>')
code=(prefix+studio+wrapper+content+app+suffix).replace('</script','<\\/script')
html=html.replace('</body>',f'<script type="module">{code}</script></body>')
target=ROOT.parent/'Aumentados-Academy-demo.html';target.write_text(html)
(ROOT/'demo.html').write_text(html)
print(f'Demo local generada: {target.name}, {target.stat().st_size/1024:.0f} KB. No utiliza servidor ni modifica la academia real.')

if args.hosted_output:
    hosted=html.replace('DEMO LOCAL · AUMENTADOS ACADEMY','VISTA DE PRUEBA · AUMENTADOS ACADEMY')
    hosted=hosted.replace('— Datos de ejemplo; sin cuentas reales.','— Datos de ejemplo · cambios solo en este navegador.')
    hosted=hosted.replace('DEMO VISUAL DEL ESTUDIO. Para grabar tu pantalla, cámara y micrófono o probar fondos reales, utiliza la aplicación completa. Esta demo no solicita permisos ni sube archivos.','ESTUDIO DE PRUEBA. Puedes grabar y descargar tu video. Los módulos, páginas y avances de esta vista se guardan solo en tu navegador; publicar grabaciones para otros usuarios requiere conectar la aplicación completa.')
    hosted=hosted.replace("root.querySelector('#prepare-sources').disabled=true;root.querySelector('#camera-background').disabled=true;root.querySelector('#live-captions').disabled=true;",'')
    args.hosted_output.parent.mkdir(parents=True,exist_ok=True)
    args.hosted_output.write_text(hosted)
    print('Hosted preview generated:',args.hosted_output)
