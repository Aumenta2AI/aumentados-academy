# Cómo revisar Aumentados Academy antes de publicarla

## 1. Recorrido sin instalar nada

Abre **demo.html** con doble clic en Chrome o Edge. También se entrega por separado como **Aumentados-Academy-demo.html**. No necesitas dominio, cuenta de alojamiento, repositorio, Python ni Docker.

Esta demo usa datos de ejemplo y un video breve que dice “VIDEO DE EJEMPLO”. No crea cuentas reales ni conecta con la base de datos de la academia. No escribas información personal ni contraseñas reales en ella.

Prueba este recorrido de cinco minutos:

1. En la barra superior, elige **Administrador**. Explora los módulos y abre **Contenido**.
2. En **Contenido**, arrastra los seis puntos de un módulo para cambiar su posición; también puedes usar las flechas. Mueve una lección a otro módulo con el arrastre o con su selector.
3. Edita una lección: agrega bloques de texto, títulos, listas, notas o video y ordénalos con arrastre o flechas. **Solo lectura** permite publicar una página sin video.
4. Cambia a **Estudiante**. Abre una lección y deja reproducir los cinco segundos del video de ejemplo. Revisa **Mi aprendizaje** para comprobar que se marcó como completada.
5. Regresa a **Administrador** y abre **Estudiantes**. Consulta el avance del estudiante de prueba.
6. Cambia a **Visitante** y revisa que solo aparezca el contenido público, sin el menú del equipo.
7. Abre **Estudio de grabación** como administrador para revisar su distribución y controles. La captura real está desactivada en esta demo.

**Reiniciar demo** restablece todos los ejemplos. Los cambios de prueba se guardan únicamente en este navegador cuando permite almacenamiento local; no se sincronizan ni cambian la academia real. Algunos navegadores restringen el almacenamiento al abrir archivos locales.

La demo es un archivo HTML con estilos, código y video integrados. La prueba automatizada se realizó sirviendo ese único archivo localmente, sin utilizar la API de la academia ni dependencias remotas. El navegador administrado del entorno bloquea la navegación `file://`, por lo que no se verificó aquí el doble clic sobre el archivo. Si tu navegador también impide abrir HTML local, utiliza la aplicación completa del siguiente apartado.

## 2. Prueba funcional de la aplicación completa

Para probar tu cámara y micrófono, grabar, subir archivos y verificar cuentas reales:

1. Descomprime el proyecto completo.
2. Instala Python 3.12 o superior, si no lo tienes.
3. En Windows, abre **iniciar.bat**. En Linux o macOS, ejecuta `./iniciar.sh` desde la carpeta del proyecto.
4. Visita **http://localhost:8000** en el mismo equipo.
5. Abre la cuenta de la esquina superior derecha y selecciona **Configurar primer administrador**.
6. Crea tu administrador utilizando el código privado de **.runtime/setup-code.txt**. Ese archivo aparece al iniciar por primera vez.
7. Crea un módulo y usa **Estudio de grabación**. Descarga la grabación o guárdala como lección.
8. Para probar el rol de estudiante a la vez, abre una ventana de incógnito, visita el mismo enlace y crea una cuenta de estudiante.

En esta modalidad los datos sí se guardan en la carpeta **.runtime** del equipo. Son datos locales de prueba; todavía no existe un enlace público. Mantén abierta la ventana del servidor mientras utilices la aplicación.

Elige Chrome o Edge actualizados en escritorio para las primeras pruebas de grabación. Cuando el navegador solicite permisos de cámara, micrófono o pantalla, concédelos solo si deseas iniciar esa prueba.

## 3. Qué revisar y comentar

- Colores, tamaños de texto y claridad de los menús.
- Organización de módulos, lecciones y búsqueda.
- Diferencias entre las vistas de equipo y estudiante.
- Reproductor, preguntas y visualización del progreso.
- Facilidad para grabar, mover la cámara y señalar pasos, en la aplicación completa.

Con tus comentarios podemos ajustar la experiencia. Después trasladaremos el código a un repositorio y elegiremos el alojamiento; ninguna de esas dos cosas es necesaria para este recorrido de pruebas.
