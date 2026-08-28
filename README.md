# 🚢 BattleMish — Plataforma Multijugador de Batalla Naval (Web & Consola)

Plataforma multijugador de **Batalla Naval (Battleship)** desarrollada en **Python 3**, que cuenta con dos modalidades completas:
1. **Versión Web Interactiva:** Interfaz en navegador (*Dark Glassmorphism*), sistema de cuentas de usuario, historial de partidas en SQLite, creación de salas por ID / código compartible, y combate en tiempo real con WebSockets y efectos de sonido dinámicos.
2. **Versión de Consola TCP:** Implementación original para la cátedra de redes, con sockets TCP puros (`socket.AF_INET`, `socket.SOCK_STREAM`), enmarcado de flujo (*Message Framing*) e informe académico formal.

---

## 🌐 Enlace Público de la Versión Web

> [!TIP]
> Puedes acceder a la versión web desplegada desde tu computador a través del túnel público seguro:
> **URL Pública:** `https://arguments-varieties-belkin-jump.trycloudflare.com`
> *(Accesible desde cualquier navegador, computadora o celular sin necesidad de configurar puertos)*

---

## 📋 Requisitos del Sistema

- **Lenguaje:** Python 3.8 o superior (compatible con Python 3.8 - 3.13).
- **Backend Web:** `fastapi`, `uvicorn`, `websockets`, `pyjwt`, `sqlite3`.
- **Frontend Web:** Vanilla HTML5, CSS3 moderno (*Glassmorphism*), JavaScript ES6+ y Web Audio API.

---

## 📂 Estructura del Proyecto

```text
BattleMish/
├── web_server.py              # Servidor Web FastAPI: REST APIs y Hub WebSocket de salas
├── database.py                # Base de datos SQLite: Usuarios, estadísticas e historial
├── game_logic.py              # Reglas de Battleship, flota, tableros y validaciones
├── static/                    # Frontend Web
│   ├── index.html             # Single Page Application (Lobby, Salas, Posicionamiento, Batalla)
│   ├── css/
│   │   └── style.css          # Estilos Cyberpunk Naval, Dark Glassmorphism y animaciones
│   └── js/
│       ├── app.js             # Lógica SPA, WebSockets y sincronización de turnos
│       └── audio.js           # Sintetizador de efectos sonoros náuticos (Web Audio API)
├── server.py                  # Servidor de consola TCP original (Sockets puros)
├── client.py                  # Cliente de consola original
├── protocol.py                # Capa de red con Message Framing sobre TCP
├── test_game.py               # Suite de pruebas automatizadas
├── INFORME_TALLER_REDES.md    # Informe académico formal de 10 secciones
└── README.md                  # Este manual de usuario
```

---

## 🚀 Cómo Ejecutar la Versión Web

### 1. Iniciar el Servidor Web Local
```bash
python -m uvicorn web_server:app --host 0.0.0.0 --port 8000
```
La aplicación estará disponible localmente en `http://127.0.0.1:8000`.

### 2. Generar o Iniciar el Enlace Público (Cloudflare Tunnel)
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```
Esto generará una URL pública segura `https://*.trycloudflare.com` que puedes compartir con cualquier persona para que juegue contigo.

---

## 🎮 Características de la Versión Web

1. **Cuentas de Usuario y Seguridad:** Registro e inicio de sesión con contraseñas encriptadas mediante SHA-256 + Salt y tokens de sesión JWT.
2. **Historial de Partidas y Récords:** Registro persistente de victorias, derrotas, porcentaje de win rate, turnos y duración de cada batalla.
3. **Salas por ID:** Crea salas privadas o públicas con códigos de 6 caracteres (ej. `WAR-7291`) o comparte un enlace directo `https://.../?room=WAR-7291`.
4. **Despliegue Táctico:** Colocación interactiva con rotación de barcos (tecla `R`) o despliegue aleatorio instantáneo.
5. **Radar en Tiempo Real:** Visualización táctica lado a lado de tu flota y el radar enemigo, con avisos de impacto, agua y hundimiento.
6. **Efectos de Sonido:** Sonar submarino, torpedos, explosiones y fanfarria de victoria generados con la API Web Audio del navegador.

---

## 💻 Cómo Ejecutar la Versión de Consola TCP (Académica)

### Servidor de Consola:
```bash
python server.py --host 0.0.0.0 --port 8888
```

### Clientes de Consola:
```bash
# Jugador 1:
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_1"

# Jugador 2:
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_2"
```

---

## 🧪 Pruebas Automatizadas

```bash
python test_game.py
```
