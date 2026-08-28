"""
protocol.py - Capa de Protocolo de Red para Battleship

Implementa la serialización y el enmarcado de mensajes (Message Framing)
sobre flujos de bytes TCP (SOCK_STREAM).

Dado que TCP es un protocolo orientado al flujo continuo de bytes (stream-oriented)
y no a límites de paquetes o datagramas, dos llamadas a send() pueden llegar
en un único recv() (concatenación) o un mensaje grande puede dividirse en múltiples
recv() (fragmentación).

Para solucionar esto, cada mensaje se envía con un encabezado de longitud fija de 4 bytes
(Big-Endian, unsigned int) indicando el tamaño exacto del payload JSON en bytes UTF-8:
    [ 4 Bytes: Longitud N ] + [ N Bytes: JSON Payload ]
"""

import json
import struct
import socket
from typing import Any, Dict, Optional

# --- Tipos de Mensajes del Protocolo ---
MSG_WELCOME = "WELCOME"                 # Servidor -> Cliente (Asignación de ID y espera)
MSG_START_PLACEMENT = "START_PLACEMENT" # Servidor -> Cliente (Iniciar colocación de barcos)
MSG_PLACE_SHIPS = "PLACE_SHIPS"         # Cliente -> Servidor (Lista de barcos posicionados)
MSG_PLACEMENT_ACK = "PLACEMENT_ACK"     # Servidor -> Cliente (Validación de barcos exitosa)
MSG_START_BATTLE = "START_BATTLE"       # Servidor -> Cliente (Inicio de batalla, indica primer turno)
MSG_YOUR_TURN = "YOUR_TURN"             # Servidor -> Cliente (Es tu turno de disparar)
MSG_WAIT_TURN = "WAIT_TURN"             # Servidor -> Cliente (Turno del oponente, espera)
MSG_ATTACK = "ATTACK"                   # Cliente -> Servidor (Coordenada de disparo, ej: "B4")
MSG_ATTACK_RESULT = "ATTACK_RESULT"     # Servidor -> Ambos (Resultado del disparo: AGUA, TOCADO, HUNDIDO)
MSG_GAME_OVER = "GAME_OVER"             # Servidor -> Ambos (Fin de partida, ganador y razón)
MSG_ERROR = "ERROR"                     # Servidor -> Cliente (Mensaje de error / jugada inválida)
MSG_DISCONNECT = "DISCONNECT"           # Servidor/Cliente (Notificación de desconexión)
MSG_CHAT = "CHAT"                       # Mensaje informativo o de estado

HEADER_FORMAT = "!I"                    # 4 bytes, Big-Endian (Network byte order), unsigned int
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def send_msg(sock: socket.socket, data: Dict[str, Any]) -> None:
    """
    Serializa un diccionario Python a JSON, calcula su tamaño en bytes UTF-8,
    antepone el encabezado de 4 bytes y lo envía completamente mediante sendall().
    
    Args:
        sock: Socket TCP conectado.
        data: Diccionario con la información del mensaje.
        
    Raises:
        ConnectionError: Si el socket se cierra o la transmisión falla.
        OSError: En caso de errores de socket del sistema operativo.
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        payload_bytes = json_str.encode("utf-8")
        msg_length = len(payload_bytes)
        
        # Empaquetar encabezado con longitud
        header = struct.pack(HEADER_FORMAT, msg_length)
        
        # Enviar encabezado + payload utilizando sendall() para garantizar
        # que todo el buffer sea transmitido íntegramente
        sock.sendall(header + payload_bytes)
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        raise ConnectionError(f"Error al enviar datos por el socket: {e}") from e


def _recv_all(sock: socket.socket, n_bytes: int) -> Optional[bytes]:
    """
    Función auxiliar que lee exactamente n_bytes del flujo TCP mediante recv() en bucle.
    
    Args:
        sock: Socket TCP conectado.
        n_bytes: Cantidad exacta de bytes a leer.
        
    Returns:
        bytes con los datos leídos, o None si la conexión se cerró limpiamente.
        
    Raises:
        ConnectionError: Si la conexión se interrumpe antes de recibir todos los bytes.
    """
    data = bytearray()
    while len(data) < n_bytes:
        try:
            chunk = sock.recv(min(4096, n_bytes - len(data)))
            if not chunk:
                # El socket fue cerrado por el extremo remoto (EOF)
                if len(data) == 0:
                    return None
                raise ConnectionError("Conexión cerrada prematuramente mientras se recibían datos.")
            data.extend(chunk)
        except (ConnectionResetError, BrokenPipeError) as e:
            raise ConnectionError(f"Conexión reiniciada por el par remoto: {e}") from e
    return bytes(data)


def recv_msg(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Recibe un mensaje completo enmarcado desde el socket TCP.
    Lee primero el encabezado de 4 bytes con la longitud y luego el payload JSON.
    
    Args:
        sock: Socket TCP conectado.
        
    Returns:
        Diccionario deserializado desde JSON, o None si el par se desconectó limpiamente.
        
    Raises:
        ConnectionError: Si hay un fallo de red o desconexión abrupta.
        ValueError: Si el payload recibido no es un JSON válido.
    """
    header_bytes = _recv_all(sock, HEADER_SIZE)
    if header_bytes is None:
        return None
    
    # Desempaquetar la longitud del mensaje
    msg_length, = struct.unpack(HEADER_FORMAT, header_bytes)
    
    # Leer el payload completo
    payload_bytes = _recv_all(sock, msg_length)
    if payload_bytes is None:
        return None
    
    try:
        json_str = payload_bytes.decode("utf-8")
        return json.loads(json_str)
    except Exception as e:
        raise ValueError(f"Error al decodificar mensaje JSON: {e}") from e
