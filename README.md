# 🚢 BattleMish — Aplicación Multijugador en Red basada en Sockets TCP

**Universidad de La Frontera**  
**Asignatura:** ICC717-1 Taller de Redes  
**Integrantes:** José Rivera Bustos · Benjamin Fonseca · Ivan Carreño  
**Docente:** Flavio Alexis Rojas Acuña  
**Fecha de Entrega:** 31 de Agosto de 2026  

---

## 📋 1. Requisitos de Instalación y Entorno

- **Lenguaje de Programación:** Python 3 (compatible con Python 3.8 a 3.13).
- **Entorno de Ejecución:** Funciona en cualquier sistema operativo (Windows, Linux, macOS).
- **Bibliotecas Necesarias (Cero dependencias externas para la versión académica):**
  La aplicación de consola basada en Sockets TCP utiliza exclusivamente la **librería estándar de Python**:
  - `socket`: Creación y manipulación de llamadas a la API de sockets a bajo nivel.
  - `struct`: Empaquetado binario del prefijo de longitud de red (`!I` Big-Endian).
  - `threading`: Gestión concurrente de clientes y salas de juego (`GameRoom`).
  - `json`: Serialización estructurada de payloads de aplicación.
  - `argparse`: Lectura de parámetros por línea de comandos (IP y Puerto).
  - `unittest`: Suite de pruebas automatizadas (`test_game.py`).

*(Para la versión web opcional/complementaria se incluye `requirements.txt` con `fastapi`, `uvicorn`, `websockets` y `pyjwt`).*

---

## ⚙️ 2. Dirección IP y Puertos Utilizados

| Componente | Dirección IP por Defecto | Puerto por Defecto | Parámetros de Consola |
| :--- | :--- | :---: | :--- |
| **Servidor (`server.py`)** | `0.0.0.0` (todas las interfaces) o `127.0.0.1` | `8888` (configurable) | `--host <IP> --port <PUERTO>` |
| **Cliente (`client.py`)** | `127.0.0.1` (localhost) o IP del servidor | `8888` | `--host <IP> --port <PUERTO> --name <NOMBRE>` |

---

## 🚀 3. Comandos para Ejecutar el Programa

Abre **tres terminales** en la carpeta del proyecto:

### Paso 1: Iniciar el Servidor
```bash
python server.py --host 127.0.0.1 --port 8888
```
*El servidor creará el socket TCP (`AF_INET`, `SOCK_STREAM`), activará `SO_REUSEADDR`, enlazará el puerto con `bind()`, entrará en modo de escucha con `listen()` y quedará a la espera de conexiones con `accept()`.*

### Paso 2: Iniciar el Cliente 1 (Jugador 1)
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_1"
```

### Paso 3: Iniciar el Cliente 2 (Jugador 2)
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_2"
```

---

## 🎮 4. Ejemplo Básico de Ejecución

1. **Emparejamiento:** Al conectarse el segundo cliente, el servidor crea inmediatamente una sala independiente `GameRoom` (hilo dedicado) y notifica a ambos con `MSG_START_PLACEMENT`.
2. **Colocación de Flota:** Cada jugador puede elegir:
   - Opción `1`: Colocación manual de los 5 barcos (Portaaviones, Acorazado, Crucero, Submarino, Destructor) indicando coordenada y orientación (ej. `A1 H`).
   - Opción `2`: Colocación automática aleatoria.
   - *El servidor valida límites y ausencia de solapamientos con `_validate_and_build_board()`.*
3. **Fase de Batalla:**
   - El servidor otorga el turno inicial e indica `¡ES TU TURNO DE ATACAR!`.
   - El jugador atacante ingresa una coordenada (ej. `B4`).
   - El servidor calcula imparcialmente el resultado (`AGUA`, `TOCADO` o `HUNDIDO`) y emite `ATTACK_RESULT` actualizando ambos radares en tiempo real.
4. **Fin de Partida y Cierre Limpio:**
   - Al hundirse los 5 barcos de un jugador, el servidor declara ganador con `MSG_GAME_OVER`.
   - Ambos extremos ejecutan `shutdown(socket.SHUT_RDWR)` y `close()`, liberando inmediatamente los descriptores del sistema operativo.

---

## 🧪 5. Ejecución de Pruebas Automatizadas

Para validar el protocolo, las reglas del juego, una partida completa y la tolerancia a desconexiones abruptas, ejecuta:

```bash
python test_game.py
```
*Salida esperada:*
```text
....
------------------------------------------------------
Ran 4 tests in 0.432s

OK
```

---

## 📂 6. Estructura de Archivos del Proyecto

```text
BattleMish/
├── server.py                  # Servidor TCP multijugador con sockets puros y multithreading
├── client.py                  # Cliente interactivo de consola con UI en colores ANSI
├── protocol.py                # Capa de red con Message Framing (4 bytes Big-Endian + JSON)
├── game_logic.py              # Reglas de Battleship, flota de 5 barcos y tableros 10x10
├── test_game.py               # Suite de 4 pruebas automatizadas end-to-end
├── INFORME_TALLER_REDES.pdf   # Informe técnico académico completo en PDF
├── PRESENTACION_BATTLEMISH.pdf# Diapositivas para la defensa oral del proyecto
├── README.md                  # Manual de usuario e instrucciones de ejecución
├── web_server.py              # (Opcional) Servidor Web FastAPI con WebSockets
├── database.py                # (Opcional) Base de datos SQLite para historial web
└── static/                    # (Opcional) Frontend web en cuaderno escolar
```
