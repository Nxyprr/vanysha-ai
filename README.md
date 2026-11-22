# Vanysha AI

Plataforma de visión artificial para **seguridad industrial, almacén inteligente, control de calidad y retail**.
Incluye frontend (interfaz web), backend (API en Python), base de datos, autenticación con roles, alertas con sonido y **detección real con cámara**.

> Estado: prototipo funcional. Lee la sección **"Qué es real y qué es simulado"** antes de presentarlo.

---

## 1. Inicio rápido (un solo doble clic)

1. Descomprime el ZIP (clic derecho > *Extraer todo*).
2. Haz **doble clic** en el lanzador de tu sistema:

| Sistema | Archivo |
|---|---|
| Windows | `INICIAR_WINDOWS.bat` |
| Mac | `INICIAR_MAC_LINUX.command` (si Mac lo bloquea: clic derecho > *Abrir*) |
| Linux | `bash INICIAR_MAC_LINUX.command` en la terminal |

El lanzador (`start.py`) hace todo solo:
- Si no tienes Python, en Windows intenta instalarlo con `winget`; si no puede, abre la página de descarga.
- Crea el entorno e instala las librerías. **La primera vez tarda unos minutos y necesita internet**; después enciende en segundos.
- Busca un puerto libre (8000, o el siguiente si está ocupado), enciende el servidor y abre el navegador cuando está listo.

Entra con:

| Correo | Contraseña |
|---|---|
| `admin@vanysha.ai` | `Vanysha2026` |

Cambia esa contraseña antes de mostrar el proyecto a otras personas (ver sección 6).
**Para apagarlo**, cierra la ventana negra (o `Ctrl + C`).

**Solo quiero ver la demo, sin instalar nada:** doble clic en `frontend/index.html`. Funciona sin servidor, con datos de ejemplo.

Opciones del lanzador (desde la terminal): `python start.py --yolo` instala también YOLO, `--port 9000` cambia el puerto y `--no-browser` no abre el navegador.

La documentación interactiva de la API queda en `http://localhost:8000/docs`.

---

## 2. Cómo probar la cámara real

1. Entra a **Cámara en vivo** en el menú.
2. Pulsa **Activar cámara** y acepta el permiso del navegador. (La cámara solo funciona en `localhost` o con HTTPS.)
3. Pulsa **Dibujar zona** y arrastra un rectángulo sobre el video.
4. Entra a la zona con una persona: tras unos 0,6 segundos suena la alerta, aparece la notificación, se guarda la foto de evidencia y la alerta aparece en **Alertas**, **Historial** y **Auditoría**.

El motor activo se ve en la etiqueta superior del video:

| Etiqueta | Significado |
|---|---|
| `IA real · YOLO (...)` | El servidor usa YOLO |
| `IA real · OpenCV HOG (personas)` | El servidor detecta personas sin descargar modelos |
| `Sin IA · solo movimiento` | No hay motor de IA disponible; solo se detecta movimiento y el contador de personas muestra "—" |

### Para qué sirve "Dibujar zona" y qué se detecta

**Dibujar zona** marca en el video un área prohibida o de riesgo (una puerta, una máquina, un almacén). Se arrastra un rectángulo sobre la imagen. Si una **persona** permanece dentro unos segundos, el sistema genera una alerta de severidad Alta: suena el aviso, aparece la notificación, se guarda una foto de evidencia y queda registrada en Alertas, Historial y Auditoría. Si lo que entra es solo **movimiento** sin una persona confirmada, la alerta es de severidad Media.

Qué dibuja la cámara:

| Color | Qué es |
|---|---|
| Blanco | Persona o rostro confirmado (se cuenta y se sigue con un número) |
| Rosa | Objeto reconocido (celular, botella, laptop, silla...). **Solo con IA** |
| Gris punteado | Movimiento. Si la figura es alta y angosta se rotula "posible persona" |
| Rojo vino | Algo dentro de la zona restringida (alerta) |

### Qué detecta la cámara y dónde funciona la IA

La detección de **personas** es real, con un modelo de IA, en dos lugares:

| Dónde | Motor | Requisito |
|---|---|---|
| **Con el servidor** (zip, `INICIAR_...`) | YOLO u OpenCV HOG en tu computadora | Ninguno extra (HOG) o `--yolo` |
| **Archivo suelto** `Vanysha_AI.html` o `frontend/index.html` | COCO-SSD (TensorFlow.js) en el navegador | **Internet**, la primera vez, para descargar el modelo (~5 MB) |

