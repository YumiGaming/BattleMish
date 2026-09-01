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
            "board1": None,
            "board2": None,
            "current_turn": 1,
            "turn_count": 0,
            "lock": asyncio.Lock()
        }

    room = active_rooms[clean_room_id]

    async with room["lock"]:
        # Asignar posición de jugador en la sala
        if room["player1"] is None:
            player_num = 1
            session = WebPlayerSession(ws, username, 1)
            room["player1"] = session
        elif room["player2"] is None:
            player_num = 2
            session = WebPlayerSession(ws, username, 2)
            room["player2"] = session
        else:
            await ws.send_json({"type": "ERROR", "message": "La sala ya se encuentra llena."})
            await ws.close()
            return

    # Notificar bienvenida y estado de sala
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
        # Notificar al primer jugador que espere oponente
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
                
                defender_session = room["player2"] if player_num == 1 else room["player1"]
                if not defender_session or not defender_session.board:
                    continue
                
                result, sunk_ship = defender_session.board.receive_attack(coord_tuple)
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
                    "defender_ships_remaining": defender_session.board.ships_remaining()
                }
                
                await room["player1"].send_json(attack_payload)
                await room["player2"].send_json(attack_payload)
                
                # Verificar victoria
                if defender_session.board.all_ships_sunk():
                    room["status"] = "FINISHED"
                    duration = time.time() - room["start_time"]
                    
                    # Registrar partida en base de datos
                    try:
                        database.record_match_result(
                            room_id=clean_room_id,
                            player1_name=room["player1"].username,
                            player2_name=room["player2"].username,
                            winner_name=username,
                            turns=room["turn_count"],
                            duration_seconds=duration,
                            reason="Destrucción completa de la flota enemiga"
                        )
                    except Exception as e:
                        print(f"Error guardando partida en BD: {e}")
                    
                    game_over_payload = {
                        "type": "GAME_OVER",
                        "winner": username,
                        "loser": defender_session.username,
                        "turns": room["turn_count"],
                        "duration_seconds": round(duration, 1),
                        "reason": f"¡{username} ha destruido todos los barcos de {defender_session.username}!"
                    }
                    await room["player1"].send_json(game_over_payload)
                    await room["player2"].send_json(game_over_payload)
                else:
                    # Cambiar de turno
                    room["current_turn"] = 2 if player_num == 1 else 1
                    next_player = room["player2"] if room["current_turn"] == 2 else room["player1"]
                    waiting_player = room["player1"] if room["current_turn"] == 2 else room["player2"]
                    
                    await next_player.send_json({"type": "YOUR_TURN"})
                    await waiting_player.send_json({"type": "WAIT_TURN", "current_player": next_player.username})

    except WebSocketDisconnect:
        # Manejar desconexión
        other_session = room["player2"] if player_num == 1 else room["player1"]
        if player_num == 1:
            room["player1"] = None
        else:
            room["player2"] = None
        
        # Si la sala estaba esperando rival y el host se va, o si ambos se fueron, limpiar la sala inmediatamente
        if (room["status"] == "WAITING" and room["player1"] is None) or (room["player1"] is None and room["player2"] is None):
            active_rooms.pop(clean_room_id, None)

        if other_session and room["status"] in ("PLACEMENT", "BATTLE"):
            room["status"] = "FINISHED"
            try:
                database.record_match_result(
                    room_id=clean_room_id,
                    player1_name=username,
                    player2_name=other_session.username,
                    winner_name=other_session.username,
                    turns=room["turn_count"],
                    duration_seconds=time.time() - room.get("start_time", time.time()),
                    reason="Victoria por abandono / desconexión del oponente"
                )
            except Exception:
                pass
            
            await other_session.send_json({
                "type": "GAME_OVER",
                "winner": other_session.username,
                "loser": username,
                "reason": f"El oponente ({username}) se ha desconectado de la partida."
            })
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
