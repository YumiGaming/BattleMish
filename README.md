# 🚢 Battleship Multiplayer — Aplicación en Red basada en Sockets TCP

Aplicación multijugador cliente-servidor de **Batalla Naval (Battleship)** desarrollada en **Python 3** utilizando la biblioteca nativa `socket`, cumpliendo con todos los requerimientos de comunicación en red, concurrencia, enmarcado de mensajes y arquitectura orientada a eventos.

---

## 📋 Requisitos del Sistema

- **Lenguaje:** Python 3.8 o superior (compatible con Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13).
- **Bibliotecas:** Únicamente la **Biblioteca Estándar de Python** (`socket`, `json`, `threading`, `struct`, `time`, `os`, `sys`, `unittest`, `argparse`).
- **Dependencias externas:** Ninguna (no requiere `pip install`).
- **Sistemas Operativos compatibles:** Windows 10/11, Linux (Ubuntu, Debian, Fedora, etc.), macOS.

---

## 📂 Estructura del Proyecto

```text
Taller Redes/
├── server.py                  # Servidor TCP multijugador y gestor de salas concurrentes
├── client.py                  # Cliente interactivo de terminal con interfaz ANSI a color
├── protocol.py                # Capa de red: Message Framing (4-byte length prefix) y JSON
├── game_logic.py              # Reglas de Battleship, flota, tableros, ataques y renderizado
├── test_game.py               # Suite de pruebas automatizadas (unitarias y de integración)
├── README.md                  # Manual de usuario e instrucciones de ejecución
└── INFORME_TALLER_REDES.md    # Informe académico formal y técnico completo (10 secciones)
```

---

## 🚀 Instrucciones de Ejecución

### 1. Iniciar el Servidor
Abre una terminal y ejecuta el servidor indicando opcionalmente la dirección IP y el puerto:

```bash
# Ejecución por defecto (0.0.0.0:8888):
python server.py

# O especificando IP y Puerto:
python server.py --host 0.0.0.0 --port 8888
```

El servidor quedará en estado de escucha pasiva (`listen`) esperando la conexión de los clientes.

### 2. Iniciar el Jugador 1 (Cliente 1)
En una segunda terminal, ejecuta:

```bash
# Conexión local por defecto:
python client.py

# O especificando parámetros:
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_Drake"
```

El cliente se conectará (`connect`) y esperará en el lobby hasta que se conecte el segundo jugador.

### 3. Iniciar el Jugador 2 (Cliente 2)
En una tercera terminal, ejecuta:

```bash
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_Nelson"
```

Tan pronto se conecte el segundo jugador, el servidor creará una sala de juego dedicada (`GameRoom`) en un hilo independiente e iniciará la **Fase de Despliegue de la Flota**.

---

## 🎮 Modo de Juego

### Fase 1: Despliegue de la Flota
Cada jugador cuenta con 5 barcos reglamentarios:
1. **Portaaviones** (5 casillas)
2. **Acorazado** (4 casillas)
3. **Crucero** (3 casillas)
4. **Submarino** (3 casillas)
5. **Destructor** (2 casillas)

Puedes elegir entre:
- **1) Despliegue Automático / Aleatorio:** Genera un tablero válido instantáneamente, con opción de reintentar o confirmar.
- **2) Despliegue Manual:** Ingresa coordenada inicial y orientación (`H` para Horizontal, `V` para Vertical). Ejemplo: `A1 H` o `C4 V`.

### Fase 2: Batalla Naval por Turnos
- En tu turno, ingresa la coordenada que deseas bombardear (ejemplo: `B4`, `J10`).
- La pantalla actualizará en tiempo real el radar y el estado de la flota:
  - `S` : Barco propio (Verde)
  - `X` : Impacto directo / Tocado (Rojo)
  - `O` : Disparo al agua (Amarillo)
  - `~` / `.` : Mar inexplorado (Azul / Blanco)
- El servidor informa si el disparo fue `AGUA`, `TOCADO` o si provocó el `HUNDIDO` de una nave específica.
- El primer jugador en hundir los 5 barcos enemigos gana la partida.

---

## 🧪 Ejecución de Pruebas Automatizadas

Para validar el correcto funcionamiento del protocolo, enmarcado de flujo, detección de errores y ciclo completo de partida:

```bash
python test_game.py
```

Salida esperada:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 0.456s

OK
```

---

## 🌐 Resumen de Métodos de Sockets Utilizados

| Método | Propósito en el Proyecto | Archivo / Contexto |
| :--- | :--- | :--- |
| `socket()` | Creación del endpoint TCP (`AF_INET`, `SOCK_STREAM`). | `server.py`, `client.py`, `test_game.py` |
| `setsockopt()` | Habilita `SO_REUSEADDR` para reiniciar el servidor sin demoras de `TIME_WAIT`. | `server.py` |
| `bind()` | Asocia la dirección IP y el puerto de escucha al servidor. | `server.py` |
| `listen()` | Pone al servidor en modo de escucha con cola de conexiones pendientes. | `server.py` |
| `accept()` | Acepta clientes entrantes y retorna un nuevo socket de comunicación. | `server.py` |
| `connect()` | Conecta el cliente al servidor remoto mediante IP y puerto. | `client.py` |
| `sendall()` | Transmite el buffer completo con prefijo de 4 bytes sin pérdidas. | `protocol.py` |
| `recv()` | Lee del flujo de bytes TCP para reconstruir el mensaje exacto. | `protocol.py` |
| `settimeout()` | Evita bloqueos indefinidos durante operaciones de red o apagado. | `server.py`, `client.py` |
| `shutdown()` | Notifica el cierre ordenado de los canales de lectura/escritura (`SHUT_RDWR`). | `server.py`, `client.py` |
| `close()` | Libera el descriptor de archivo del socket en el sistema operativo. | `server.py`, `client.py`, `protocol.py` |
| `gethostbyname()` | Resuelve nombres de dominio o hosts (ej. `localhost`) a direcciones IPv4. | `client.py` |
