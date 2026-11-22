# Arquitectura de Vanysha AI

```
 Navegador (frontend/index.html)                     Servidor (backend/app)
┌──────────────────────────────────┐   HTTPS/REST   ┌──────────────────────────────────────┐
│ Dashboard · Cámara · Análisis    │ ─────────────► │ FastAPI                              │
│ Alertas · Historial · Asistente  │                │  ├─ auth (JWT + PBKDF2) y roles       │
│ Modelos · Reglas · Auditoría     │ ◄───────────── │  ├─ usuarios, alertas, análisis, CSV  │
│ Usuarios · Ajustes               │   WebSocket    │  ├─ reglas (rules.py)                 │
│                                  │ ─ fotogramas ► │  ├─ detector (detector.py)            │
│ getUserMedia → JPEG 640 px       │ ◄─ detecciones │  │    YOLO  →  HOG  →  DEMO           │
└──────────────────────────────────┘ ◄─ alertas ─── │  └─ SQLite (data/vanysha.db) + evidencia│
                                                    └──────────────────────────────────────┘
```

## Flujo de la cámara en vivo
1. El navegador abre la cámara (`getUserMedia`) y dibuja las cajas encima del video.
2. Cada ~100 ms envía al servidor un fotograma JPEG y la zona restringida dibujada por el usuario (`/ws/detect`).
3. El servidor ejecuta el detector, devuelve las detecciones y evalúa las reglas.
4. Si una regla se cumple (por ejemplo, una persona 0,6 s dentro de la zona), guarda el análisis y la alerta en la base de datos, guarda la foto de evidencia y avisa a todos los navegadores conectados (`/ws/events`).

## Adaptador DEMO → REAL
`detector.py` define una interfaz única (`detect(frame)`). Cambiar de motor no toca la interfaz ni las reglas:

| Motor | Qué detecta | Requiere |
|---|---|---|
| `yolo` | 80 clases COCO; con modelo propio: cascos, chalecos, defectos | `pip install ultralytics` (+ PyTorch) |
| `hog`  | Personas | Solo OpenCV 4.x. Sin descargas |
| `demo` | Nada en video real; resultados de ejemplo en imágenes | Nada |

`auto` prueba `yolo`, luego `hog`, luego `demo`.

## Modelo de datos (SQLite)
`users` · `analyses` · `alerts` · `rules` · `audit` · `meta` (contadores). Las funciones de `db.py` son las únicas que tocan SQL, así que migrar a PostgreSQL implica cambiar solo ese archivo.
