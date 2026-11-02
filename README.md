# Aumentados Academy

Aplicación funcional para una academia pública de tutoriales, con espacio privado para el equipo, seguimiento por estudiante y grabador en el navegador. Identidad visual morada, fondos blancos y grises, degradados, esquinas redondeadas y sombras suaves.

**Para revisar la interfaz sin instalar nada:** abre `demo.html`. Usa ejemplos y roles simulados; no es la aplicación completa ni solicita acceso a cámara o micrófono. Consulta [PRUEBAS-SIN-PUBLICAR.md](PRUEBAS-SIN-PUBLICAR.md) para el recorrido y para probar después la grabación real.

## Ejecutar

Requiere Python 3.12 o superior. El servidor no requiere instalar paquetes.

```bash
cd /workspace/aumentados-academy
python3 scripts/prepare-assets.py
python3 server.py
```

En Windows también puedes abrir `iniciar.bat`; en Linux o macOS, ejecuta `./iniciar.sh`. Ambos intentan abrir el navegador automáticamente.

Abre **http://localhost:8000** en el mismo equipo donde ejecutas el servidor. En un servidor remoto, `localhost` se refiere al servidor: utiliza tu dominio HTTPS o un túnel de puertos autorizado. El enlace local de esta entrega no es una publicación en Internet.

1. Abre la cuenta de la esquina superior derecha.
2. Selecciona **Configurar primer administrador**.
3. Introduce tu nombre, correo y una contraseña de al menos 12 caracteres.
4. Introduce el código privado del archivo `.runtime/setup-code.txt`. No lo compartas con estudiantes. Se elimina después de configurar al administrador.
5. Crea módulos desde **Contenido**; agrega videos o grábalos en **Estudio de grabación**.
6. Publica las lecciones que quieras mostrar en la academia.

No hay usuarios, contraseñas, estudiantes ni videos de ejemplo en los datos de la aplicación. Las capturas de `test-results` se generaron con una base de datos temporal de pruebas.

## Lo que funciona

- **Navegación de clases:** tarjetas o lista desplegable, índice móvil con botón explícito, clase anterior/siguiente y organización dentro de cada módulo.
- **Academia pública:** módulos, búsqueda por título, descripción y etiquetas, reproducción de videos, instrucciones, enlaces y transcripción navegable. Los visitantes no pueden editar ni eliminar contenido.
- **Estudiante:** registro, inicio y cierre de sesión, reanudación de lecciones, avance por módulo, lecciones completadas y preguntas por lección. La identidad es necesaria para guardar el progreso entre dispositivos; consultar videos no requiere una cuenta.
- **Editor:** crear, editar, ordenar y eliminar módulos y lecciones, subir videos, publicar borradores y consultar avances. El organizador permite arrastrar módulos, ordenar lecciones y moverlas entre módulos; también ofrece flechas y un selector como alternativa al arrastre.
- **Administrador:** permisos del editor y gestión de roles. Las personas se registran como estudiantes; un administrador puede convertirlas en editores desde **Estudiantes**. No hay un selector que conceda permisos desde la interfaz.
- **Seguimiento:** tiempo reproducido, última actividad, estado por lección, avance global, detalle de cada persona y exportación CSV. Las lecciones se completan al acreditar al menos el 90% de su duración de reproducción. Adelantar el video por sí solo no acredita tiempo. Es un indicador de reproducción, no una certificación de atención o conocimiento.
- **Videos:** subida en bloques de 8 MB, hasta 2 GB por archivo; reproducción HTTP con rangos; MP4, WebM, MOV y OGV cuando el navegador soporte sus códecs.
- **Grabador:** pantalla, cámara o ambas; elección de cámara y micrófono; mezcla con audio de la pantalla cuando el navegador lo ofrece; cámara flotante circular, cuadrada o redondeada; tamaño ajustable; lápiz, flechas, marcadores numerados, colores, deshacer y borrar; pausa, reanudación, descarga y guardado como lección. Al salir del estudio con una grabación sin guardar, solicita confirmación y permite quedarse sin perderla.
- **Fondos virtuales:** recorte de persona con MediaPipe ejecutado en el dispositivo, desenfoque, estudio morado, imagen, GIF animado o video en bucle. Los archivos del modelo y WebAssembly se sirven desde esta aplicación, sin una CDN en tiempo de ejecución.
- **Subtítulos:** importación y edición de WebVTT/SRT; pistas de subtítulos y transcripción que permite saltar a cada fragmento. Transcripción durante la grabación opcional cuando el navegador ofrece Web Speech.
- **Páginas por bloques:** texto, títulos, listas de pasos, notas destacadas, separadores y un bloque de video por lección. Se pueden reordenar con arrastre o flechas. Las lecciones pueden ser solo escritas y publicarse sin video; los estudiantes las marcan como leídas. El editor conserva los textos al ir al estudio y regresar con una grabación.
- **Recorte de reproducción:** inicio/final por lección. Conserva el video original; no genera un nuevo archivo recortado.

