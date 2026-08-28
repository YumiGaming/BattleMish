"""
game_logic.py - Lógica de Juego y Reglas de Battleship (Batalla Naval)

Define la estructura de tableros, barcos, validación de coordenadas,
colocación manual o automática, y resolución de impactos/hundimientos.
"""

import random
from typing import Dict, List, Optional, Tuple, Set

# Dimensiones del tablero estándar
BOARD_SIZE = 10
ROWS = [chr(ord('A') + i) for i in range(BOARD_SIZE)]  # ['A', 'B', ..., 'J']
COLS = [str(i + 1) for i in range(BOARD_SIZE)]          # ['1', '2', ..., '10']

# Definición de la flota oficial de Battleship
FLEET_SPEC = [
    {"name": "Portaaviones", "size": 5, "id": "P"},
    {"name": "Acorazado",    "size": 4, "id": "A"},
    {"name": "Crucero",      "size": 3, "id": "C"},
    {"name": "Submarino",    "size": 3, "id": "S"},
    {"name": "Destructor",   "size": 2, "id": "D"},
]

# Símbolos del tablero
CELL_WATER = "~"
CELL_SHIP = "S"
CELL_HIT = "X"
CELL_MISS = "O"
CELL_RADAR_EMPTY = "."


def parse_coord(coord_str: str) -> Optional[Tuple[int, int]]:
    """
    Convierte una coordenada como 'A1', 'j10', 'B5' a tupla (fila, columna) [0..9].
    Retorna None si la coordenada no tiene formato válido o está fuera de límites.
    """
    if not coord_str or not isinstance(coord_str, str):
        return None
    
    clean = coord_str.strip().upper()
    if len(clean) < 2 or len(clean) > 3:
        return None
    
    row_char = clean[0]
    col_part = clean[1:]
    
    if row_char not in ROWS:
        return None
    
    try:
        col_num = int(col_part)
        if col_num < 1 or col_num > BOARD_SIZE:
            return None
    except ValueError:
        return None
    
    row_idx = ord(row_char) - ord('A')
    col_idx = col_num - 1
    return (row_idx, col_idx)


def format_coord(r: int, c: int) -> str:
    """Convierte índices (fila, col) a formato alfanumérico (ej: 'A1', 'J10')."""
    return f"{ROWS[r]}{c + 1}"


class Ship:
    """Representa una nave en el tablero."""
    def __init__(self, name: str, size: int, coords: List[Tuple[int, int]], ship_id: str = "S"):
        self.name = name
        self.size = size
        self.coords = coords  # Lista de (r, c)
        self.ship_id = ship_id
        self.hits: Set[Tuple[int, int]] = set()

    def is_sunk(self) -> bool:
        """Verifica si todos los segmentos del barco han sido impactados."""
        return len(self.hits) >= self.size

    def take_hit(self, coord: Tuple[int, int]) -> bool:
        """Registra un impacto si la coordenada pertenece a este barco."""
        if coord in self.coords:
            self.hits.add(coord)
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": self.size,
            "coords": [[r, c] for r, c in self.coords],
            "ship_id": self.ship_id,
            "hits": [[r, c] for r, c in self.hits]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Ship':
        ship = cls(data["name"], data["size"], [tuple(c) for c in data["coords"]], data.get("ship_id", "S"))
        ship.hits = set(tuple(h) for h in data.get("hits", []))
        return ship


