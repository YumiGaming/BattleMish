# BattleMish — Batalla Naval Multijugador

> **Batalla Naval en Hoja de Cuaderno** // Juego multijugador en tiempo real con estética de lápiz y papel.  
> **Desarrollador:** Yumi

---

## 1. Descripción General

**BattleMish** es una recreación moderna del clásico juego de estrategia naval con estética de libreta de apuntes (*notebook paper doodle*). El proyecto ofrece una experiencia multijugador completa en tiempo real, permitiendo a los jugadores crear salas, posicionar su flota de 5 buques reglamentarios, batallar mediante disparos navales por turnos y llevar registro de sus estadísticas y victorias.

El proyecto cuenta con dos modalidades:
1. **Versión Web Moderna (Principal):** Servidor asíncrono con FastAPI y WebSockets, interfaz web responsiva, efectos de sonido sintetizados en el cliente con Web Audio API, autenticación JWT y persistencia con SQLite.
2. **Versión Consola TCP (Core):** Implementación clásica basada en sockets TCP puros (`socket`, `struct`, `threading`), con Message Framing binario (4 bytes Big-Endian + JSON).

---

## 2. Características Principales

- **Multijugador en Tiempo Real:** Comunicación bidireccional de baja latencia mediante WebSockets.
- **Estética Cuaderno Cuadriculado:** Interfaz estilizada tipo hoja de libreta escolar con márgenes, tipografías estilo manuscrito y trazos doodle en tinta azul y roja.
- **Flota de Combate Completa:** 5 navíos reglamentarios (Portaaviones: 5 casillas, Acorazado: 4, Crucero: 3, Submarino: 3, Destructor: 2).
- **Despliegue Estratégico:** Colocación manual interactiva con rotación (horizontal/vertical) o generación aleatoria automática de flota.
- **Motor de Audio Sintetizado:** Efectos de sonido dinámicos (disparos, impactos, agua, victoria y derrota) generados en tiempo real con Web Audio API sin necesidad de archivos de audio externos.
- **Cuentas y Estadísticas:** Registro y login de usuarios con contraseñas seguras (PBKDF2-HMAC-SHA256), tokens JWT, historial de partidas y porcentaje de victorias.
- **Salas Públicas y Privadas:** Creación y unión a salas mediante identificadores únicos (`WAR-XXXX`).
- **Favicon e Identidad Visual:** Icono temático del barco de guerra en formato SVG y multi-resolución ICO adaptado a temas claros y oscuros.

---

## 3. Tecnologías y Requisitos

### Requisitos del Sistema
- **Python:** 3.8 o superior (compatible con Python 3.13)
- **Navegador Web:** Cualquier navegador moderno con soporte para WebSockets y Web Audio API (Chrome, Edge, Firefox, Safari, Brave, Opera)

### Dependencias de la Versión Web
```bash
pip install fastapi uvicorn websockets pyjwt
```

---

## 4. Guía de Ejecución

### 4.1 Iniciar la Versión Web (Recomendado)

Inicia el servidor web FastAPI con Uvicorn:

```bash
python -m uvicorn web_server:app --host 0.0.0.0 --port 8000
```

Abre tu navegador web e ingresa a:
```
http://localhost:8000
```

*(Opcional: Para jugar a través de internet con amigos, puedes exponer el puerto usando Cloudflare Tunnels: `cloudflared tunnel --url http://127.0.0.1:8000`)*.

---

### 4.2 Iniciar la Versión de Consola TCP

Si deseas ejecutar la versión de terminal por sockets TCP nativos:

**Terminal 1 — Servidor TCP:**
```bash
python server.py --host 127.0.0.1 --port 8888
```

**Terminal 2 — Jugador 1:**
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Capitan_1"
```

**Terminal 3 — Jugador 2:**
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Capitan_2"
```

---

## 5. Pruebas Automatizadas

El proyecto incluye una suite completa de pruebas unitarias y de integración end-to-end:

```bash
python test_game.py
```

---

## 6. Estructura del Repositorio

```text
BattleMish/
├── web_server.py         # Servidor Web FastAPI con endpoints REST y Hub WebSocket
├── database.py           # Gestión de base de datos SQLite (usuarios, partidas, stats)
├── game_logic.py         # Reglas del juego Battleship, validación de coordenadas y tablero
├── server.py             # Servidor TCP de terminal con concurrencia y sockets nativos
├── client.py             # Cliente interactivo de terminal (interfaz ANSI)
├── protocol.py           # Protocolo de comunicación y Message Framing TCP
├── test_game.py          # Suite de pruebas automatizadas
├── static/               # Frontend Web
│   ├── index.html        # Estructura principal y pantallas del juego
│   ├── css/
│   │   └── style.css     # Diseño y estilos temáticos de hoja de cuaderno
│   ├── js/
│   │   ├── app.js        # Lógica del cliente, conexión WebSocket y renderizado de tableros
│   │   └── audio.js      # Sintetizador de audio con Web Audio API
│   ├── favicon.ico       # Icono multi-resolución para navegadores
│   ├── favicon.svg       # Icono vectorial escalable
│   └── *.png             # Iconos PNG y Apple Touch Icon
└── README.md             # Documentación del proyecto
```

---

## 7. Autor y Créditos

- **Desarrollador:** Yumi
