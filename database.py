"""
database.py - Capa de Persistencia SQLite para BattleMish

Gestiona usuarios, contraseñas seguras con hash + salt, estadísticas de juego
e historial detallado de partidas multijugador.
"""

import os
import time
import sqlite3
import hashlib
import secrets
from typing import Dict, List, Optional, Tuple, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battlemish.db")


def get_connection() -> sqlite3.Connection:
    """Retorna una conexión a la base de datos SQLite con soporte de diccionarios."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Inicializa las tablas de la base de datos si no existen."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla de Usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at REAL NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_games INTEGER DEFAULT 0
            )
        """)
        
        # Tabla de Historial de Partidas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                player1_name TEXT NOT NULL,
                player2_name TEXT NOT NULL,
                winner_name TEXT NOT NULL,
                turns INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                reason TEXT,
                created_at REAL NOT NULL
            )
        """)
        
        conn.commit()


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Genera un hash SHA-256 seguro con salting para la contraseña."""
    if salt is None:
        salt = secrets.token_hex(16)
    salted = f"{salt}:{password}".encode("utf-8")
    pwd_hash = hashlib.sha256(salted).hexdigest()
    return pwd_hash, salt


def register_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Registra un nuevo usuario en la base de datos.
    Retorna (éxito, mensaje, datos_usuario).
    """
    clean_user = username.strip()
    if len(clean_user) < 3 or len(clean_user) > 20:
        return False, "El nombre de usuario debe tener entre 3 y 20 caracteres.", None
    
    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres.", None

    pwd_hash, salt = hash_password(password)
    now = time.time()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (clean_user, pwd_hash, salt, now)
            )
            user_id = cursor.lastrowid
            conn.commit()
            
            user_data = {
                "id": user_id,
                "username": clean_user,
                "created_at": now,
                "wins": 0,
                "losses": 0,
                "total_games": 0,
                "win_rate": 0.0
            }
            return True, "Registro exitoso.", user_data
    except sqlite3.IntegrityError:
        return False, f"El nombre de usuario '{clean_user}' ya está en uso.", None
    except Exception as e:
        return False, f"Error en base de datos: {e}", None


def authenticate_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verifica las credenciales de un usuario.
    Retorna (éxito, mensaje, datos_usuario).
    """
    clean_user = username.strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (clean_user,))
        row = cursor.fetchone()
        
        if not row:
            return False, "Usuario o contraseña incorrectos.", None
        
        expected_hash, _ = hash_password(password, row["salt"])
        if expected_hash != row["password_hash"]:
            return False, "Usuario o contraseña incorrectos.", None
        
        total = row["total_games"]
        wins = row["wins"]
        win_rate = round((wins / total * 100), 1) if total > 0 else 0.0

        user_data = {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "wins": wins,
            "losses": row["losses"],
            "total_games": total,
            "win_rate": win_rate
        }
        return True, "Inicio de sesión exitoso.", user_data


def get_user_profile(username: str) -> Optional[Dict[str, Any]]:
    """Obtiene el perfil y estadísticas de un usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        
        total = row["total_games"]
        wins = row["wins"]
        win_rate = round((wins / total * 100), 1) if total > 0 else 0.0

        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "wins": wins,
            "losses": row["losses"],
            "total_games": total,
            "win_rate": win_rate
        }


def record_match_result(
    room_id: str,
    player1_name: str,
    player2_name: str,
    winner_name: str,
    turns: int,
    duration_seconds: float,
    reason: str = ""
) -> int:
    """
    Registra el resultado de una partida y actualiza las estadísticas de ambos jugadores.
    """
    now = time.time()
    loser_name = player2_name if winner_name == player1_name else player1_name

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Insertar partida en el historial
        cursor.execute("""
            INSERT INTO matches 
            (room_id, player1_name, player2_name, winner_name, turns, duration_seconds, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_id, player1_name, player2_name, winner_name, turns, duration_seconds, reason, now))
        match_id = cursor.lastrowid
        
        # 2. Actualizar estadísticas del ganador
        cursor.execute("""
            UPDATE users 
            SET wins = wins + 1, total_games = total_games + 1 
            WHERE username = ?
        """, (winner_name,))
        
        # 3. Actualizar estadísticas del perdedor
        cursor.execute("""
            UPDATE users 
            SET losses = losses + 1, total_games = total_games + 1 
            WHERE username = ?
        """, (loser_name,))
        
        conn.commit()
        return match_id


def get_user_match_history(username: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Obtiene el historial de partidas de un usuario."""
    clean_user = username.strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM matches 
            WHERE player1_name = ? OR player2_name = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (clean_user, clean_user, limit))
        
        rows = cursor.fetchall()
        history = []
        for r in rows:
            is_winner = (r["winner_name"] == clean_user)
            opponent = r["player2_name"] if r["player1_name"] == clean_user else r["player1_name"]
            
            history.append({
                "id": r["id"],
                "room_id": r["room_id"],
                "opponent": opponent,
                "winner": r["winner_name"],
                "is_winner": is_winner,
                "result": "VICTORIA" if is_winner else "DERROTA",
                "turns": r["turns"],
                "duration_seconds": round(r["duration_seconds"], 1),
                "reason": r["reason"],
                "created_at": r["created_at"]
            })
            
        return history


# Inicializar base de datos automáticamente al importar
init_db()
