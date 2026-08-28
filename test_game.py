"""
test_game.py - Suite de Pruebas Automatizadas para Battleship con Sockets TCP

Verifica:
1. Creación y enlace del socket servidor (bind, listen, accept).
2. Conexión de dos clientes concurrentes (connect, sendall, recv).
3. Enmarcado de mensajes y serialización JSON (Message Framing).
4. Fase de posicionamiento de flota (auto-place y validación en servidor).
5. Intercambio de ataques por turnos hasta victoria (Game Loop completo).
6. Detección y manejo controlado de desconexión abrupta.
"""

import time
import socket
import threading
import unittest

import protocol
from game_logic import Board, Ship, FLEET_SPEC, BOARD_SIZE, format_coord, parse_coord
from server import BattleshipServer

TEST_HOST = "127.0.0.1"


def get_free_port() -> int:
    """Obtiene un puerto TCP libre del sistema operativo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((TEST_HOST, 0))
        return s.getsockname()[1]


class TestBattleshipSockets(unittest.TestCase):

    def test_01_protocol_framing_and_special_chars(self):
        """Prueba que el protocolo con encabezado de 4 bytes mantenga la integridad de datos."""
        port = get_free_port()
        server_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_s.bind((TEST_HOST, port))
        server_s.listen(1)

        client_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_s.connect((TEST_HOST, port))
        conn_s, _ = server_s.accept()

        test_payload = {
            "type": "TEST",
            "message": "Mensaje de prueba con caracteres especiales ñ, á, é, í, ó, ú, 🚢",
            "numbers": list(range(500)),
            "nested": {"status": "OK", "code": 200}
        }

        # Enviar desde cliente y recibir en servidor
        protocol.send_msg(client_s, test_payload)
        received = protocol.recv_msg(conn_s)

        self.assertEqual(test_payload, received)

        # Enviar respuesta desde servidor a cliente
        response_payload = {"reply": "RECIBIDO_OK", "timestamp": time.time()}
        protocol.send_msg(conn_s, response_payload)
        client_received = protocol.recv_msg(client_s)

        self.assertEqual(response_payload, client_received)

        # Limpieza
        client_s.close()
        conn_s.close()
        server_s.close()

    def test_02_board_logic_and_placement(self):
        """Prueba las reglas de colocación de barcos y registro de impactos."""
        board = Board(BOARD_SIZE)
        
        # Colocación válida
        ship = board.place_ship("Destructor", 2, 0, 0, 'H', 'D')
        self.assertIsNotNone(ship)
        self.assertEqual(len(board.ships), 1)

        # Colocación inválida (solapamiento)
        overlap_ship = board.place_ship("Crucero", 3, 0, 1, 'V', 'C')
        self.assertIsNone(overlap_ship)

        # Colocación inválida (fuera de límites)
        out_of_bounds = board.place_ship("Portaaviones", 5, 8, 8, 'H', 'P')
        self.assertIsNone(out_of_bounds)

        # Prueba de ataque: TOCADO
        res1, sunk1 = board.receive_attack((0, 0))
        self.assertEqual(res1, "TOCADO")
        self.assertIsNone(sunk1)

        # Prueba de ataque repetido: ALREADY_SHOT
        res_repeat, _ = board.receive_attack((0, 0))
        self.assertEqual(res_repeat, "ALREADY_SHOT")

        # Prueba de ataque: HUNDIDO
        res2, sunk2 = board.receive_attack((0, 1))
        self.assertEqual(res2, "HUNDIDO")
        self.assertEqual(sunk2, "Destructor")
        self.assertTrue(board.all_ships_sunk())

    def test_03_full_game_simulation_and_victory(self):
        """Simula una partida completa de 2 jugadores por TCP hasta la victoria."""
        port = get_free_port()
        server = BattleshipServer(TEST_HOST, port)
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        try:
            # Conectar Jugador 1
            s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s1.connect((TEST_HOST, port))
            protocol.send_msg(s1, {"player_name": "Almirante_Alpha"})
            welcome1 = protocol.recv_msg(s1)
            self.assertEqual(welcome1.get("type"), protocol.MSG_WELCOME)

            # Conectar Jugador 2
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.connect((TEST_HOST, port))
            protocol.send_msg(s2, {"player_name": "Almirante_Beta"})

            # Ambos reciben MSG_START_PLACEMENT
            place1 = protocol.recv_msg(s1)
            place2 = protocol.recv_msg(s2)
            self.assertEqual(place1.get("type"), protocol.MSG_START_PLACEMENT)
            self.assertEqual(place2.get("type"), protocol.MSG_START_PLACEMENT)

            # Crear flotas conocidas para ambos
            b1 = Board(BOARD_SIZE)
            b1.auto_place_fleet()
            fleet1_payload = [{
                "name": s.name,
                "size": s.size,
                "start": format_coord(s.coords[0][0], s.coords[0][1]),
                "orientation": "V" if len(s.coords) > 1 and s.coords[1][0] != s.coords[0][0] else "H"
            } for s in b1.ships]

            b2 = Board(BOARD_SIZE)
            b2.auto_place_fleet()
            fleet2_payload = [{
                "name": s.name,
                "size": s.size,
                "start": format_coord(s.coords[0][0], s.coords[0][1]),
                "orientation": "V" if len(s.coords) > 1 and s.coords[1][0] != s.coords[0][0] else "H"
            } for s in b2.ships]

            # Enviar flotas al servidor
            protocol.send_msg(s1, {"type": protocol.MSG_PLACE_SHIPS, "ships": fleet1_payload})
            protocol.send_msg(s2, {"type": protocol.MSG_PLACE_SHIPS, "ships": fleet2_payload})

            # Recibir confirmación de colocación
            ack1 = protocol.recv_msg(s1)
            ack2 = protocol.recv_msg(s2)
            self.assertEqual(ack1.get("type"), protocol.MSG_PLACEMENT_ACK)
            self.assertEqual(ack2.get("type"), protocol.MSG_PLACEMENT_ACK)

            # Inicio de batalla
            battle1 = protocol.recv_msg(s1)
            battle2 = protocol.recv_msg(s2)
            self.assertEqual(battle1.get("type"), protocol.MSG_START_BATTLE)
            self.assertEqual(battle2.get("type"), protocol.MSG_START_BATTLE)

            # Extraer todas las coordenadas de los barcos de Beta para que Alpha gane rápidamente
            target_coords_alpha = []
            for ship in b2.ships:
                for r, c in ship.coords:
                    target_coords_alpha.append(format_coord(r, c))

            # Beta dispara a casillas fijas
            beta_targets = [format_coord(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE)]

            game_finished = False
            winner_name = None

            for _ in range(50):
                # Leer turno en s1 y s2
                msg_s1 = protocol.recv_msg(s1)
                msg_s2 = protocol.recv_msg(s2)

                if not msg_s1 or not msg_s2:
                    break

                if msg_s1.get("type") == protocol.MSG_GAME_OVER or msg_s2.get("type") == protocol.MSG_GAME_OVER:
                    game_finished = True
                    winner_name = (msg_s1 if msg_s1.get("type") == protocol.MSG_GAME_OVER else msg_s2).get("winner")
                    break

                if msg_s1.get("type") == protocol.MSG_YOUR_TURN:
                    # Le toca a Alpha
                    shot = target_coords_alpha.pop(0)
                    protocol.send_msg(s1, {"type": protocol.MSG_ATTACK, "coord": shot})
                elif msg_s2.get("type") == protocol.MSG_YOUR_TURN:
                    # Le toca a Beta
                    shot = beta_targets.pop(0)
                    protocol.send_msg(s2, {"type": protocol.MSG_ATTACK, "coord": shot})

                # Recibir resultado de ataque en ambos
                res1 = protocol.recv_msg(s1)
                res2 = protocol.recv_msg(s2)

                if res1 and res1.get("type") == protocol.MSG_GAME_OVER:
                    game_finished = True
                    winner_name = res1.get("winner")
                    break
                if res2 and res2.get("type") == protocol.MSG_GAME_OVER:
                    game_finished = True
                    winner_name = res2.get("winner")
                    break

            self.assertTrue(game_finished, "La partida debió concluir con la victoria de Alpha")
            self.assertEqual(winner_name, "Almirante_Alpha")

            s1.close()
            s2.close()
        finally:
            server.stop()

    def test_04_player_disconnect_handling(self):
        """Prueba que si un jugador se desconecta, el otro recibe la victoria por abandono."""
        port = get_free_port()
        server = BattleshipServer(TEST_HOST, port)
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        try:
            s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s1.connect((TEST_HOST, port))
            protocol.send_msg(s1, {"player_name": "Abandono_P1"})
            protocol.recv_msg(s1)

            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.connect((TEST_HOST, port))
            protocol.send_msg(s2, {"player_name": "Permanente_P2"})

            # Ambos reciben START_PLACEMENT
            protocol.recv_msg(s1)
            protocol.recv_msg(s2)

            # Desconectar s1 abruptamente
            s1.close()

            # Enviar colocación válida de s2
            b2 = Board(BOARD_SIZE)
            b2.auto_place_fleet()
            fleet2_payload = [{
                "name": s.name,
                "size": s.size,
                "start": format_coord(s.coords[0][0], s.coords[0][1]),
                "orientation": "V" if len(s.coords) > 1 and s.coords[1][0] != s.coords[0][0] else "H"
            } for s in b2.ships]
            protocol.send_msg(s2, {"type": protocol.MSG_PLACE_SHIPS, "ships": fleet2_payload})

            # s2 debe recibir ACK y luego GAME_OVER informando la desconexión del rival
            msg_ack = protocol.recv_msg(s2)
            self.assertEqual(msg_ack.get("type"), protocol.MSG_PLACEMENT_ACK)
            
            msg_over = protocol.recv_msg(s2)
            self.assertEqual(msg_over.get("type"), protocol.MSG_GAME_OVER)
            self.assertEqual(msg_over.get("winner"), "Permanente_P2")
            self.assertIn("desconectado", msg_over.get("reason", "").lower())

            s2.close()
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