## Compatibilidad y límites concretos

- La cámara, el micrófono y la captura de pantalla requieren **HTTPS o localhost** y permiso explícito del navegador. La configuración recomendada para grabar es Chrome o Edge actualizados en escritorio.
- La captura de pantalla y el audio del sistema dependen del navegador y sistema operativo. En móviles, la grabación de pantalla suele no estar disponible; la academia y el reproductor sí tienen diseño adaptable.
- Las anotaciones se dibujan sobre la vista previa de la aplicación y se integran al video. Una aplicación web no puede superponer herramientas sobre cualquier aplicación del escritorio ni detectar todos sus clics fuera de la página. Para eso se necesita una extensión o aplicación de escritorio adicional.
- Los fondos requieren capacidad de CPU y una buena iluminación. La reproducción de GIF usa `ImageDecoder`; si el navegador no lo soporta, utiliza un video MP4 en bucle. Un fondo personalizado admite hasta 50 MB.
- La grabación se acumula en memoria y se limita a aproximadamente 1 GB. Conviene crear cápsulas breves y descargarlas antes de salir. No hay recuperación de una grabación después de cerrar la pestaña sin guardarla.
- La transcripción durante la grabación es opcional y depende de Web Speech; el proveedor del navegador puede procesar audio remotamente. Está desactivada por defecto y requiere revisar el texto. **No hay transcripción automática de videos ya subidos, ni un servicio de IA configurado.** Puedes importar subtítulos manuales.
- No se incluyen emisión automática de certificados, evaluaciones, envío de correos, recuperación de contraseña por correo, inicio con Google, analítica de presencia en tiempo real ni streaming adaptativo/transcodificación de videos. No se ha integrado un proveedor de correo o video de pago.
- El servidor usa SQLite y almacenamiento de archivos local. Esta entrega es una primera versión funcional para evaluación y despliegue controlado; necesita pruebas con usuarios y dispositivos reales, copias de seguridad y dimensionamiento antes de una apertura masiva.

## Despliegue con dominio y HTTPS

El proyecto incluye un contenedor y un proxy Caddy con HTTPS automático. Requiere un servidor con Docker Compose, un dominio que apunte a ese servidor y puertos 80/443 disponibles.

```bash
export ACADEMY_DOMAIN=academia.tudominio.com
docker compose up -d --build
docker compose exec academy cat /data/setup-code.txt
```

Visita `https://academia.tudominio.com`, configura al administrador con ese código y comparte `https://academia.tudominio.com/#academy` con tus estudiantes. El código solo existe antes de la primera configuración. El certificado requiere que el dominio y la conectividad del servidor estén correctamente configurados.