Mientras el modelo carga, **y si no se puede descargar**, la cámara detecta **rostros al instante, aunque estés quieto**, con un detector que viaja dentro de la propia página (no necesita internet) y que además detecta movimiento. Con eso se cuentan personas, se registran sus entradas y salidas y funciona la alerta de zona restringida. Lo que ese modo **no** ve son personas de cuerpo completo caminando de espaldas, de perfil o lejos: para eso hace falta la IA (COCO-SSD o el servidor). El panel lo avisa y ofrece **Reintentar IA**.

El detector de rostros revisa el cuadro derecho y con una leve inclinación (±10°), y mantiene la caja unos instantes si pierde la cara un cuadro, para que no parpadee. En pruebas con imágenes simuladas acierta cerca de 86–94% con rostros de frente, buena luz y tamaño normal, y baja con rostros muy pequeños, muy girados o sobreexpuestos.

En movimiento, las figuras altas y angostas se marcan como **posible persona** (no se cuentan como personas confirmadas) y el resto como **movimiento**.

**La página publicada en un enlace (vista incrustada) no puede descargar el modelo**: esos entornos bloquean las conexiones externas. Para detección real úsala desde el archivo suelto o con el servidor.

El panel muestra personas en escena, el máximo, eventos de entrada y salida con el tiempo que estuvo cada persona, alerta de zona restringida y fotos de evidencia.

### Activar YOLO (recomendado)

```bash
pip install -r backend/requirements-yolo.txt
```

