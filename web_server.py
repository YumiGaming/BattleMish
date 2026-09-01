"""
web_server.py - Servidor Web FastAPI & Hub WebSocket para BattleMish

Provee endpoints REST para registro, autenticación, estadísticas e historial de partidas,
y gestiona salas de juego en tiempo real mediante WebSockets.
"""

import os
import time
import json
import random
import secrets
import asyncio
from typing import Dict, List, Optional, Any

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import database
from game_logic import Board, Ship, FLEET_SPEC, parse_coord, format_coord, BOARD_SIZE

JWT_SECRET = "battlemish_secret_key_9823471092834710"
JWT_ALGORITHM = "HS256"

app = FastAPI(title="BattleMish Web Server", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directorio de archivos estáticos
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


# --- Modelos Pydantic para API REST ---
class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateRoomRequest(BaseModel):
    room_name: Optional[str] = None
    is_private: Optional[bool] = False


def create_jwt_token(username: str) -> str:
    """Genera un token JWT para la sesión del usuario."""
    payload = {
        "sub": username,
        "iat": time.time(),
        "exp": time.time() + (30 * 24 * 3600)  # 30 días
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[str]:
    """Decodifica un token JWT y retorna el nombre de usuario."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


def get_current_username(authorization: Optional[str] = Header(None), token: Optional[str] = Query(None)) -> str:
    """Extrae el usuario autenticado desde el Header Authorization o query param."""
    raw_token = token
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ")[1]
    
    if not raw_token:
        raise HTTPException(status_code=401, detail="Token de autenticación no proporcionado.")
    
    username = decode_jwt_token(raw_token)
    if not username:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")
    
    return username


# --- Endpoints REST ---

@app.post("/api/register")
def api_register(req: RegisterRequest):
    success, msg, user_data = database.register_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    token = create_jwt_token(user_data["username"])
    return {"success": True, "message": msg, "user": user_data, "token": token}


@app.post("/api/login")
def api_login(req: LoginRequest):
    success, msg, user_data = database.authenticate_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=401, detail=msg)
    token = create_jwt_token(user_data["username"])
    return {"success": True, "message": msg, "user": user_data, "token": token}


@app.get("/api/me")
def api_me(username: str = Depends(get_current_username)):
    profile = database.get_user_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {"success": True, "user": profile}


@app.get("/api/history")
def api_history(username: str = Depends(get_current_username)):
    history = database.get_user_match_history(username)
    return {"success": True, "history": history}


@app.get("/api/rooms")
def api_list_rooms():
    """Retorna las salas disponibles que están esperando jugadores y limpia salas inactivas/abandonadas."""
    now = time.time()
    stale_keys = []
    
    for r_id, room in list(active_rooms.items()):
        # Si la sala lleva más de 30 minutos, o si no tiene host conectado en espera, o si ya terminó
        if room["status"] == "FINISHED" or (now - room.get("created_at", now) > 1800):
            stale_keys.append(r_id)
        elif room["status"] == "WAITING" and room["player1"] is None and (now - room.get("created_at", now) > 60):
            stale_keys.append(r_id)

    for k in stale_keys:
        active_rooms.pop(k, None)

    waiting_rooms = []
    for r_id, room in active_rooms.items():
        # Solo mostrar salas en espera con anfitrión conectado
        if room["status"] == "WAITING" and not room["is_private"] and room["player1"] is not None:
            host_name = room["player1"].username if hasattr(room["player1"], "username") else "Anónimo"
            waiting_rooms.append({
                "room_id": r_id,
                "room_name": room["name"],
                "host_name": host_name,
                "created_at": room["created_at"]
            })
            
    return {"success": True, "rooms": waiting_rooms}


@app.delete("/api/rooms/{room_id}")
def api_delete_room(room_id: str):
    """Permite cerrar o eliminar una sala activa o de testeo."""
    clean_id = room_id.strip().upper()
    if clean_id in active_rooms:
        room = active_rooms.pop(clean_id)
        # Si hay conexiones abiertas, cerrarlas
        for p in (room.get("player1"), room.get("player2")):
            if p and hasattr(p, "ws"):
                try:
                    asyncio.create_task(p.ws.close())
                except Exception:
                    pass
        return {"success": True, "message": f"Sala {clean_id} cerrada exitosamente."}
    return {"success": False, "message": f"La sala {clean_id} no existe o ya fue cerrada."}


@app.post("/api/rooms/clear-test")
def api_clear_test_rooms():
    """Elimina todas las salas en espera o de testeo."""
    cleared = list(active_rooms.keys())
    active_rooms.clear()
    return {"success": True, "message": f"Se han cerrado {len(cleared)} salas.", "cleared": cleared}



@app.post("/api/rooms/create")
def api_create_room(req: CreateRoomRequest, username: str = Depends(get_current_username)):
    """Genera una nueva sala con un código identificador único."""
    code = f"WAR-{random.randint(1000, 9999)}"
    room_name = req.room_name.strip() if req.room_name and req.room_name.strip() else f"Sala de {username}"
    
    active_rooms[code] = {
        "room_id": code,
        "name": room_name,
        "is_private": req.is_private,
        "status": "WAITING",
        "created_at": time.time(),
        "start_time": 0,
        "player1": None,
        "player2": None,
        "board1": None,
        "board2": None,
        "current_turn": 1,
        "turn_count": 0,
        "lock": asyncio.Lock()
    }
    
    return {"success": True, "room_id": code, "room_name": room_name}


# --- Hub de Salas y WebSockets ---

active_rooms: Dict[str, Dict[str, Any]] = {}


class WebPlayerSession:
    """Sesión de jugador conectada por WebSocket."""
    def __init__(self, ws: WebSocket, username: str, player_num: int):
        self.ws = ws
        self.username = username
        self.player_num = player_num
        self.ready = False
        self.board: Optional[Board] = None

    async def send_json(self, data: dict):
        try:
            await self.ws.send_json(data)
        except Exception:
            pass


@app.websocket("/ws/battle/{room_id}")
async def websocket_battle_endpoint(
    ws: WebSocket,
    room_id: str,
    token: Optional[str] = Query(None),
    guest_name: Optional[str] = Query(None)
):
    await ws.accept()
    
    # Identificar jugador
    username = None
    if token:
        username = decode_jwt_token(token)
    if not username:
        username = guest_name.strip() if guest_name and guest_name.strip() else f"Almirante_{random.randint(100, 999)}"

    # Verificar o crear sala
    clean_room_id = room_id.strip().upper()
    if clean_room_id not in active_rooms:
        active_rooms[clean_room_id] = {
            "room_id": clean_room_id,
            "name": f"Sala {clean_room_id}",
            "is_private": False,
            "status": "WAITING",
            "created_at": time.time(),
            "start_time": 0,
            "player1": None,
            "player2": None,
            "player1_name": None,
            "player2_name": None,
            "board1": None,
            "board2": None,
            "current_turn": 1,
            "turn_count": 0,
            "lock": asyncio.Lock(),
            "disconnect_task": None,
            "disconnected_player": None
        }

    room = active_rooms[clean_room_id]
    is_reconnect = False

    async with room["lock"]:
        if room["status"] in ("PLACEMENT", "BATTLE"):
            # Verificar si es una reconexión de jugador existente
            if room["player1"] is None and (room.get("player1_name") == username or room.get("player2_name") != username):
                player_num = 1
                session = WebPlayerSession(ws, username, 1)
                session.board = room.get("board1")
                session.ready = True if session.board else False
                room["player1"] = session
                room["player1_name"] = username
                is_reconnect = True
            elif room["player2"] is None and (room.get("player2_name") == username or room.get("player1_name") != username):
                player_num = 2
                session = WebPlayerSession(ws, username, 2)
                session.board = room.get("board2")
                session.ready = True if session.board else False
                room["player2"] = session
                room["player2_name"] = username
                is_reconnect = True
            else:
                await ws.send_json({"type": "ERROR", "message": "La partida ya está en curso y la sala se encuentra llena."})
                await ws.close()
                return
        else:
            # Estado WAITING normal
            if room["player1"] is None:
                player_num = 1
                session = WebPlayerSession(ws, username, 1)
                room["player1"] = session
                room["player1_name"] = username
            elif room["player2"] is None:
                player_num = 2
                session = WebPlayerSession(ws, username, 2)
                room["player2"] = session
                room["player2_name"] = username
            else:
                await ws.send_json({"type": "ERROR", "message": "La sala ya se encuentra llena."})
                await ws.close()
                return

    if is_reconnect:
        # Cancelar tarea de cuenta regresiva de 30 segundos
        if room.get("disconnect_task") and not room["disconnect_task"].done():
            room["disconnect_task"].cancel()
        room["disconnected_player"] = None

        other_session = room["player2"] if player_num == 1 else room["player1"]
        other_name = room.get("player2_name") if player_num == 1 else room.get("player1_name")

        # Notificar al oponente que volvió
        if other_session:
            await other_session.send_json({
                "type": "OPPONENT_RECONNECTED",
                "username": username,
                "message": f"¡{username} se ha reconectado! La batalla continúa."
            })

        my_board = room.get("board1") if player_num == 1 else room.get("board2")
        opp_board = room.get("board2") if player_num == 1 else room.get("board1")

        my_grid_cells = []
        radar_grid_cells = []
        if my_board and opp_board:
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if (r, c) in my_board.shots_received:
                        hit_ship = next((s for s in my_board.ships if (r, c) in s.coords), None)
                        if hit_ship:
                            my_grid_cells.append({"r": r, "c": c, "val": f"HIT_{hit_ship.name}"})
                        else:
                            my_grid_cells.append({"r": r, "c": c, "val": "MISS"})
                    else:
                        ship = next((s for s in my_board.ships if (r, c) in s.coords), None)
                        if ship:
                            my_grid_cells.append({"r": r, "c": c, "val": ship.name})

                    if (r, c) in opp_board.shots_received:
                        hit_ship = next((s for s in opp_board.ships if (r, c) in s.coords), None)
                        if hit_ship:
                            if hit_ship.is_sunk():
                                radar_grid_cells.append({"r": r, "c": c, "val": "SUNK"})
                            else:
                                radar_grid_cells.append({"r": r, "c": c, "val": "HIT"})
                        else:
                            radar_grid_cells.append({"r": r, "c": c, "val": "MISS"})

        await session.send_json({
            "type": "RECONNECT_SUCCESS",
            "room_id": clean_room_id,
            "player_num": player_num,
            "username": username,
            "opponent_name": other_name or "Oponente",
            "status": room["status"],
            "your_turn": (room["current_turn"] == player_num),
            "turn_count": room["turn_count"],
            "my_grid_cells": my_grid_cells,
            "radar_grid_cells": radar_grid_cells,
            "my_hp": my_board.ships_remaining() if my_board else 5,
            "opp_hp": opp_board.ships_remaining() if opp_board else 5
        })

    else:
        # Notificar bienvenida normal
        await session.send_json({
            "type": "JOIN_SUCCESS",
            "room_id": clean_room_id,
            "player_num": player_num,
            "username": username
        })

        # Si ambos jugadores ya están conectados, iniciar fase de posicionamiento
        if room["player1"] and room["player2"] and room["status"] == "WAITING":
            room["status"] = "PLACEMENT"
            room["start_time"] = time.time()
            
            start_payload_p1 = {
                "type": "START_PLACEMENT",
                "room_id": clean_room_id,
                "opponent_name": room["player2"].username,
                "fleet_spec": FLEET_SPEC,
                "board_size": BOARD_SIZE
            }
            start_payload_p2 = {
                "type": "START_PLACEMENT",
                "room_id": clean_room_id,
                "opponent_name": room["player1"].username,
                "fleet_spec": FLEET_SPEC,
                "board_size": BOARD_SIZE
            }
            await room["player1"].send_json(start_payload_p1)
            await room["player2"].send_json(start_payload_p2)
        else:
            await session.send_json({
                "type": "WAITING_OPPONENT",
                "message": f"Esperando a que otro jugador se una a la sala {clean_room_id}..."
            })

    try:
        while True:
            raw_data = await ws.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                continue
            
            mtype = data.get("type")
            
            # --- Chat en tiempo real ---
            if mtype == "CHAT":
                chat_payload = {
                    "type": "CHAT",
                    "sender": username,
                    "text": data.get("text", "")
                }
                if room["player1"]: await room["player1"].send_json(chat_payload)
                if room["player2"]: await room["player2"].send_json(chat_payload)

            # --- Colocación de barcos ---
            elif mtype == "PLACE_SHIPS":
                ships_data = data.get("ships", [])
                board = validate_web_fleet(ships_data)
                
                if board is None:
                    await session.send_json({
                        "type": "ERROR",
                        "message": "Configuración de flota inválida (solapamiento o fuera de límites)."
                    })
                else:
                    session.board = board
                    if player_num == 1:
                        room["board1"] = board
                    else:
                        room["board2"] = board
                    session.ready = True
                    await session.send_json({
                        "type": "PLACEMENT_ACK",
                        "message": "Flota confirmada con éxito por el servidor."
                    })
                    
                    # Notificar al rival que este jugador está listo
                    other = room["player2"] if player_num == 1 else room["player1"]
                    if other:
                        await other.send_json({
                            "type": "OPPONENT_READY",
                            "message": f"{username} ha posicionado su flota."
                        })
                    
                    # Si ambos colocaron barcos, comenzar batalla
                    if room["player1"] and room["player2"] and room["player1"].ready and room["player2"].ready:
                        room["status"] = "BATTLE"
                        room["current_turn"] = 1
                        
                        await room["player1"].send_json({
                            "type": "START_BATTLE",
                            "first_player": room["player1"].username,
                            "your_turn": True
                        })
                        await room["player2"].send_json({
                            "type": "START_BATTLE",
                            "first_player": room["player1"].username,
                            "your_turn": False
                        })

            # --- Disparo / Ataque ---
            elif mtype == "ATTACK":
                if room["status"] != "BATTLE":
                    continue
                
                # Verificar turno
                if room["current_turn"] != player_num:
                    await session.send_json({"type": "ERROR", "message": "No es tu turno de disparar."})
                    continue
                
                coord_str = data.get("coord", "")
                coord_tuple = parse_coord(coord_str)
                if coord_tuple is None:
                    await session.send_json({"type": "ERROR", "message": f"Coordenada inválida: {coord_str}"})
                    continue
                
                defender_board = room.get("board2") if player_num == 1 else room.get("board1")
                defender_session = room["player2"] if player_num == 1 else room["player1"]
                if not defender_board:
                    continue
                
                result, sunk_ship = defender_board.receive_attack(coord_tuple)
                if result == "ALREADY_SHOT":
                    await session.send_json({"type": "ERROR", "message": f"Ya has disparado a {coord_str}."})
                    continue
                
                room["turn_count"] += 1
                formatted_coord = format_coord(*coord_tuple)
                
                attack_payload = {
                    "type": "ATTACK_RESULT",
                    "attacker": username,
                    "attacker_num": player_num,
                    "coord": formatted_coord,
                    "result": result,  # "AGUA", "TOCADO", "HUNDIDO"
                    "sunk_ship": sunk_ship,
                    "defender_ships_remaining": defender_board.ships_remaining()
                }
                
                if room["player1"]: await room["player1"].send_json(attack_payload)
                if room["player2"]: await room["player2"].send_json(attack_payload)
                
                # Verificar victoria
                if defender_board.all_ships_sunk():
                    room["status"] = "FINISHED"
                    duration = time.time() - room.get("start_time", time.time())
                    
                    try:
                        database.record_match_result(
                            room_id=clean_room_id,
                            player1_name=room.get("player1_name", "P1"),
                            player2_name=room.get("player2_name", "P2"),
                            winner_name=username,
                            turns=room["turn_count"],
                            duration_seconds=duration,
                            reason="Destrucción completa de la flota enemiga"
                        )
                    except Exception as e:
                        print(f"Error guardando partida en BD: {e}")
                    
                    opp_name = room.get("player2_name") if player_num == 1 else room.get("player1_name")
                    game_over_payload = {
                        "type": "GAME_OVER",
                        "winner": username,
                        "loser": opp_name or "Oponente",
                        "turns": room["turn_count"],
                        "duration_seconds": round(duration, 1),
                        "reason": f"¡{username} ha destruido todos los barcos enemigos!"
                    }
                    if room["player1"]: await room["player1"].send_json(game_over_payload)
                    if room["player2"]: await room["player2"].send_json(game_over_payload)
                else:
                    # Cambiar de turno
                    room["current_turn"] = 2 if player_num == 1 else 1
                    next_player = room["player2"] if room["current_turn"] == 2 else room["player1"]
                    waiting_player = room["player1"] if room["current_turn"] == 2 else room["player2"]
                    
                    if next_player:
                        await next_player.send_json({"type": "YOUR_TURN"})
                    if waiting_player:
                        next_name = room.get("player2_name") if room["current_turn"] == 2 else room.get("player1_name")
                        await waiting_player.send_json({"type": "WAIT_TURN", "current_player": next_name or "Oponente"})

    except WebSocketDisconnect:
        # Manejar desconexión con cuenta regresiva de 30 segundos
        other_session = room["player2"] if player_num == 1 else room["player1"]
        if player_num == 1:
            room["player1"] = None
        else:
            room["player2"] = None

        if room["status"] == "WAITING":
            if room["player1"] is None and room["player2"] is None:
                active_rooms.pop(clean_room_id, None)
        elif room["status"] in ("PLACEMENT", "BATTLE"):
            if other_session:
                room["disconnected_player"] = player_num

                async def countdown_disconnect_task():
                    try:
                        for remaining_sec in range(30, 0, -1):
                            if clean_room_id not in active_rooms:
                                return
                            current_room = active_rooms[clean_room_id]
                            # Si el jugador se reconectó durante el countdown, salir limpiamente
                            if (player_num == 1 and current_room.get("player1") is not None) or (player_num == 2 and current_room.get("player2") is not None):
                                return

                            target_other = current_room.get("player2") if player_num == 1 else current_room.get("player1")
                            if target_other:
                                await target_other.send_json({
                                    "type": "OPPONENT_DISCONNECTED",
                                    "username": username,
                                    "seconds_left": remaining_sec,
                                    "message": f"El oponente ({username}) se ha desconectado. Esperando reconexión ({remaining_sec}s)..."
                                })
                            await asyncio.sleep(1)

                        # Si los 30s se agotaron sin reconexión
                        if clean_room_id in active_rooms:
                            final_room = active_rooms[clean_room_id]
                            if (player_num == 1 and final_room.get("player1") is None) or (player_num == 2 and final_room.get("player2") is None):
                                final_room["status"] = "FINISHED"
                                active_other = final_room.get("player2") if player_num == 1 else final_room.get("player1")
                                winner_name = active_other.username if active_other else "Oponente"

                                try:
                                    database.record_match_result(
                                        room_id=clean_room_id,
                                        player1_name=final_room.get("player1_name", "P1"),
                                        player2_name=final_room.get("player2_name", "P2"),
                                        winner_name=winner_name,
                                        turns=final_room.get("turn_count", 0),
                                        duration_seconds=time.time() - final_room.get("start_time", time.time()),
                                        reason=f"Victoria por abandono (tiempo de reconexión de 30s agotado para {username})"
                                    )
                                except Exception as e:
                                    print(f"Error registrando partida: {e}")

                                if active_other:
                                    await active_other.send_json({
                                        "type": "GAME_OVER",
                                        "winner": winner_name,
                                        "loser": username,
                                        "reason": f"El oponente ({username}) no se reconectó a tiempo (30s agotados)."
                                    })
                                active_rooms.pop(clean_room_id, None)
                    except asyncio.CancelledError:
                        pass

                room["disconnect_task"] = asyncio.create_task(countdown_disconnect_task())
            else:
                active_rooms.pop(clean_room_id, None)




def validate_web_fleet(ships_data: List[dict]) -> Optional[Board]:
    """Valida la colocación de barcos enviada desde el cliente web."""
    if not isinstance(ships_data, list) or len(ships_data) != len(FLEET_SPEC):
        return None
    
    board = Board(BOARD_SIZE)
    for spec in FLEET_SPEC:
        matching = [s for s in ships_data if s.get("name") == spec["name"] and s.get("size") == spec["size"]]
        if len(matching) != 1:
            return None
        
        s = matching[0]
        start_coord = s.get("start")
        orientation = s.get("orientation", "H").upper()
        
        coord_tuple = parse_coord(start_coord)
        if coord_tuple is None or orientation not in ('H', 'V'):
            return None
        
        r, c = coord_tuple
        ship = board.place_ship(spec["name"], spec["size"], r, c, orientation, spec["id"])
        if ship is None:
            return None
        
    return board


# Endpoint explícito para favicon.ico
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon no encontrado")


# Montar archivos estáticos
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
