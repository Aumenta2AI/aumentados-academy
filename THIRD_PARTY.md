# Componentes de terceros

- **MediaPipe Tasks Vision**, Google LLC, versión `0.10.22-rc.20250304`. Licencia Apache 2.0. Se distribuyen el paquete JavaScript `vision_bundle.mjs` y los runtimes WebAssembly SIMD/no SIMD desde el paquete oficial `@mediapipe/tasks-vision`.
- **MediaPipe Selfie Segmenter Landscape**, modelo float16. Archivo oficial de Google: `https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite`. Se usa para segmentación local de personas.

Los avisos de copyright incluidos en los archivos JavaScript se conservan. Se incluye el texto de Apache 2.0 en `public/vendor/LICENSE-Apache-2.0.txt`. El README oficial del paquete está en `public/vendor/README-mediapipe.md`.

No se cargan fuentes, bibliotecas ni modelos desde una CDN cuando se abre la aplicación. El reconocimiento de voz opcional pertenece al navegador y tiene su propio proveedor y condiciones.

Python, Chromium, FFmpeg y Playwright son herramientas del entorno de ejecución o pruebas; sus binarios no se incluyen en esta distribución.