La primera ejecución descarga `yolov8n.pt` (necesita internet). Con GPU NVIDIA instala antes PyTorch con CUDA (https://pytorch.org/get-started/locally/).
Elige el motor con la variable `VANYSHA_DETECTOR` (`auto`, `yolo`, `hog`, `demo`). Por defecto `auto`.

### Detectar cascos, chalecos y defectos (modelo propio)

Un modelo genérico no reconoce cascos ni chalecos. Hay que entrenar uno con imágenes etiquetadas de **tus propios entornos**
(por ejemplo con YOLO y un conjunto de datos de EPP) y apuntar el servidor a él:

```
VANYSHA_DETECTOR=yolo
VANYSHA_MODEL=C:\modelos\epp.pt
```

El motor de reglas reconoce estas clases: `no_helmet`, `no-hardhat`, `no_vest`, `no-safety-vest`, `sin_casco`, `sin_chaleco` (regla **EPP incompleto**)
y `defect`, `defecto`, `crack`, `scratch` (regla **Producto no conforme**). Se pueden ampliar en `backend/app/rules.py`.

---

## 3. Qué incluye

```
vanysha-ai/
├─ frontend/index.html        Interfaz completa (un solo archivo, sin instalación)
├─ backend/
│  ├─ app/
│  │  ├─ main.py              API REST + WebSockets (FastAPI)
│  │  ├─ detector.py          Motores YOLO / HOG / DEMO
│  │  ├─ rules.py             Motor de reglas (zona restringida, EPP, defectos, aforo)
│  │  ├─ db.py                Base de datos SQLite
│  │  ├─ security.py          Contraseñas (PBKDF2) y tokens (JWT)
│  │  └─ config.py            Configuración por variables de entorno
│  ├─ tests/                  Pruebas automáticas
│  ├─ requirements*.txt       Dependencias
│  └─ .env.example            Variables de configuración
├─ docs/ARQUITECTURA.md       Diagrama y flujo
├─ Dockerfile · docker-compose.yml
├─ start.py                   Lanzador: instala, enciende y abre el navegador
└─ INICIAR_WINDOWS.bat · INICIAR_MAC_LINUX.command · LEEME_PRIMERO.txt
```

**Interfaz:** Dashboard, Cámara en vivo, Análisis visual, Alertas, Historial (con CSV), Asistente IA, Modelos, Reglas, Auditoría, Usuarios y Ajustes. Login con administradora, sonidos y notificaciones de alerta. **El sonido y las alertas en vivo se activan en cada inicio de sesión** y suenan en cualquier sección del menú (el navegador exige un clic previo para permitir audio; el clic de "Ingresar" ya lo cumple).

**Sin backend:** si abres `frontend/index.html` directamente (doble clic), funciona en **modo DEMO local**: los datos viven en el navegador y la cámara usa COCO-SSD (necesita internet) o detección de movimiento. Con el backend, todo se guarda en el servidor. Al crear la base de datos por primera vez se cargan los mismos datos de ejemplo (12 análisis y 5 alertas); para empezar vacío define `VANYSHA_DEMO_DATA=0`.

---

## 4. Roles y permisos

| Rol | Ve | Puede hacer |
|---|---|---|
| **Administración** | Todo | Todo, incluida la gestión de cuentas |
| **Supervisión** | Todo menos Usuarios | Revisar y cerrar alertas, activar o desactivar reglas |
| **Operación** | Dashboard, Cámara, Análisis, Alertas, Historial, Asistente | Revisar alertas, analizar |
| **Auditoría** | Dashboard, Alertas, Historial, Modelos, Auditoría | Solo lectura (el servidor rechaza cambios) |

La interfaz oculta las secciones y el **servidor aplica los permisos**: un rol sin permiso recibe `403` aunque llame a la API a mano.

---

## 5. API (resumen)

Todas las rutas, salvo `/api/health` y `/api/auth/login`, requieren `Authorization: Bearer <token>`.

| Método y ruta | Rol | Descripción |
|---|---|---|
| `GET /api/health` | público | Estado, modo (REAL/DEMO) y detector activo |
| `POST /api/auth/login` | público | Devuelve token y usuario. Bloquea tras 5 intentos fallidos |
| `GET /api/auth/me` | cualquiera | Usuario actual |
| `POST /api/auth/password` | cualquiera | Cambiar la propia contraseña (`old`, `new`) |
| `GET/POST /api/users`, `DELETE /api/users/{id}` | admin | Gestión de cuentas |
| `GET /api/alerts`, `PATCH /api/alerts/{id}` | lectura: todos · cambios: admin, supervisor, operador | Alertas, estado y notas |
| `GET /api/alerts/{id}/evidence` | cualquiera | Foto de evidencia (acepta `?token=`) |
| `GET /api/analyses`, `POST /api/analyses`, `GET /api/analyses.csv` | lectura: todos · alta: admin, supervisor, operador | Historial y exportación |
| `POST /api/analyze/image` | admin, supervisor, operador | Analiza una imagen subida con el detector activo |
| `GET /api/rules`, `PATCH /api/rules/{código}` | lectura: todos · cambios: admin, supervisor | Reglas activas |
| `GET /api/audit` | admin, supervisor, auditor | Registro de auditoría |
| `GET /api/stats` | cualquiera | Totales |
| `WS /ws/detect?token=` | admin, supervisor, operador | Fotogramas → detecciones y alertas |
| `WS /ws/events?token=` | cualquiera | Alertas en tiempo real |

Ejemplo (analizar una imagen):

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@vanysha.ai","password":"Vanysha2026"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -X POST "localhost:8000/api/analyze/image?scenario=alm" -H "Authorization: Bearer $TOKEN" -F "file=@foto.jpg"
```

---

## Agregar usuarios

**Desde la interfaz (lo más fácil):** entra como administradora, abre **Usuarios** en el menú, completa nombre, correo, cargo, rol y una contraseña temporal (mínimo 8 caracteres) y pulsa **Crear cuenta**. Esa persona ya puede entrar con su correo.

**Desde la terminal** (útil si olvidaste la contraseña de la administradora). Con el entorno activado, dentro de `backend/`:

```bash
python -m app.cli list-users                          # ver las cuentas
python -m app.cli add-user                            # crear una cuenta (pregunta los datos)
python -m app.cli set-password --email admin@vanysha.ai   # cambiar una contraseña
```

---

## Publicar en un link

| Opción | Para qué sirve | Cómo |
|---|---|---|
| **Demostración (ya publicada)** | Mostrar el diseño a cualquiera, sin servidor. Alertas con sonido, cuentas y datos de ejemplo; todo se guarda solo en el navegador de cada visitante. | Usa el enlace de la página publicada. La cámara real con IA del servidor no está disponible ahí. |
| **Link temporal desde tu computadora** | Que otra persona (o tu celular) use el sistema completo mientras tu PC esté encendida. | Con el sistema encendido, instala Cloudflare Tunnel (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) y ejecuta `cloudflared tunnel --url http://localhost:8000`. Te da un link `https://...trycloudflare.com` con HTTPS. **Antes cambia la contraseña de la administradora**: cualquiera con el link vería la pantalla de login. |
| **Link permanente en la nube** | Sistema completo siempre disponible. | Sube esta carpeta a GitHub y en https://render.com elige *New > Blueprint* con este repositorio (usa `render.yaml`). En el panel define `VANYSHA_ADMIN_PASSWORD`. El plan gratuito se apaga por inactividad y **no guarda datos entre reinicios**; para conservarlos hace falta un disco de pago o migrar a PostgreSQL. |

---

## 6. Configuración y seguridad

Copia `backend/.env.example` a `backend/.env` y ajusta. Lo más importante:

- `VANYSHA_ADMIN_PASSWORD`: la contraseña inicial de la administradora (solo se usa cuando la base de datos está vacía).
- `VANYSHA_SECRET`: clave para firmar sesiones. Si no la defines se genera una y se guarda en `backend/data/.secret`.
- Para cambiar la contraseña desde la API: `POST /api/auth/password` con `{"old":"...","new":"..."}`.

**Antes de usarlo con datos reales** (esto es un prototipo, no un producto terminado):

1. Servirlo detrás de **HTTPS** (por ejemplo con Caddy o Nginx). Sin HTTPS, las contraseñas y el video viajan sin cifrar fuera de `localhost`.
2. Cambiar la contraseña por defecto y definir `VANYSHA_SECRET`.
3. Migrar de SQLite a **PostgreSQL** si habrá varios servidores o mucho volumen (solo cambia `db.py`).
4. Añadir copias de seguridad de `backend/data/` y una política de retención de las fotos de evidencia.
5. **Privacidad:** el video y las evidencias pueden contener rostros. Revisa la Ley 29733 de protección de datos personales (Perú), coloca avisos de videovigilancia y define quién accede a las evidencias. Consúltalo con un especialista legal.
6. **Licencias:** `ultralytics` (YOLO) se publica bajo AGPL-3.0; para uso comercial cerrado necesitas su licencia empresarial o un modelo con licencia permisiva. COCO-SSD y OpenCV usan licencias permisivas.

---

## 7. Qué es real y qué es simulado

**Real**
- Login, roles, cuentas, alertas, historial, reglas y auditoría guardados en la base de datos y protegidos por el servidor.
- Cámara en vivo: el video de tu cámara se analiza en el servidor (YOLO u OpenCV HOG), con seguimiento, zona restringida, alerta con sonido, evidencia y aviso en tiempo real a todos los navegadores conectados.
- Análisis de imágenes subidas por API (`/api/analyze/image`).

**Simulado (modo DEMO)**
- Las cuatro cámaras animadas del Dashboard y la sección **Análisis visual**: son escenas dibujadas para mostrar cómo se vería el producto. Sus resultados son fijos.
- El **Asistente IA** responde con reglas simples sobre los datos, no es un modelo de lenguaje.
- La sección **Modelos** muestra métricas de ejemplo.

**Pendiente para llegar a producción** (fases finales del informe de arquitectura)
- Modelo propio entrenado y validado con imágenes de tu entorno (cascos, chalecos, defectos, montacargas).
- Conexión a cámaras IP/CCTV por RTSP (hoy se usa la cámara del navegador o un video).
- Procesamiento con GPU dedicada para varias cámaras a la vez.
- Revisión humana de detecciones inciertas, métricas reales de precisión y piloto con usuarios.
- HTTPS, PostgreSQL, copias de seguridad, y cumplimiento legal de privacidad.

---

## 8. Pruebas

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

`tests/test_core.py` prueba contraseñas, tokens, base de datos, reglas y detectores. `tests/test_api.py` prueba la API completa (login, roles, alertas, reglas, CSV y seguridad de rutas).

---

## 9. Docker

```bash
docker compose up --build
```

Abre `http://localhost:8000`. Los datos quedan en el volumen `vanysha-data`.
Para YOLO dentro de Docker, añade `ultralytics` a `backend/requirements.txt` y reconstruye.

---

## 10. Problemas frecuentes

| Problema | Solución |
|---|---|
| La cámara no se activa | Usa `http://localhost:8000` (no una IP) o HTTPS, y permite la cámara en el navegador. |
| La etiqueta dice "Sin IA · solo movimiento" | El servidor no pudo iniciar YOLO ni HOG. Revisa la terminal: ahí aparece el motivo. Instala `opencv-python-headless<5`. |
| `No module named ...` | Activa el entorno virtual y ejecuta `pip install -r requirements.txt`. |
| El puerto 8000 está ocupado | Cambia `--port 8000` por otro puerto. |
| Olvidé la contraseña de la administradora | Borra `backend/data/vanysha.db` (se pierden los datos) y define `VANYSHA_ADMIN_PASSWORD` antes de volver a iniciar. |
