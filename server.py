"""
server.py - Servidor Multijugador de Battleship (Batalla Naval) con Sockets TCP

Gestiona conexiones concurrentes, emparejamiento de jugadores en salas de juego,
validación de colocación de flotas, control estricto de turnos, verificación de
impactos/hundimientos y detección de desconexiones.

Uso de Sockets TCP:
    - socket(): Creación del socket IPv4 / TCP de flujo (AF_INET, SOCK_STREAM).
    - setsockopt(): Configuración de opciones (SO_REUSEADDR, SO_KEEPALIVE).
    - bind(): Asociación de la dirección IP y el puerto de escucha.
    - listen(): Puesta en estado de escucha pasiva con cola de espera.
    - accept(): Aceptación de conexiones entrantes de clientes.
    - settimeout(): Control de tiempos de espera para operaciones bloqueantes.
    - sendall(): Envío íntegro de datos enmarcardos.
    - recv(): Lectura continua del flujo de bytes.
    - shutdown() / close(): Cierre y liberación ordenada de recursos.
"""

import sys
import time
import socket
import threading
import argparse
import traceback
from typing import Dict, List, Optional, Tuple

import protocol
from game_logic import (
    Board, Ship, FLEET_SPEC, parse_coord, format_coord,
    BOARD_SIZE
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8888
SOCKET_TIMEOUT = 120.0  # 2 minutos de inactividad máxima por operación


def log(msg: str, prefix: str = "SERVER") -> None:
    """Imprime un mensaje formateado con marca temporal."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{prefix}] {msg}", flush=True)


class PlayerConnection:
    """Encapsula la sesión de socket y estado de juego de un jugador conectado."""
    def __init__(self, sock: socket.socket, addr: Tuple[str, int], player_id: int, name: str = ""):
        self.sock = sock
        self.addr = addr
        self.player_id = player_id
        self.name = name or f"Jugador_{player_id}"
        self.board: Optional[Board] = None
        self.is_ready = False
        self.is_connected = True

    def send(self, data: dict) -> bool:
        """Envía un mensaje enmarcado al cliente de manera segura."""
        if not self.is_connected:
            return False
        try:
            protocol.send_msg(self.sock, data)
            return True
        except Exception as e:
            log(f"Error al enviar mensaje a {self.name} ({self.addr}): {e}", "SOCKET")
            self.is_connected = False
            return False

    def recv(self) -> Optional[dict]:
        """Recibe un mensaje enmarcado desde el cliente de manera segura."""
        if not self.is_connected:
            return None
        try:
            msg = protocol.recv_msg(self.sock)
            if msg is None:
                self.is_connected = False
            return msg
        except socket.timeout:
            log(f"Timeout de socket alcanzado para {self.name} ({self.addr})", "SOCKET")
            self.is_connected = False
            return None
        except Exception as e:
            log(f"Error al recibir datos de {self.name} ({self.addr}): {e}", "SOCKET")
            self.is_connected = False
            return None

    def close(self) -> None:
        """Cierra el socket liberando los recursos de red."""
        self.is_connected = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class GameRoom(threading.Thread):
    """
    Hilo de ejecución que administra una partida completa entre dos jugadores.
    """
    def __init__(self, room_id: int, p1: PlayerConnection, p2: PlayerConnection):
        super().__init__(name=f"GameRoom-{room_id}", daemon=True)
        self.room_id = room_id
        self.p1 = p1
        self.p2 = p2
        self.running = True

    def run(self) -> None:
        log(f"Sala #{self.room_id} iniciada: {self.p1.name} vs {self.p2.name}", "ROOM")
        try:
            # 1. Notificar a ambos jugadores que la partida va a comenzar la fase de posicionamiento
            self._notify_start_placement()
            
            # 2. Recibir y validar la colocación de barcos de ambos jugadores
            if not self._handle_placement_phase():
                return
            
            # 3. Fase de batalla por turnos
            self._handle_battle_phase()
            
        except Exception as e:
            log(f"Excepción no controlada en Sala #{self.room_id}: {e}\n{traceback.format_exc()}", "ERROR")
        finally:
            self._cleanup()
            log(f"Sala #{self.room_id} finalizada.", "ROOM")

    def _notify_start_placement(self) -> None:
        """Notifica a ambos jugadores que deben posicionar sus flotas."""
        self.p1.send({
            "type": protocol.MSG_START_PLACEMENT,
            "player_id": self.p1.player_id,
            "opponent_name": self.p2.name,
            "fleet_spec": FLEET_SPEC,
            "board_size": BOARD_SIZE
        })
        self.p2.send({
            "type": protocol.MSG_START_PLACEMENT,
            "player_id": self.p2.player_id,
            "opponent_name": self.p1.name,
            "fleet_spec": FLEET_SPEC,
            "board_size": BOARD_SIZE
        })

    def _validate_and_build_board(self, ships_data: List[dict]) -> Optional[Board]:
        """Valida que la lista de barcos enviada cumpla con las reglas oficiales."""
        if not isinstance(ships_data, list):
            return None
        
        board = Board(BOARD_SIZE)
        # Verificar cantidad de barcos
        if len(ships_data) != len(FLEET_SPEC):
            return None
        
        # Verificar cada barco
        for spec in FLEET_SPEC:
            matching = [s for s in ships_data if s.get("name") == spec["name"] and s.get("size") == spec["size"]]
            if len(matching) != 1:
                return None
            
            s = matching[0]
            start_coord = s.get("start")  # ej: "A1"
            orientation = s.get("orientation")  # 'H' o 'V'
            
            coord_tuple = parse_coord(start_coord)
            if coord_tuple is None or orientation not in ('H', 'V'):
                return None
            
            r, c = coord_tuple
            ship = board.place_ship(spec["name"], spec["size"], r, c, orientation, spec["id"])
            if ship is None:
                # Posición inválida o solapada
                return None
            
        return board

    def _handle_placement_phase(self) -> bool:
        """Espera y procesa la colocación de barcos de ambos jugadores concurrentemente."""
        results = {"p1_ok": False, "p2_ok": False}

        def process_player(p: PlayerConnection, opponent: PlayerConnection, key: str):
            while p.is_connected and not results[key]:
                msg = p.recv()
                if not msg:
                    break
                
                msg_type = msg.get("type")
                if msg_type == protocol.MSG_PLACE_SHIPS:
                    ships_data = msg.get("ships", [])
                    board = self._validate_and_build_board(ships_data)
                    
                    if board is not None:
                        p.board = board
                        p.is_ready = True
                        results[key] = True
                        p.send({
                            "type": protocol.MSG_PLACEMENT_ACK,
                            "message": "Flota desplegada y validada correctamente por el servidor. Esperando al oponente..."
                        })
                        log(f"{p.name} ha posicionado su flota con éxito.", f"ROOM-{self.room_id}")
                    else:
                        p.send({
                            "type": protocol.MSG_ERROR,
                            "message": "Configuración de flota inválida (solapamiento o fuera de límites). Intenta nuevamente."
                        })
                else:
                    p.send({
                        "type": protocol.MSG_ERROR,
                        "message": f"Mensaje no esperado durante la fase de posicionamiento: {msg_type}"
                    })

        t1 = threading.Thread(target=process_player, args=(self.p1, self.p2, "p1_ok"), daemon=True)
        t2 = threading.Thread(target=process_player, args=(self.p2, self.p1, "p2_ok"), daemon=True)
        
        t1.start()
        t2.start()
        
        t1.join(timeout=SOCKET_TIMEOUT)
        t2.join(timeout=SOCKET_TIMEOUT)

        if not results["p1_ok"] or not results["p2_ok"]:
            # Uno o ambos se desconectaron o agotaron el tiempo
            if not self.p1.is_connected and self.p2.is_connected:
                self.p2.send({
                    "type": protocol.MSG_GAME_OVER,
                    "winner": self.p2.name,
                    "reason": f"El oponente ({self.p1.name}) se ha desconectado durante el posicionamiento."
                })
            elif not self.p2.is_connected and self.p1.is_connected:
                self.p1.send({
                    "type": protocol.MSG_GAME_OVER,
                    "winner": self.p1.name,
                    "reason": f"El oponente ({self.p2.name}) se ha desconectado durante el posicionamiento."
                })
            return False

        return True

    def _handle_battle_phase(self) -> None:
        """Administra los turnos de disparo alternados entre p1 y p2."""
        current_attacker = self.p1
        current_defender = self.p2
        
        # Notificar inicio de combate
        self.p1.send({
            "type": protocol.MSG_START_BATTLE,
            "first_turn_player": current_attacker.name
        })
        self.p2.send({
            "type": protocol.MSG_START_BATTLE,
            "first_turn_player": current_attacker.name
        })
        
        log(f"Comienza la batalla en Sala #{self.room_id}. Primer turno: {current_attacker.name}", f"ROOM-{self.room_id}")

        while self.running and self.p1.is_connected and self.p2.is_connected:
            # 1. Indicar turnos
            current_attacker.send({"type": protocol.MSG_YOUR_TURN})
            current_defender.send({"type": protocol.MSG_WAIT_TURN, "current_player": current_attacker.name})
            
            # 2. Esperar coordenadas del atacante
            valid_attack = False
            while not valid_attack and current_attacker.is_connected:
                msg = current_attacker.recv()
                if not msg:
                    break
                
                if msg.get("type") != protocol.MSG_ATTACK:
                    current_attacker.send({
                        "type": protocol.MSG_ERROR,
                        "message": "Se esperaba una orden de ataque (MSG_ATTACK)."
                    })
                    continue
                
                coord_str = msg.get("coord", "")
                coord_tuple = parse_coord(coord_str)
                
                if coord_tuple is None:
                    current_attacker.send({
                        "type": protocol.MSG_ERROR,
                        "message": f"Coordenada inválida '{coord_str}'. Formato esperado: Letra (A-J) + Número (1-10), ej: 'B4'."
                    })
                    continue
                
                # Ejecutar ataque en el tablero del defensor
                result, sunk_ship_name = current_defender.board.receive_attack(coord_tuple)
                
                if result == "ALREADY_SHOT":
                    current_attacker.send({
                        "type": protocol.MSG_ERROR,
                        "message": f"Ya has disparado previamente a la casilla {coord_str.upper()}. Elige otra coordenada."
                    })
                    continue
                
                valid_attack = True
                formatted_coord = format_coord(*coord_tuple)
                log(f"{current_attacker.name} disparó a {formatted_coord} -> {result} {f'({sunk_ship_name})' if sunk_ship_name else ''}", f"ROOM-{self.room_id}")
                
                # Enviar resultado a ambos jugadores
                attack_payload = {
                    "type": protocol.MSG_ATTACK_RESULT,
                    "attacker": current_attacker.name,
                    "defender": current_defender.name,
                    "coord": formatted_coord,
                    "result": result,  # "AGUA", "TOCADO", "HUNDIDO"
                    "sunk_ship": sunk_ship_name,
                    "defender_ships_remaining": current_defender.board.ships_remaining()
                }
                current_attacker.send(attack_payload)
                current_defender.send(attack_payload)
                
                # Verificar condición de victoria
                if current_defender.board.all_ships_sunk():
                    log(f"¡Victoria para {current_attacker.name} en Sala #{self.room_id}!", f"ROOM-{self.room_id}")
                    game_over_payload = {
                        "type": protocol.MSG_GAME_OVER,
                        "winner": current_attacker.name,
                        "loser": current_defender.name,
                        "reason": f"¡{current_attacker.name} ha destruido toda la flota enemiga!"
                    }
                    self.p1.send(game_over_payload)
                    self.p2.send(game_over_payload)
                    self.running = False
                    return

            # Cambiar de turno
            current_attacker, current_defender = current_defender, current_attacker

        # Si el bucle termina por desconexión de algún jugador
        if not self.p1.is_connected and self.p2.is_connected:
            self.p2.send({
                "type": protocol.MSG_GAME_OVER,
                "winner": self.p2.name,
                "reason": f"El oponente ({self.p1.name}) se ha desconectado de la partida."
            })
        elif not self.p2.is_connected and self.p1.is_connected:
            self.p1.send({
                "type": protocol.MSG_GAME_OVER,
                "winner": self.p1.name,
                "reason": f"El oponente ({self.p2.name}) se ha desconectado de la partida."
            })

    def _cleanup(self) -> None:
        """Cierra sockets de ambos jugadores de la sala."""
        self.running = False
        self.p1.close()
        self.p2.close()


class BattleshipServer:
    """
    Servidor principal de Battleship.
    Escucha conexiones entrantes, asigna clientes y crea salas de juego de 2 jugadores.
    """
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False
        self.waiting_player: Optional[PlayerConnection] = None
        self.waiting_lock = threading.Lock()
        self.room_counter = 0

    def start(self) -> None:
        """Inicia el socket del servidor y el bucle de aceptación de conexiones."""
        # 1. Crear el socket TCP (IPv4, SOCK_STREAM)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # 2. Configurar opciones del socket: SO_REUSEADDR permite reutilizar el puerto inmediatamente
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 3. Enlazar socket a la dirección IP y puerto
        try:
            self.server_socket.bind((self.host, self.port))
        except OSError as e:
            log(f"Error fatal al enlazar socket a {self.host}:{self.port}: {e}", "FATAL")
            sys.exit(1)
            
        # 4. Poner el socket en modo de escucha con una cola de conexiones pendientes
        self.server_socket.listen(10)
        self.is_running = True
        
        # Configurar un timeout en el socket de escucha para permitir interrupciones limpias (Ctrl+C)
        self.server_socket.settimeout(1.0)
        
        log(f"Servidor Battleship TCP iniciado exitosamente en {self.host}:{self.port}", "INIT")
        log("Esperando jugadores para emparejar...", "INIT")

        player_counter = 0
        try:
            while self.is_running:
                try:
                    # 5. Aceptar conexión entrante
                    client_sock, client_addr = self.server_socket.accept()
                except socket.timeout:
                    # Timeout esperado para verificar si self.is_running sigue siendo True
                    continue
                except OSError:
                    break
                
                # Configurar timeout en el socket del cliente para evitar bloqueos eternos
                client_sock.settimeout(SOCKET_TIMEOUT)
                
                player_counter += 1
                log(f"Nueva conexión aceptada desde {client_addr[0]}:{client_addr[1]} (ID Asignado: {player_counter})", "CONNECT")
                
                # Leer mensaje de bienvenida / handshake inicial
                p_conn = PlayerConnection(client_sock, client_addr, player_counter)
                
                # Hilo para procesar el handshake y emparejamiento
                threading.Thread(target=self._handle_new_player, args=(p_conn,), daemon=True).start()

        except KeyboardInterrupt:
            log("Interrupción de teclado (Ctrl+C) recibida. Apagando servidor...", "SHUTDOWN")
        finally:
            self.stop()

    def _handle_new_player(self, p_conn: PlayerConnection) -> None:
        """Gestiona el handshake inicial y empareja al jugador."""
        try:
            # Recibir datos iniciales del jugador (ej. nombre)
            msg = p_conn.recv()
            if not msg:
                p_conn.close()
                return
            
            p_conn.name = msg.get("player_name", f"Almirante_{p_conn.player_id}")
            log(f"Handshake completado: {p_conn.name} ({p_conn.addr})", "HANDSHAKE")
            
            with self.waiting_lock:
                if self.waiting_player is None or not self.waiting_player.is_connected:
                    # Primer jugador esperando rival
                    self.waiting_player = p_conn
                    p_conn.send({
                        "type": protocol.MSG_WELCOME,
                        "player_id": p_conn.player_id,
                        "message": f"¡Bienvenido, {p_conn.name}! Esperando a que se conecte un oponente..."
                    })
                    log(f"{p_conn.name} en espera de oponente.", "LOBBY")
                else:
                    # Segundo jugador: Se forma una sala de juego
                    p1 = self.waiting_player
                    p2 = p_conn
                    self.waiting_player = None
                    self.room_counter += 1
                    
                    log(f"¡Emparejamiento exitoso! Sala #{self.room_counter}: {p1.name} vs {p2.name}", "LOBBY")
                    
                    room = GameRoom(self.room_counter, p1, p2)
                    room.start()
                    
        except Exception as e:
            log(f"Error en handshake con {p_conn.addr}: {e}", "ERROR")
            p_conn.close()

    def stop(self) -> None:
        """Apaga el servidor y cierra el socket principal."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        log("Servidor detenido y recursos de socket liberados.", "SHUTDOWN")


def main():
    parser = argparse.ArgumentParser(description="Servidor de Battleship con Sockets TCP")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Dirección IP de escucha (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto TCP (default: 8888)")
    args = parser.parse_args()

    server = BattleshipServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()
