"""
client.py - Cliente Interactivo de Battleship (Batalla Naval) con Sockets TCP

Proporciona una interfaz de consola rica en colores ANSI para conectarse al servidor,
configurar la flota de barcos (manual o aleatoria), visualizar el radar en tiempo real
y realizar ataques por turnos.

Uso de Sockets TCP:
    - socket.gethostbyname() / getaddrinfo(): Resolución de nombre de host o dominio a IP.
    - socket(): Creación del socket de flujo (AF_INET, SOCK_STREAM).
    - settimeout(): Configuración de tiempos de espera para la conexión y operaciones.
    - connect(): Establecimiento de la conexión con el servidor remoto.
    - sendall(): Envío íntegro de datos enmarcados (JSON).
    - recv(): Recepción continua de respuestas y eventos del juego.
    - shutdown() / close(): Cierre y liberación ordenada del socket.
"""

import os
import sys
import time
import socket
import argparse
from typing import Optional, List, Tuple

import protocol
from game_logic import (
    Board, Ship, FLEET_SPEC, BOARD_SIZE,
    parse_coord, format_coord,
    render_boards_side_by_side,
    ANSI_RESET, ANSI_BOLD, ANSI_CYAN, ANSI_GREEN,
    ANSI_RED, ANSI_YELLOW, ANSI_BLUE, ANSI_WHITE
)

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8888


def clear_screen() -> None:
    """Limpia la terminal de forma compatible con Windows y Unix."""
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    """Imprime el banner inicial de Battleship."""
    banner = f"""
{ANSI_CYAN}{ANSI_BOLD}
  ██████╗  █████╗ ████████╗████████╗██╗     ███████╗███████╗██╗  ██╗██╗██████╗ 
  ██╔══██╗██╔══██╗╚══██╔══╝╚══██╔══╝██║     ██╔════╝██╔════╝██║  ██║██║██╔══██╗
  ██████╔╝███████║   ██║      ██║   ██║     █████╗  ███████╗███████║██║██████╔╝
  ██╔══██╗██╔══██║   ██║      ██║   ██║     ██╔══╝  ╚════██║██╔══██║██║██╔═══╝ 
  ██████╔╝██║  ██║   ██║      ██║   ███████╗███████╗███████║██║  ██║██║██║     
  ╚═════╝ ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝     
{ANSI_RESET}{ANSI_YELLOW}        == TALLER DE REDES Y COMUNICACIÓN BASADA EN SOCKETS TCP =={ANSI_RESET}
"""
    print(banner)


