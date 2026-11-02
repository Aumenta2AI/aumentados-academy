# Publicación en Vercel

Estado: repositorio privado creado en https://github.com/Aumenta2AI/aumentados-academy. Conexión con Vercel pendiente de autorización; aún no se ha creado el proyecto de Vercel.

## Arquitectura

La aplicación completa usa Python HTTPServer, SQLite y archivos persistentes. No se debe desplegar este servidor sin cambios como una función de Vercel: el disco no es persistente y las subidas por bloques requieren almacenamiento compartido.

El frontend puede alojarse en Vercel. Para la aplicación compartida necesita una API persistente y almacenamiento de videos; las rutas `/api/*` deben apuntar a esa API. La API existente se puede ejecutar con Docker en un servidor con volumen persistente y HTTPS. Otra opción requiere migrar base de datos y videos a servicios externos.

La demo estática es una vista de prueba con datos guardados en el navegador. Publicarla en Vercel no equivale a publicar la aplicación completa.

## Seguimiento

- Nombre previsto del repositorio: `aumentados-academy`, privado.
- Cuenta de GitHub identificada mediante el conector: `Aumenta2AI`.
- Nombre previsto del proyecto de Vercel: `aumentados-academy`.
- Rama inicial: `main`.
- Versión inicial del código: `0.1.0`.
- Conservar secretos y datos de estudiantes fuera de Git.

Después de conectar las cuentas, verificar el propietario autenticado y la disponibilidad del nombre antes de crear recursos. Registrar aquí las URLs y el commit publicado cuando el despliegue esté verificado.
