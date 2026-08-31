# BattleMish — Aplicación Multijugador en Red basada en Sockets TCP

**Universidad de La Frontera**  
**Asignatura:** ICC717-1 Taller de Redes  
**Integrantes:** José Rivera Bustos · Benjamin Fonseca · Ivan Carreño  
**Docente:** Flavio Alexis Rojas Acuña  
**Fecha de Entrega:** 31 de Agosto de 2026  

---

## 1. Requisitos de Instalación y Entorno

- **Lenguaje de Programación:** Python 3 (compatible con Python 3.8 a 3.13).
- **Entorno de Ejecución:** Multiplataforma (Windows, Linux, macOS).
- **Bibliotecas Necesarias (Cero dependencias externas para la versión académica):**
  La aplicación de consola basada en Sockets TCP utiliza exclusivamente módulos de la **librería estándar de Python**:
  - `socket`: Creación y control de sockets TCP/IP a bajo nivel.
  - `struct`: Empaquetado binario del prefijo de longitud de red (`!I` Big-Endian).
  - `threading`: Gestión concurrente de clientes y salas de juego (`GameRoom`).
  - `json`: Serialización y deserialización de mensajes estructurados.
  - `argparse`: Procesamiento de argumentos por línea de comandos (IP y Puerto).
  - `unittest`: Suite de pruebas automatizadas (`test_game.py`).

*(Para la versión web complementaria se incluye `requirements.txt` con `fastapi`, `uvicorn`, `websockets` y `pyjwt`).*

---

## 2. Dirección IP y Puertos Utilizados

| Componente | Dirección IP por Defecto | Puerto por Defecto | Parámetros de Consola |
| :--- | :--- | :---: | :--- |
| **Servidor (`server.py`)** | `0.0.0.0` (todas las interfaces) o `127.0.0.1` | `8888` (configurable) | `--host <IP> --port <PUERTO>` |
| **Cliente (`client.py`)** | `127.0.0.1` (localhost) o IP del servidor | `8888` | `--host <IP> --port <PUERTO> --name <NOMBRE>` |

---

## 3. Comandos para Ejecutar el Programa

Abrir **tres terminales** en el directorio raíz del proyecto:

### Paso 1: Iniciar el Servidor
```bash
python server.py --host 127.0.0.1 --port 8888
```
*El servidor inicializa el socket TCP (`AF_INET`, `SOCK_STREAM`), habilita `SO_REUSEADDR`, asocia el puerto con `bind()`, pasa a modo pasivo con `listen()` y atiende conexiones entrantes con `accept()`.*

### Paso 2: Iniciar el Cliente 1 (Jugador 1)
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_1"
```

### Paso 3: Iniciar el Cliente 2 (Jugador 2)
```bash
python client.py --host 127.0.0.1 --port 8888 --name "Almirante_2"
```

---

## 4. Ejemplo Básico de Ejecución

1. **Emparejamiento:** Al establecer conexión el segundo cliente, el servidor instancia una sala de juego aislada `GameRoom` (hilo independiente) y notifica a ambos con `MSG_START_PLACEMENT`.
2. **Colocación de Flota:** Cada participante selecciona su modo de despliegue:
   - Opción `1`: Posicionamiento manual de los 5 buques reglamentarios (Portaaviones, Acorazado, Crucero, Submarino, Destructor) especificando coordenada de inicio y orientación (ej. `A1 H`).
   - Opción `2`: Posicionamiento automático aleatorio.
   - *El servidor valida límites y colisiones mediante el método `_validate_and_build_board()`.*
3. **Fase de Batalla:**
   - El servidor otorga el turno inicial e indica `¡ES TU TURNO DE ATACAR!`.
   - El atacante ingresa la coordenada de disparo (ej. `B4`).
   - El servidor evalúa el impacto (`AGUA`, `TOCADO` o `HUNDIDO`) y emite `ATTACK_RESULT` actualizando ambos tableros en tiempo real.
4. **Fin de Partida y Cierre de Conexiones:**
   - Al destruirse los 5 buques de una flota, el servidor declara ganador mediante `MSG_GAME_OVER`.
   - Ambos extremos invocan `shutdown(socket.SHUT_RDWR)` y `close()`, liberando de inmediato los descriptores del sistema operativo.

---

## 5. Ejecución de Pruebas Automatizadas

Para verificar el enmarcado de flujo, las reglas del tablero, una partida completa hasta la victoria y la gestión de desconexiones abruptas:

```bash
python test_game.py
```
*Resultado esperado:*
```text
....
------------------------------------------------------
Ran 4 tests in 0.432s

OK
```

---

## 6. Estructura de Archivos del Proyecto

```text
BattleMish/
├── server.py                  # Servidor TCP multijugador con sockets nativos y concurrencia
├── client.py                  # Cliente interactivo de consola con interfaz ANSI
├── protocol.py                # Capa de red con Message Framing (4 bytes Big-Endian + JSON UTF-8)
├── game_logic.py              # Reglas de Battleship, flota de 5 buques y tableros 10x10
├── test_game.py               # Suite de 4 pruebas automatizadas end-to-end
├── INFORME_TALLER_REDES.pdf   # Informe técnico académico formal en PDF
├── PRESENTACION_BATTLEMISH.pdf# Diapositivas para la exposición y defensa oral
├── README.md                  # Manual técnico e instrucciones de ejecución
├── web_server.py              # (Complementario) Servidor Web FastAPI con WebSockets
├── database.py                # (Complementario) Base de datos SQLite para persistencia
└── static/                    # (Complementario) Frontend web
```