**Estado de la entrega:** la [vista de prueba](https://aumentados-academy-prueba.teamaumenta2.chatgpt.site) está publicada con ejemplos y cambios guardados solo en el navegador. La aplicación completa con almacenamiento y usuarios compartidos todavía no está desplegada. Se construyó y probó la imagen Docker, incluido arranque sin root, almacenamiento persistente y recreación del contenedor conservando datos. La configuración de Compose y Caddy se validó localmente. El certificado público y la conectividad deben verificarse en el servidor de destino con el dominio definitivo. La aplicación usa su propia autenticación; no depende de ChatGPT para que los estudiantes se registren.

## Datos y operación

- Base de datos: `.runtime/academy.sqlite`.
- Videos: `.runtime/media/`.
- Sesiones con cookies HttpOnly, SameSite y CSRF. En HTTPS activa `ACADEMY_SECURE_COOKIES=1`; Compose ya lo hace.
- Contraseñas: PBKDF2-HMAC-SHA256, 600.000 iteraciones y sal individual.
- Los permisos y la visibilidad de borradores se comprueban en el servidor. El acceso a los archivos originales de un video publicado es público; no hay DRM ni prevención de descargas.
- Copia de seguridad consistente, incluso con el servidor activo: `python3 maintenance.py backup .runtime/backups/academia.tar`. Incluye una instantánea de SQLite y los videos terminados; verifica la integridad y no sobrescribe archivos existentes. Las sesiones y subidas incompletas se excluyen de la copia. Los usuarios deberán iniciar sesión otra vez si se restaura. El archivo se crea con permisos privados; guárdalo también fuera del servidor. No copies solo el archivo `.sqlite` mientras está escribiendo, porque puede perder cambios del WAL.
- Los videos eliminados y las subidas abandonadas se conservan en almacenamiento en esta versión. Programa una política de retención y limpieza antes de acumular grandes volúmenes. El límite total predeterminado es 20 GB.
- Guarda la carpeta de datos fuera del directorio público. No subas `.runtime` al repositorio ni la incluyas en archivos de distribución.

Variables disponibles:

| Variable | Uso |
| --- | --- |
| `ACADEMY_DATA_DIR` | Carpeta persistente de datos; por defecto `.runtime` junto al servidor. |
| `ACADEMY_SECURE_COOKIES` | `1` cuando se sirve mediante HTTPS. |
| `ACADEMY_TRUST_PROXY` | `1` solo cuando el servidor es accesible exclusivamente mediante un proxy de confianza. Compose lo activa con Caddy; evita aplicar el límite de acceso a todos los estudiantes como si fueran una sola IP. |
| `ACADEMY_STORAGE_LIMIT` | Límite total de videos en bytes; por defecto 20 GB. |

## Copias en Docker y restauración

```bash
docker compose exec academy python3 maintenance.py backup /data/backups/academia.tar
docker compose cp academy:/data/backups/academia.tar ./academia.tar
```

Ese archivo contiene datos privados de los estudiantes y contraseñas cifradas mediante hash; mantenlo fuera del directorio público y no lo compartas. Guarda otra copia en un almacenamiento privado independiente del servidor.

Para restaurar, detén la academia, respalda primero la carpeta actual y extrae una copia confiable en una carpeta de datos vacía. Contiene `academy.sqlite`, `media/` y `backup-info.json`. No mezcles el SQLite restaurado con archivos WAL/SHM de otra base. Configura `ACADEMY_DATA_DIR` con esa carpeta, asegura que el usuario del servicio pueda leerla y escribir en ella, y arranca la aplicación. La administración y el contenido se conservan; las sesiones se vuelven a crear al iniciar sesión. No restaures mientras el servidor esté utilizando la base.

## Validación

```bash
python3 -m unittest discover -s tests -v
node --check public/app.js
node --check public/studio.js
```

`tests/browser.cjs` verifica los flujos completos con Playwright, Chromium y FFmpeg ya instalados. Usa una base temporal y no modifica los datos de la academia:

```bash
node tests/browser.cjs
```

Se aprobaron **18 pruebas de integración**, el recorrido de navegador y la prueba de despliegue Docker con conservación de datos al recrear el contenedor.

La prueba de despliegue crea recursos Docker temporales y los elimina al finalizar:

```bash
python3 tests/deployment.py
```

`/api/health` permite comprobar la disponibilidad de la aplicación y su base de datos sin exponer información de usuarios. Docker utiliza ese endpoint para su comprobación de salud.

La prueba del grabador utiliza cámara/micrófono simulados y una pantalla generada para pruebas. No certifica permisos de pantalla, calidad de cámara, audio real o rendimiento en todos los dispositivos.

## Archivos principales

- `server.py`: API HTTP, autenticación, permisos, SQLite y videos.
- `maintenance.py`: copias privadas y consistentes de datos y videos.
- `public/app.js`: academia, contenido, estudiantes y edición de lecciones.
- `public/content.js`: organizador de módulos y lecciones, editor por bloques y vista de lectura.
- `public/studio.js`: grabador, composición, fondos y anotaciones.
- `public/style.css`: diseño adaptable de Aumentados Academy.
- `public/vendor/`: MediaPipe, WebAssembly y modelo de segmentación.
- `tests/`: pruebas de permisos, datos y flujos de usuario.

Consulta `THIRD_PARTY.md` para las dependencias distribuidas.

## Optimizaciones verificadas

- Los archivos estáticos se revalidan con ETag: una respuesta 304 evita retransmitir JavaScript, modelos y WebAssembly sin cambios. Los videos siguen comprobando permisos y usan `private, no-store`.
- Seis índices adicionales cubren orden por módulo, visibilidad de videos, comentarios, relaciones de progreso y sesiones. Se crean de forma idempotente al arrancar, también en bases existentes.
- El cálculo de progreso y las reservas de almacenamiento utilizan transacciones de escritura para evitar conflictos concurrentes. Las subidas rechazan tamaños fraccionarios y tipos MIME inválidos.
- El fondo virtual reutiliza ImageData y el canvas de la máscara en lugar de recrearlos en cada segmentación. Solo se actualiza el canal alfa de cada píxel.
- Generación reproducible de las dos demos: `python3 scripts/create-demo.py --hosted-output /ruta/del/sitio/dist/index.html`. La demo local desactiva dispositivos; la versión HTTPS permite grabar y descargar. Ambas mantienen datos de ejemplo locales al navegador.

Las 18 pruebas del servidor incluyen revalidación HTTP, mantenimiento de privacidad con caché y progresos concurrentes. El recorrido de navegador comprueba el grabador con dispositivos simulados, fondos y archivo final de audio/video. Estas verificaciones no son una prueba de carga ni una medición de rendimiento en cámaras físicas.

Los dos archivos WebAssembly grandes se preparan con `python3 scripts/prepare-assets.py`. El instalador comprueba SHA-256 y reutiliza archivos válidos. Se requiere acceso a Internet durante esa preparación; la aplicación los sirve localmente al ejecutarse.