class BattleshipClient:
    """Cliente de juego de Battleship."""
    def __init__(self, host: str, port: int, player_name: str = ""):
        self.host = host
        self.port = port
        self.player_name = player_name
        self.sock: Optional[socket.socket] = None
        self.player_id: Optional[int] = None
        self.opponent_name = "Oponente"
        self.board = Board(BOARD_SIZE)
        self.is_running = True

    def connect(self) -> bool:
        """Resuelve la dirección IP y establece la conexión TCP con el servidor."""
        print(f"\n{ANSI_CYAN}[SOCKET]{ANSI_RESET} Resolviendo dirección para '{self.host}'...")
        try:
            # 1. Resolver el nombre de host a IP mediante gethostbyname
            target_ip = socket.gethostbyname(self.host)
            print(f"{ANSI_CYAN}[SOCKET]{ANSI_RESET} IP resuelta: {target_ip}")
        except socket.gaierror as e:
            print(f"{ANSI_RED}[ERROR]{ANSI_RESET} No se pudo resolver el host '{self.host}': {e}")
            return False

        # 2. Crear el socket TCP (IPv4, STREAM)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # 3. Configurar timeout para el intento de conexión
        self.sock.settimeout(10.0)

        print(f"{ANSI_CYAN}[SOCKET]{ANSI_RESET} Conectando a {target_ip}:{self.port} (TCP)...")
        try:
            # 4. Establecer conexión con connect()
            self.sock.connect((target_ip, self.port))
            # Quitar timeout de conexión o dejar un timeout amplio para juego
            self.sock.settimeout(180.0)
            print(f"{ANSI_GREEN}[OK]{ANSI_RESET} ¡Conexión establecida con éxito!")
            return True
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            print(f"{ANSI_RED}[ERROR]{ANSI_RESET} No se pudo conectar al servidor en {target_ip}:{self.port}")
            print(f"Detalle del error: {e}")
            print("Verifica que el servidor esté ejecutándose y el puerto sea accesible.")
            return False

    def run(self) -> None:
        """Ciclo de vida principal del cliente."""
        clear_screen()
        print_banner()

        if not self.player_name:
            try:
                self.player_name = input(f"{ANSI_BOLD}Ingresa tu nombre de Almirante: {ANSI_RESET}").strip()
                if not self.player_name:
                    self.player_name = "Almirante_1"
            except (KeyboardInterrupt, EOFError):
                print("\nOperación cancelada por el usuario.")
                return

        if not self.connect():
            return

        try:
            # 1. Enviar mensaje de Handshake inicial con el nombre
            protocol.send_msg(self.sock, {
                "player_name": self.player_name
            })

            # 2. Bucle de mensajes del juego
            while self.is_running:
                msg = protocol.recv_msg(self.sock)
                if msg is None:
                    print(f"\n{ANSI_RED}[RED]{ANSI_RESET} La conexión con el servidor fue cerrada.")
                    break
                
                self._handle_server_message(msg)

        except KeyboardInterrupt:
            print(f"\n{ANSI_YELLOW}[SALIDA]{ANSI_RESET} Desconectándose del servidor...")
        except ConnectionError as e:
            print(f"\n{ANSI_RED}[ERROR DE RED]{ANSI_RESET} {e}")
        finally:
            self.close()

    def _handle_server_message(self, msg: dict) -> None:
        """Despacha y procesa los distintos tipos de mensajes recibidos."""
        mtype = msg.get("type")

        if mtype == protocol.MSG_WELCOME:
            self.player_id = msg.get("player_id")
            print(f"\n{ANSI_GREEN}[SERVIDOR]{ANSI_RESET} {msg.get('message')}")

        elif mtype == protocol.MSG_START_PLACEMENT:
            self.opponent_name = msg.get("opponent_name", "Oponente")
            print(f"\n{ANSI_GREEN}[SALA]{ANSI_RESET} ¡Oponente encontrado: {ANSI_BOLD}{self.opponent_name}{ANSI_RESET}!")
            time.sleep(1)
            self._placement_flow()

        elif mtype == protocol.MSG_PLACEMENT_ACK:
            print(f"\n{ANSI_GREEN}[VALIDACIÓN]{ANSI_RESET} {msg.get('message')}")

        elif mtype == protocol.MSG_START_BATTLE:
            first_player = msg.get("first_turn_player")
            clear_screen()
            print_banner()
            print(f"{ANSI_BOLD}{ANSI_CYAN}=== ¡COMIENZA LA BATALLA NAVAL! ==={ANSI_RESET}")
            print(f"Primer turno asignado a: {ANSI_BOLD}{ANSI_YELLOW}{first_player}{ANSI_RESET}\n")
            print(render_boards_side_by_side(self.board))

        elif mtype == protocol.MSG_YOUR_TURN:
            self._turn_attack_flow()

        elif mtype == protocol.MSG_WAIT_TURN:
            current_p = msg.get("current_player", "el oponente")
            print(f"\n{ANSI_YELLOW}>> Esperando el turno de {current_p}...{ANSI_RESET}")

        elif mtype == protocol.MSG_ATTACK_RESULT:
            self._handle_attack_result(msg)

        elif mtype == protocol.MSG_GAME_OVER:
            self._handle_game_over(msg)

        elif mtype == protocol.MSG_ERROR:
            print(f"\n{ANSI_RED}[ERROR DEL SERVIDOR]{ANSI_RESET} {msg.get('message')}")

    def _placement_flow(self) -> None:
        """Maneja la fase de colocación de barcos (manual o aleatoria)."""
        clear_screen()
        print_banner()
        print(f"{ANSI_BOLD}{ANSI_CYAN}=== FASE DE DESPLIEGUE DE LA FLOTA ==={ANSI_RESET}")
        print(f"Almirante: {ANSI_GREEN}{self.player_name}{ANSI_RESET} | Rival: {ANSI_RED}{self.opponent_name}{ANSI_RESET}\n")

        print("Selecciona cómo deseas posicionar tus barcos:")
        print(f"  {ANSI_BOLD}1){ANSI_RESET} Despliegue Automático / Aleatorio (Rápido)")
        print(f"  {ANSI_BOLD}2){ANSI_RESET} Despliegue Manual (Coordenada por coordenada)")

        choice = ""
        while choice not in ("1", "2"):
            try:
                choice = input(f"\n{ANSI_BOLD}Opción (1 o 2): {ANSI_RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                self.is_running = False
                return

        if choice == "1":
            self._auto_placement_flow()
        else:
            self._manual_placement_flow()

    def _auto_placement_flow(self) -> None:
        """Genera posiciones aleatorias y permite regenerar o confirmar."""
        while True:
            self.board.auto_place_fleet()
            clear_screen()
            print_banner()
            print(f"{ANSI_BOLD}{ANSI_CYAN}=== FLOTA DESPLEGADA AUTOMÁTICAMENTE ==={ANSI_RESET}\n")
            print(render_boards_side_by_side(self.board))
            
            print(f"\n¿Aceptas esta disposición?")
            print(f"  {ANSI_BOLD}S){ANSI_RESET} Sí, confirmar y enviar al servidor")
            print(f"  {ANSI_BOLD}R){ANSI_RESET} Reintentar / Re-generar")
            ans = input(f"\n{ANSI_BOLD}Opción (S/R): {ANSI_RESET}").strip().upper()
            if ans == "S" or ans == "SI" or ans == "Y":
                break

        self._send_fleet_to_server()

    def _manual_placement_flow(self) -> None:
        """Permite al usuario ingresar una por una las posiciones de cada barco."""
        self.board = Board(BOARD_SIZE)
        
        for spec in FLEET_SPEC:
            placed = False
            while not placed:
                clear_screen()
                print_banner()
                print(f"{ANSI_BOLD}{ANSI_CYAN}=== COLOCACIÓN MANUAL DE BARCOS ==={ANSI_RESET}\n")
                print(render_boards_side_by_side(self.board))
                print(f"\nColocando: {ANSI_BOLD}{ANSI_GREEN}{spec['name']}{ANSI_RESET} (Tamaño: {spec['size']} casillas)")
                print("Ingresa coordenada de inicio y orientación (H: Horizontal, V: Vertical).")
                print("Ejemplo: 'A1 H' o 'D5 V'")
                
                try:
                    entry = input(f"{ANSI_BOLD}Posición para {spec['name']}: {ANSI_RESET}").strip().split()
                    if len(entry) < 2:
                        print(f"{ANSI_RED}Formato incorrecto. Debe incluir coordenada y orientación (ej: 'B3 H'). Presiona Enter.{ANSI_RESET}")
                        input()
                        continue
                    
                    coord_str, orient = entry[0], entry[1].upper()
                    coord_tuple = parse_coord(coord_str)
                    if coord_tuple is None or orient not in ('H', 'V'):
                        print(f"{ANSI_RED}Coordenada u orientación inválida. Presiona Enter.{ANSI_RESET}")
                        input()
                        continue
                    
                    r, c = coord_tuple
                    ship = self.board.place_ship(spec["name"], spec["size"], r, c, orient, spec["id"])
                    if ship is None:
                        print(f"{ANSI_RED}El barco no cabe o se solapa con otro. Intenta en otra posición. Presiona Enter.{ANSI_RESET}")
                        input()
                        continue
                    
                    placed = True
                except (KeyboardInterrupt, EOFError):
                    self.is_running = False
                    return

        clear_screen()
        print_banner()
        print(f"{ANSI_BOLD}{ANSI_GREEN}¡Toda tu flota ha sido posicionada con éxito!{ANSI_RESET}\n")
        print(render_boards_side_by_side(self.board))
        self._send_fleet_to_server()

    def _send_fleet_to_server(self) -> None:
        """Serializa la flota y la envía al servidor para validación."""
        ships_payload = []
        for ship in self.board.ships:
            # Determinar start y orientación a partir de las coordenadas
            first_r, first_c = ship.coords[0]
            if len(ship.coords) > 1 and ship.coords[1][0] != first_r:
                orient = "V"
            else:
                orient = "H"
            
            ships_payload.append({
                "name": ship.name,
                "size": ship.size,
                "start": format_coord(first_r, first_c),
                "orientation": orient
            })

        print(f"\n{ANSI_CYAN}[SOCKET]{ANSI_RESET} Enviando configuración de flota al servidor...")
        protocol.send_msg(self.sock, {
            "type": protocol.MSG_PLACE_SHIPS,
            "ships": ships_payload
        })

    def _turn_attack_flow(self) -> None:
        """Solicita las coordenadas del ataque y las envía al servidor."""
        print(f"\n{ANSI_BOLD}{ANSI_GREEN}╔═══════════════════════════════════════════════════╗{ANSI_RESET}")
        print(f"{ANSI_BOLD}{ANSI_GREEN}║             ¡ES TU TURNO DE ATACAR!               ║{ANSI_RESET}")
        print(f"{ANSI_BOLD}{ANSI_GREEN}╚═══════════════════════════════════════════════════╝{ANSI_RESET}")
        
        valid = False
        while not valid and self.is_running:
            try:
                target = input(f"{ANSI_BOLD}Ingresa la coordenada a atacar (ej: B4, J10): {ANSI_RESET}").strip()
                if not target:
                    continue
                coord_tuple = parse_coord(target)
                if coord_tuple is None:
                    print(f"{ANSI_RED}Coordenada inválida. Debe ser Letra (A-J) + Número (1-10).{ANSI_RESET}")
                    continue
                
                # Comprobar si ya disparamos ahí
                if coord_tuple in self.board.shots_fired:
                    print(f"{ANSI_YELLOW}Ya has disparado previamente a {target.upper()}. Elige otra casilla.{ANSI_RESET}")
                    continue

                protocol.send_msg(self.sock, {
                    "type": protocol.MSG_ATTACK,
                    "coord": target.upper()
                })
                valid = True
            except (KeyboardInterrupt, EOFError):
                self.is_running = False
                break

    def _handle_attack_result(self, msg: dict) -> None:
        """Actualiza el tablero o radar con el resultado del ataque y lo dibuja."""
        attacker = msg.get("attacker")
        defender = msg.get("defender")
        coord_str = msg.get("coord")
        result = msg.get("result")
        sunk_ship = msg.get("sunk_ship")
        rem = msg.get("defender_ships_remaining")
        
        coord_tuple = parse_coord(coord_str)
        if coord_tuple is None:
            return

        clear_screen()
        print_banner()

        if attacker == self.player_name:
            # Nosotros atacamos: actualizar nuestro radar
            self.board.record_attack_result(coord_tuple, result)
            print(f"{ANSI_BOLD}{ANSI_CYAN}=== REPORTE DE TU ATAQUE ==={ANSI_RESET}")
            if result == "AGUA":
                print(f"Tu disparo a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_BLUE}¡AGUA! (Sin impacto){ANSI_RESET}")
            elif result == "TOCADO":
                print(f"Tu disparo a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_RED}{ANSI_BOLD}¡IMPACTO DIRECTO! (Barco enemigo averiado){ANSI_RESET}")
            elif result == "HUNDIDO":
                print(f"Tu disparo a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_RED}{ANSI_BOLD}¡HUNDIDO! Has destruido el {sunk_ship} enemigo.{ANSI_RESET}")
            print(f"Barcos restantes del enemigo: {ANSI_YELLOW}{rem}{ANSI_RESET}\n")
        else:
            # El oponente nos atacó: nuestro tablero ya fue modificado o lo actualizamos
            self.board.receive_attack(coord_tuple)
            print(f"{ANSI_BOLD}{ANSI_RED}=== ALERTA: ATAQUE ENEMIGO RECIBIDO ==={ANSI_RESET}")
            if result == "AGUA":
                print(f"{attacker} disparó a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_GREEN}¡Cayó al AGUA! Tus barcos están a salvo.{ANSI_RESET}")
            elif result == "TOCADO":
                print(f"{attacker} disparó a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_RED}{ANSI_BOLD}¡IMPACTO en uno de tus barcos!{ANSI_RESET}")
            elif result == "HUNDIDO":
                print(f"{attacker} disparó a {ANSI_BOLD}{coord_str}{ANSI_RESET}: {ANSI_RED}{ANSI_BOLD}¡TU {sunk_ship.upper()} HA SIDO HUNDIDO!{ANSI_RESET}")
            print(f"Tus barcos restantes: {ANSI_GREEN}{self.board.ships_remaining()}{ANSI_RESET}\n")

        print(render_boards_side_by_side(self.board))

    def _handle_game_over(self, msg: dict) -> None:
        """Muestra el resultado final de la partida."""
        winner = msg.get("winner")
        loser = msg.get("loser")
        reason = msg.get("reason", "")
        
        print("\n" + "=" * 60)
        if winner == self.player_name:
            print(f"{ANSI_BOLD}{ANSI_GREEN}            🏆 ¡¡¡ VICTORIA NAVAL !!! 🏆{ANSI_RESET}")
            print(f"{ANSI_GREEN}¡Felicitaciones Almirante {self.player_name}! Has ganado la batalla.{ANSI_RESET}")
        else:
            print(f"{ANSI_BOLD}{ANSI_RED}            💀 ¡¡¡ DERROTA NAVAL !!! 💀{ANSI_RESET}")
            print(f"{ANSI_RED}Tu flota ha sido derrotada por el Almirante {winner}.{ANSI_RESET}")
        
        print(f"Motivo: {reason}")
        print("=" * 60 + "\n")
        self.is_running = False

    def close(self) -> None:
        """Cierra el socket liberando los recursos de red."""
        self.is_running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        print(f"{ANSI_CYAN}[SOCKET]{ANSI_RESET} Conexión cerrada y recursos liberados.")


def main():
    parser = argparse.ArgumentParser(description="Cliente de Battleship con Sockets TCP")
    parser.add_argument("--host", default=DEFAULT_SERVER_HOST, help="Dirección IP o nombre de host del servidor (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT, help="Puerto del servidor (default: 8888)")
    parser.add_argument("--name", default="", help="Nombre del jugador")
    args = parser.parse_args()

    client = BattleshipClient(args.host, args.port, args.name)
    client.run()


if __name__ == "__main__":
    main()