class Board:
    """Representa el tablero de un jugador."""
    def __init__(self, size: int = BOARD_SIZE):
        self.size = size
        self.ships: List[Ship] = []
        # Tablero propio: contiene CELL_WATER, CELL_SHIP, CELL_HIT, CELL_MISS
        self.grid = [[CELL_WATER for _ in range(size)] for _ in range(size)]
        # Tablero radar (disparos hacia el enemigo): CELL_RADAR_EMPTY, CELL_HIT, CELL_MISS
        self.radar = [[CELL_RADAR_EMPTY for _ in range(size)] for _ in range(size)]
        self.shots_received: Set[Tuple[int, int]] = set()
        self.shots_fired: Set[Tuple[int, int]] = set()

    def can_place_ship(self, size: int, start_r: int, start_c: int, orientation: str) -> Optional[List[Tuple[int, int]]]:
        """
        Calcula las coordenadas de un barco y verifica que no salga del tablero
        ni se solape con barcos existentes.
        
        orientation: 'H' (Horizontal) o 'V' (Vertical)
        Retorna lista de (r, c) si es válido, o None si es inválido.
        """
        orientation = orientation.upper()
        coords: List[Tuple[int, int]] = []
        
        for i in range(size):
            if orientation == 'H':
                r = start_r
                c = start_c + i
            elif orientation == 'V':
                r = start_r + i
                c = start_c
            else:
                return None
            
            # Comprobar límites
            if r < 0 or r >= self.size or c < 0 or c >= self.size:
                return None
            
            # Comprobar solapamiento
            if self.grid[r][c] != CELL_WATER:
                return None
            
            coords.append((r, c))
            
        return coords

    def place_ship(self, name: str, size: int, start_r: int, start_c: int, orientation: str, ship_id: str = "S") -> Optional[Ship]:
        """Coloca un barco en el tablero si la posición es válida."""
        coords = self.can_place_ship(size, start_r, start_c, orientation)
        if coords is None:
            return None
        
        ship = Ship(name, size, coords, ship_id)
        self.ships.append(ship)
        for r, c in coords:
            self.grid[r][c] = CELL_SHIP
        return ship

    def auto_place_fleet(self) -> None:
        """Coloca toda la flota reglamentaria de manera aleatoria y válida."""
        self.ships.clear()
        self.grid = [[CELL_WATER for _ in range(self.size)] for _ in range(self.size)]
        
        for spec in FLEET_SPEC:
            placed = False
            while not placed:
                r = random.randint(0, self.size - 1)
                c = random.randint(0, self.size - 1)
                orient = random.choice(['H', 'V'])
                ship = self.place_ship(spec["name"], spec["size"], r, c, orient, spec["id"])
                if ship is not None:
                    placed = True

    def receive_attack(self, coord: Tuple[int, int]) -> Tuple[str, Optional[str]]:
        """
        Procesa un disparo recibido en `coord` (r, c).
        Retorna tupla: (resultado, nombre_barco_hundido_o_none)
        Resultados posibles: 'ALREADY_SHOT', 'AGUA', 'TOCADO', 'HUNDIDO'
        """
        r, c = coord
        if coord in self.shots_received:
            return ("ALREADY_SHOT", None)
        
        self.shots_received.add(coord)
        
        # Buscar si impactó algún barco
        for ship in self.ships:
            if coord in ship.coords:
                ship.take_hit(coord)
                self.grid[r][c] = CELL_HIT
                if ship.is_sunk():
                    return ("HUNDIDO", ship.name)
                return ("TOCADO", None)
        
        # No impactó ningún barco
        self.grid[r][c] = CELL_MISS
        return ("AGUA", None)

    def record_attack_result(self, coord: Tuple[int, int], result: str) -> None:
        """Registra en el radar el resultado de un disparo efectuado."""
        r, c = coord
        self.shots_fired.add(coord)
        if result in ("TOCADO", "HUNDIDO"):
            self.radar[r][c] = CELL_HIT
        else:
            self.radar[r][c] = CELL_MISS

    def all_ships_sunk(self) -> bool:
        """Retorna True si todos los barcos del tablero fueron destruidos."""
        if not self.ships:
            return False
        return all(ship.is_sunk() for ship in self.ships)

    def ships_remaining(self) -> int:
        """Retorna la cantidad de barcos aún a flote."""
        return sum(1 for ship in self.ships if not ship.is_sunk())

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "ships": [s.to_dict() for s in self.ships],
            "grid": self.grid,
            "radar": self.radar,
            "shots_received": [[r, c] for r, c in self.shots_received],
            "shots_fired": [[r, c] for r, c in self.shots_fired]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Board':
        board = cls(data.get("size", BOARD_SIZE))
        board.grid = data["grid"]
        board.radar = data["radar"]
        board.ships = [Ship.from_dict(s) for s in data["ships"]]
        board.shots_received = set(tuple(c) for c in data.get("shots_received", []))
        board.shots_fired = set(tuple(c) for c in data.get("shots_fired", []))
        return board


# --- Funciones de Renderizado ANSI para Consola ---

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_BLUE = "\033[34m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_WHITE = "\033[37m"
ANSI_BG_BLUE = "\033[44m"
ANSI_BG_DARK = "\033[40m"


def color_cell(cell: str, is_radar: bool = False) -> str:
    """Colorea un caracter de celda para una presentación visual atractiva."""
    if cell == CELL_WATER:
        return f"{ANSI_BLUE}~{ANSI_RESET}"
    elif cell == CELL_SHIP:
        return f"{ANSI_GREEN}{ANSI_BOLD}S{ANSI_RESET}"
    elif cell == CELL_HIT:
        return f"{ANSI_RED}{ANSI_BOLD}X{ANSI_RESET}"
    elif cell == CELL_MISS:
        return f"{ANSI_YELLOW}O{ANSI_RESET}"
    elif cell == CELL_RADAR_EMPTY:
        return f"{ANSI_WHITE}.{ANSI_RESET}"
    return cell


def render_boards_side_by_side(own_board: Board, show_ships: bool = True) -> str:
    """
    Genera un string formateado con los dos tableros lado a lado:
    [ TU FLOTA ]                         [ RADAR DE DISPAROS ]
    """
    lines = []
    
    header_col = "   " + " ".join(f"{c:>2}" for c in COLS)
    separator = "       "
    
    lines.append(f"{ANSI_BOLD}{ANSI_CYAN}         === TU FLOTA ==={ANSI_RESET}{separator}{ANSI_BOLD}{ANSI_YELLOW}      === RADAR ENEMIGO ==={ANSI_RESET}")
    lines.append(f"{ANSI_BOLD}{header_col}{separator}{header_col}{ANSI_RESET}")
    
    for r in range(BOARD_SIZE):
        row_letter = ROWS[r]
        
        # Fila del tablero propio
        own_row_cells = []
        for c in range(BOARD_SIZE):
            cell = own_board.grid[r][c]
            if not show_ships and cell == CELL_SHIP:
                cell = CELL_WATER
            own_row_cells.append(color_cell(cell))
        own_str = f" {row_letter}  " + "  ".join(own_row_cells)
        
        # Fila del radar
        radar_row_cells = []
        for c in range(BOARD_SIZE):
            cell = own_board.radar[r][c]
            radar_row_cells.append(color_cell(cell, is_radar=True))
        radar_str = f" {row_letter}  " + "  ".join(radar_row_cells)
        
        lines.append(f"{own_str}{separator}{radar_str}")
        
    lines.append("")
    lines.append(f"  {ANSI_GREEN}S{ANSI_RESET}=Barco propio | {ANSI_RED}X{ANSI_RESET}=Impacto | {ANSI_YELLOW}O{ANSI_RESET}=Agua | {ANSI_BLUE}~{ANSI_RESET}/{ANSI_WHITE}.{ANSI_RESET}=Desconocido")
    lines.append(f"  Barcos restantes: {ANSI_GREEN}{own_board.ships_remaining()}/{len(own_board.ships)}{ANSI_RESET}")
    return "\n".join(lines)
