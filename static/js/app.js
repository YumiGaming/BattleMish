/**
 * app.js - Lógica de Cliente Web para BattleMish (Estilo Hoja de Cuaderno)
 * Gestión de estado, interfaz de usuario SPA, WebSockets y combate en tiempo real.
 */

const FLEET_SPEC = [
    { name: "Portaaviones", size: 5, id: "P" },
    { name: "Acorazado",    size: 4, id: "A" },
    { name: "Crucero",      size: 3, id: "C" },
    { name: "Submarino",    size: 3, id: "S" },
    { name: "Destructor",   size: 2, id: "D" }
];

const WATER_MISS_SVG = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round"><path d="M2 11c3-2 6 2 10 0s7 2 10 0M4 16c3-1.5 5 1.5 8 0s5 1.5 8 0"/></svg>`;

const SHIP_ICONS = {
    "Portaaviones": `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="2" y="7" width="20" height="10" rx="2"/><line x1="2" y1="12" x2="22" y2="12" stroke-dasharray="2 2"/><polygon points="14 3 19 3 17 7 12 7"/></svg>`,
    "Acorazado": `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M2 14 L22 14 L18 19 L6 19 Z"/><circle cx="8" cy="11" r="2"/><circle cx="16" cy="11" r="2"/><line x1="8" y1="9" x2="8" y2="5"/><line x1="16" y1="9" x2="16" y2="5"/></svg>`,
    "Crucero": `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 14 L21 14 L18 18 L6 18 Z"/><path d="M8 14 L8 9 L16 9 L16 14"/><line x1="12" y1="5" x2="12" y2="9"/></svg>`,
    "Submarino": `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><ellipse cx="12" cy="13" rx="9" ry="5"/><circle cx="12" cy="6" r="2"/><line x1="12" y1="8" x2="12" y2="10"/><line x1="3" y1="13" x2="1" y2="10"/><line x1="3" y1="13" x2="1" y2="16"/></svg>`,
    "Destructor": `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 13 L21 13 L17 17 L7 17 Z"/><line x1="12" y1="7" x2="12" y2="13"/><polygon points="12 7 16 9 12 11"/></svg>`
};


const ROWS = ['A','B','C','D','E','F','G','H','I','J'];
const COLS = ['1','2','3','4','5','6','7','8','9','10'];
const BOARD_SIZE = 10;

class BattleMishApp {
    constructor() {
        this.token = localStorage.getItem('bm_token') || null;
        this.user = null;
        this.currentRoomId = null;
        this.ws = null;
        this.playerNum = null;
        this.isHost = false;
        this.opponentName = "Oponente";

        // Estado de colocación
        this.placedShips = []; // { name, size, start: "A1", orientation: "H", coords: [[r,c]] }
        this.selectedShipIndex = 0;
        this.currentOrientation = "H"; // "H" o "V"
        this.myGrid = Array(10).fill(null).map(() => Array(10).fill(null));

        // Estado de combate
        this.radarGrid = Array(10).fill(null).map(() => Array(10).fill(null));
        this.isMyTurn = false;
        this.turnCount = 1;
        this.myShipsAlive = 5;
        this.oppShipsAlive = 5;

        this.initElements();
        this.bindEvents();
        this.checkAuthAndParams();
    }

    initElements() {
        // Vistas
        this.views = {
            lobby: document.getElementById('view-lobby'),
            waiting: document.getElementById('view-waiting'),
            placement: document.getElementById('view-placement'),
            battle: document.getElementById('view-battle')
        };

        // Modales
        this.modals = {
            auth: document.getElementById('modal-auth'),
            history: document.getElementById('modal-history'),
            gameover: document.getElementById('modal-gameover')
        };

        // Grids
        this.placementGridEl = document.getElementById('placement-grid');
        this.radarGridEl = document.getElementById('radar-grid');
        this.ownBattleGridEl = document.getElementById('own-battle-grid');
    }

    bindEvents() {
        // Teclas rápidas (R para rotar)
        window.addEventListener('keydown', (e) => {
            if (e.key === 'r' || e.key === 'R') {
                this.toggleOrientation();
            }
        });

        // Botón sonido
        document.getElementById('btn-toggle-sound').addEventListener('click', (e) => {
            const enabled = window.soundEngine.toggle();
            e.currentTarget.style.opacity = enabled ? '1' : '0.4';
        });

        // Autenticación
        document.getElementById('btn-open-login').addEventListener('click', () => this.openModal('auth'));
        document.getElementById('btn-close-auth').addEventListener('click', () => this.closeModal('auth'));
        document.getElementById('tab-login').addEventListener('click', () => this.switchAuthTab('login'));
        document.getElementById('tab-register').addEventListener('click', () => this.switchAuthTab('register'));
        document.getElementById('form-login').addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('form-register').addEventListener('submit', (e) => this.handleRegister(e));
        document.getElementById('btn-logout').addEventListener('click', () => this.logout());

        // Historial
        document.getElementById('btn-open-history').addEventListener('click', () => this.openHistoryModal());
        document.getElementById('btn-close-history').addEventListener('click', () => this.closeModal('history'));

        // Lobby & Salas
        document.getElementById('btn-create-room').addEventListener('click', () => this.createRoom());
        document.getElementById('btn-join-room').addEventListener('click', () => this.joinRoomFromInput());
        document.getElementById('btn-refresh-rooms').addEventListener('click', () => this.fetchPublicRooms());
        const btnClear = document.getElementById('btn-clear-rooms');
        if (btnClear) {
            btnClear.addEventListener('click', () => this.clearAllRooms());
        }
        document.getElementById('btn-copy-link').addEventListener('click', () => this.copyShareLink());
        document.getElementById('btn-leave-room').addEventListener('click', () => this.leaveRoom());


        // Colocación
        document.getElementById('btn-rotate-ship').addEventListener('click', () => this.toggleOrientation());
        document.getElementById('btn-auto-place').addEventListener('click', () => this.autoPlaceShips());
        document.getElementById('btn-reset-placement').addEventListener('click', () => this.resetPlacement());
        document.getElementById('btn-confirm-fleet').addEventListener('click', () => this.confirmFleet());

        // Game Over
        document.getElementById('btn-gameover-lobby').addEventListener('click', () => {
            this.closeModal('gameover');
            this.showView('lobby');
            this.fetchProfile();
        });
    }

    async checkAuthAndParams() {
        if (this.token) {
            await this.fetchProfile();
        }
        this.fetchPublicRooms();

        // Verificar si la URL tiene ?room=WAR-XXXX
        const urlParams = new URLSearchParams(window.location.search);
        const roomParam = urlParams.get('room');
        if (roomParam) {
            this.joinRoom(roomParam.toUpperCase());
        }
    }

    // --- Gestión de Vistas y Modales ---
    showView(viewName) {
        Object.values(this.views).forEach(v => v.classList.remove('active', 'hidden'));
        Object.keys(this.views).forEach(k => {
            if (k === viewName) {
                this.views[k].classList.add('active');
            } else {
                this.views[k].classList.add('hidden');
            }
        });
    }

    openModal(modalName) {
        if (this.modals[modalName]) {
            this.modals[modalName].classList.remove('hidden');
        }
    }

    closeModal(modalName) {
        if (this.modals[modalName]) {
            this.modals[modalName].classList.add('hidden');
        }
    }

    switchAuthTab(tab) {
        const isLogin = tab === 'login';
        document.getElementById('tab-login').classList.toggle('active', isLogin);
        document.getElementById('tab-register').classList.toggle('active', !isLogin);
        document.getElementById('form-login').classList.toggle('hidden', !isLogin);
        document.getElementById('form-register').classList.toggle('hidden', isLogin);
    }

    // --- Autenticación & Perfil ---
    async handleLogin(e) {
        e.preventDefault();
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        const errEl = document.getElementById('login-error');
        errEl.classList.add('hidden');

        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al iniciar sesión');

            this.token = data.token;
            this.user = data.user;
            localStorage.setItem('bm_token', this.token);
            this.updateUserUI();
            this.closeModal('auth');
            window.soundEngine.playSonar();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove('hidden');
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value;
        const errEl = document.getElementById('reg-error');
        errEl.classList.add('hidden');

        try {
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al registrarse');

            this.token = data.token;
            this.user = data.user;
            localStorage.setItem('bm_token', this.token);
            this.updateUserUI();
            this.closeModal('auth');
            window.soundEngine.playVictory();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove('hidden');
        }
    }

    async fetchProfile() {
        if (!this.token) return;
        try {
            const res = await fetch('/api/me', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (res.ok) {
                const data = await res.json();
                this.user = data.user;
                this.updateUserUI();
            } else {
                this.logout();
            }
        } catch (e) {
            console.error(e);
        }
    }

    updateUserUI() {
        const badge = document.getElementById('user-badge');
        const authBtns = document.getElementById('auth-buttons');
        if (this.user) {
            badge.classList.remove('hidden');
            authBtns.classList.add('hidden');
            document.getElementById('nav-username').textContent = this.user.username;
            document.getElementById('nav-stats').textContent = `${this.user.wins}V - ${this.user.losses}D (${this.user.win_rate}%)`;
        } else {
            badge.classList.add('hidden');
            authBtns.classList.remove('hidden');
        }
    }

    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('bm_token');
        this.updateUserUI();
    }

    async openHistoryModal() {
        if (!this.token) return;
        this.openModal('history');
        document.getElementById('profile-name').textContent = this.user.username;
        document.getElementById('stat-total').textContent = this.user.total_games;
        document.getElementById('stat-wins').textContent = this.user.wins;
        document.getElementById('stat-losses').textContent = this.user.losses;
        document.getElementById('stat-rate').textContent = `${this.user.win_rate}%`;

        const container = document.getElementById('history-container');
        container.innerHTML = '<div class="empty-state">Cargando registros...</div>';

        try {
            const res = await fetch('/api/history', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            if (data.history && data.history.length > 0) {
                container.innerHTML = '';
                data.history.forEach(m => {
                    const dateStr = new Date(m.created_at * 1000).toLocaleDateString() + ' ' + new Date(m.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const isWin = m.is_winner;
                    const item = document.createElement('div');
                    item.className = `history-item ${isWin ? 'win' : 'loss'}`;
                    item.innerHTML = `
                        <div>
                            <strong>[${isWin ? 'VICTORIA' : 'DERROTA'}]</strong> vs <em>${m.opponent}</em>
                            <div style="font-size:0.85rem; color:var(--pencil-gray); margin-top:2px;">${m.reason} // ${dateStr}</div>
                        </div>
                        <div style="text-align:right; font-family:var(--font-mono); font-size:0.9rem;">
                            <span>${m.turns} Turnos</span><br>
                            <span style="color:var(--pencil-light); font-size:0.8rem;">${m.duration_seconds}s</span>
                        </div>
                    `;
                    container.appendChild(item);
                });
            } else {
                container.innerHTML = '<div class="empty-state">No hay partidas registradas aún. ¡Juega tu primer duelo!</div>';
            }
        } catch (e) {
            container.innerHTML = '<div class="empty-state">Error al cargar historial.</div>';
        }
    }

    // --- Gestión de Salas ---
    async fetchPublicRooms() {
        try {
            const res = await fetch('/api/rooms');
            const data = await res.json();
            const list = document.getElementById('rooms-list');
            if (data.rooms && data.rooms.length > 0) {
                list.innerHTML = '';
                data.rooms.forEach(r => {
                    const item = document.createElement('div');
                    item.className = 'room-item';
                    item.innerHTML = `
                        <div>
                            <strong>${r.room_name}</strong>
                            <div style="font-size:0.8rem; color:var(--pencil-gray); font-family:var(--font-mono);">${r.room_id} // Host: ${r.host_name}</div>
                        </div>
                        <div style="display:flex; gap:6px; align-items:center;">
                            <button class="btn btn-stamp btn-xs" onclick="window.app.joinRoom('${r.room_id}')">Entrar</button>
                            <button class="btn btn-link btn-xs" style="color:var(--pencil-light); padding:2px 6px;" title="Cerrar esta sala" onclick="window.app.deleteRoom('${r.room_id}')">✕</button>
                        </div>
                    `;
                    list.appendChild(item);
                });
            } else {
                list.innerHTML = '<div class="empty-state">No hay hojas de partida en espera. ¡Crea una!</div>';
            }
        } catch (e) {
            console.error(e);
        }
    }

    async deleteRoom(roomId) {
        try {
            await fetch(`/api/rooms/${encodeURIComponent(roomId)}`, { method: 'DELETE' });
            this.fetchPublicRooms();
        } catch (e) {
            console.error(e);
        }
    }

    async clearAllRooms() {
        try {
            await fetch('/api/rooms/clear-test', { method: 'POST' });
            this.fetchPublicRooms();
        } catch (e) {
            console.error(e);
        }
    }

    async createRoom() {
        const nameInput = document.getElementById('input-room-name');
        const roomName = nameInput.value.trim();

        if (!this.token) {
            this.openModal('auth');
            return;
        }

        try {
            const res = await fetch('/api/rooms/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify({ room_name: roomName })
            });
            const data = await res.json();
            if (data.room_id) {
                this.isHost = true;
                this.joinRoom(data.room_id);
            }
        } catch (e) {
            alert('Error al crear sala: ' + e);
        }
    }

    joinRoomFromInput() {
        const idInput = document.getElementById('input-room-id');
        const code = idInput.value.trim().toUpperCase();
        if (code) {
            this.joinRoom(code);
        }
    }

    joinRoom(roomId) {
        this.currentRoomId = roomId;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl = `${protocol}//${window.location.host}/ws/battle/${roomId}`;
        
        if (this.token) {
            wsUrl += `?token=${encodeURIComponent(this.token)}`;
        } else {
            const guest = prompt("Ingresa tu nombre de Capitán para jugar:") || `Capitán_${Math.floor(Math.random()*1000)}`;
            wsUrl += `?guest_name=${encodeURIComponent(guest)}`;
        }

        this.connectWebSocket(wsUrl);
    }

    connectWebSocket(url) {
        if (this.ws) {
            this.ws.close();
        }

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log("WebSocket conectado.");
            window.soundEngine.playSonar();
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.handleWebSocketMessage(msg);
        };

        this.ws.onclose = () => {
            console.log("WebSocket desconectado.");
        };

        this.ws.onerror = (e) => {
            console.error("Error en WebSocket:", e);
        };
    }

    handleWebSocketMessage(msg) {
        const mtype = msg.type;

        if (mtype === 'JOIN_SUCCESS') {
            this.playerNum = msg.player_num;
            document.getElementById('display-room-code').textContent = this.currentRoomId;
            const fullLink = `${window.location.origin}/?room=${this.currentRoomId}`;
            document.getElementById('share-link-input').value = fullLink;
            document.getElementById('slot-p1-name').textContent = msg.username;
            this.showView('waiting');
        }
        else if (mtype === 'WAITING_OPPONENT') {
            // Quedarse en waiting
        }
        else if (mtype === 'START_PLACEMENT') {
            this.opponentName = msg.opponent_name || "Oponente";
            this.initPlacementView();
            this.showView('placement');
            window.soundEngine.playSonar();
        }
        else if (mtype === 'PLACEMENT_ACK') {
            document.getElementById('btn-confirm-fleet').disabled = true;
            document.getElementById('btn-confirm-fleet').textContent = 'Cuadrícula Lista - Esperando Rival...';
        }
        else if (mtype === 'OPPONENT_READY') {
            const oppStatus = document.getElementById('opponent-placement-status');
            oppStatus.className = 'status-indicator ready';
            document.getElementById('opp-place-text').textContent = `¡${this.opponentName} terminó de dibujar sus barcos!`;
        }
        else if (mtype === 'START_BATTLE') {
            this.isMyTurn = msg.your_turn;
            this.initBattleView();
            this.showView('battle');
            window.soundEngine.playShot();
        }
        else if (mtype === 'YOUR_TURN') {
            this.isMyTurn = true;
            this.updateTurnUI();
            window.soundEngine.playSonar();
        }
        else if (mtype === 'WAIT_TURN') {
            this.isMyTurn = false;
            this.updateTurnUI();
        }
        else if (mtype === 'ATTACK_RESULT') {
            this.handleAttackResult(msg);
        }
        else if (mtype === 'GAME_OVER') {
            this.handleGameOver(msg);
        }
        else if (mtype === 'ERROR') {
            alert(msg.message);
        }
    }

    copyShareLink() {
        const input = document.getElementById('share-link-input');
        input.select();
        navigator.clipboard.writeText(input.value);
        const btn = document.getElementById('btn-copy-link');
        btn.textContent = '¡Copiado!';
        setTimeout(() => btn.textContent = 'Copiar Link', 2000);
    }

    leaveRoom() {
        if (this.currentRoomId) {
            fetch(`/api/rooms/${encodeURIComponent(this.currentRoomId)}`, { method: 'DELETE' }).catch(() => {});
        }
        if (this.ws) this.ws.close();
        this.showView('lobby');
        this.fetchPublicRooms();
        window.history.pushState({}, document.title, window.location.pathname);
    }


    // --- Fase de Posicionamiento ---
    initPlacementView() {
        this.placedShips = [];
        this.selectedShipIndex = 0;
        this.currentOrientation = "H";
        this.myGrid = Array(10).fill(null).map(() => Array(10).fill(null));

        this.renderFleetSelector();
        this.renderPlacementGrid();
        this.updatePlacementUI();
    }

    renderFleetSelector() {
        const container = document.getElementById('fleet-selector');
        container.innerHTML = '';

        FLEET_SPEC.forEach((spec, idx) => {
            const isPlaced = this.placedShips.some(s => s.name === spec.name);
            const isSelected = this.selectedShipIndex === idx;
            const iconSvg = SHIP_ICONS[spec.name] || '';

            const card = document.createElement('div');
            card.className = `ship-card ${isSelected ? 'selected' : ''} ${isPlaced ? 'placed' : ''}`;
            card.onclick = () => {
                this.selectedShipIndex = idx;
                this.renderFleetSelector();
            };

            let blocksHtml = '';
            for (let i = 0; i < spec.size; i++) {
                blocksHtml += `<div class="ship-block"></div>`;
            }

            card.innerHTML = `
                <div style="display:flex; align-items:center; gap:10px;">
                    <div style="display:flex; align-items:center; justify-content:center; width:32px; height:32px; background:#e2e8f0; border-radius:4px; color:#1e293b;">
                        ${iconSvg}
                    </div>
                    <div>
                        <strong>${spec.name} (${spec.id})</strong>
                        <div style="font-size:0.85rem; color:var(--pencil-gray);">${spec.size} casillas ${isPlaced ? '[OK]' : ''}</div>
                    </div>
                </div>
                <div class="ship-blocks">${blocksHtml}</div>
            `;
            container.appendChild(card);
        });
    }

    toggleOrientation() {
        this.currentOrientation = this.currentOrientation === "H" ? "V" : "H";
        document.getElementById('rotate-label').textContent = this.currentOrientation === "H" ? "Horizontal" : "Vertical";
    }

    renderPlacementGrid() {
        this.placementGridEl.innerHTML = '';

        // Esquina vacía
        this.placementGridEl.appendChild(document.createElement('div'));
        
        // Cabecera Columnas (1..10)
        COLS.forEach(c => {
            const cell = document.createElement('div');
            cell.className = 'grid-header-cell';
            cell.textContent = c;
            this.placementGridEl.appendChild(cell);
        });

        // Filas (A..J)
        for (let r = 0; r < BOARD_SIZE; r++) {
            const headerRow = document.createElement('div');
            headerRow.className = 'grid-header-cell';
            headerRow.textContent = ROWS[r];
            this.placementGridEl.appendChild(headerRow);

            for (let c = 0; c < BOARD_SIZE; c++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.dataset.r = r;
                cell.dataset.c = c;

                if (this.myGrid[r][c]) {
                    const shipName = this.myGrid[r][c];
                    const spec = FLEET_SPEC.find(s => s.name === shipName);
                    const shipId = spec ? spec.id : 'S';
                    cell.classList.add('cell-ship', `cell-ship-${shipId}`);
                    cell.textContent = shipId;
                }

                cell.addEventListener('mouseenter', () => this.previewPlacement(r, c));
                cell.addEventListener('mouseleave', () => this.clearPreview());
                cell.addEventListener('click', () => this.placeCurrentShip(r, c));

                this.placementGridEl.appendChild(cell);
            }
        }
    }


    getShipCoords(r, c, size, orientation) {
        const coords = [];
        for (let i = 0; i < size; i++) {
            const nr = orientation === 'V' ? r + i : r;
            const nc = orientation === 'H' ? c + i : c;
            if (nr < 0 || nr >= BOARD_SIZE || nc < 0 || nc >= BOARD_SIZE) return null;
            coords.push([nr, nc]);
        }
        return coords;
    }

    canPlace(r, c, size, orientation) {
        const coords = this.getShipCoords(r, c, size, orientation);
        if (!coords) return false;
        
        const curShip = FLEET_SPEC[this.selectedShipIndex];
        return coords.every(([nr, nc]) => {
            const cellContent = this.myGrid[nr][nc];
            return !cellContent || cellContent === curShip.name;
        });
    }

    previewPlacement(r, c) {
        this.clearPreview();
        const spec = FLEET_SPEC[this.selectedShipIndex];
        if (!spec) return;

        const coords = this.getShipCoords(r, c, spec.size, this.currentOrientation);
        const valid = this.canPlace(r, c, spec.size, this.currentOrientation);

        if (coords) {
            coords.forEach(([nr, nc]) => {
                const cell = this.placementGridEl.querySelector(`[data-r="${nr}"][data-c="${nc}"]`);
                if (cell) {
                    cell.classList.add(valid ? 'cell-preview-valid' : 'cell-preview-invalid');
                }
            });
        }
    }

    clearPreview() {
        this.placementGridEl.querySelectorAll('.cell-preview-valid, .cell-preview-invalid').forEach(el => {
            el.classList.remove('cell-preview-valid', 'cell-preview-invalid');
        });
    }

    placeCurrentShip(r, c) {
        const spec = FLEET_SPEC[this.selectedShipIndex];
        if (!this.canPlace(r, c, spec.size, this.currentOrientation)) {
            return;
        }

        // Eliminar colocación previa del mismo barco si existe
        this.placedShips = this.placedShips.filter(s => s.name !== spec.name);
        for (let row = 0; row < BOARD_SIZE; row++) {
            for (let col = 0; col < BOARD_SIZE; col++) {
                if (this.myGrid[row][col] === spec.name) {
                    this.myGrid[row][col] = null;
                }
            }
        }

        const coords = this.getShipCoords(r, c, spec.size, this.currentOrientation);
        coords.forEach(([nr, nc]) => {
            this.myGrid[nr][nc] = spec.name;
        });

        this.placedShips.push({
            name: spec.name,
            size: spec.size,
            start: `${ROWS[r]}${c + 1}`,
            orientation: this.currentOrientation,
            coords: coords
        });

        window.soundEngine.playSonar();

        // Pasar al siguiente barco no colocado
        for (let i = 0; i < FLEET_SPEC.length; i++) {
            if (!this.placedShips.some(s => s.name === FLEET_SPEC[i].name)) {
                this.selectedShipIndex = i;
                break;
            }
        }

        this.renderFleetSelector();
        this.renderPlacementGrid();
        this.updatePlacementUI();
    }

    autoPlaceShips() {
        this.resetPlacement();
        FLEET_SPEC.forEach(spec => {
            let placed = false;
            while (!placed) {
                const orient = Math.random() < 0.5 ? 'H' : 'V';
                const r = Math.floor(Math.random() * BOARD_SIZE);
                const c = Math.floor(Math.random() * BOARD_SIZE);
                const coords = this.getShipCoords(r, c, spec.size, orient);
                
                if (coords && coords.every(([nr, nc]) => !this.myGrid[nr][nc])) {
                    coords.forEach(([nr, nc]) => this.myGrid[nr][nc] = spec.name);
                    this.placedShips.push({
                        name: spec.name,
                        size: spec.size,
                        start: `${ROWS[r]}${c + 1}`,
                        orientation: orient,
                        coords: coords
                    });
                    placed = true;
                }
            }
        });

        window.soundEngine.playSonar();
        this.renderFleetSelector();
        this.renderPlacementGrid();
        this.updatePlacementUI();
    }

    resetPlacement() {
        this.placedShips = [];
        this.myGrid = Array(10).fill(null).map(() => Array(10).fill(null));
        this.selectedShipIndex = 0;
        this.renderFleetSelector();
        this.renderPlacementGrid();
        this.updatePlacementUI();
    }

    updatePlacementUI() {
        const btn = document.getElementById('btn-confirm-fleet');
        const allPlaced = this.placedShips.length === FLEET_SPEC.length;
        btn.disabled = !allPlaced;
        btn.textContent = allPlaced ? 'Confirmar & Desplegar Flota' : `Dibuja todos tus barcos (${this.placedShips.length}/5)`;
    }

    confirmFleet() {
        if (this.placedShips.length !== FLEET_SPEC.length) return;
        this.ws.send(JSON.stringify({
            type: "PLACE_SHIPS",
            ships: this.placedShips
        }));
    }

    // --- Fase de Batalla ---
    initBattleView() {
        document.getElementById('hud-my-name').textContent = (this.user ? this.user.username : 'Capitán Tú');
        document.getElementById('hud-opp-name').textContent = this.opponentName;
        document.getElementById('battle-room-id').textContent = this.currentRoomId;

        this.radarGrid = Array(10).fill(null).map(() => Array(10).fill(null));
        this.myShipsAlive = 5;
        this.oppShipsAlive = 5;
        this.turnCount = 1;

        this.renderRadarGrid();
        this.renderOwnBattleGrid();
        this.updateTurnUI();
        this.updateFleetHpUI();
    }

    renderRadarGrid() {
        this.radarGridEl.innerHTML = '';
        this.radarGridEl.appendChild(document.createElement('div'));
        COLS.forEach(c => {
            const cell = document.createElement('div');
            cell.className = 'grid-header-cell';
            cell.textContent = c;
            this.radarGridEl.appendChild(cell);
        });

        for (let r = 0; r < BOARD_SIZE; r++) {
            const h = document.createElement('div');
            h.className = 'grid-header-cell';
            h.textContent = ROWS[r];
            this.radarGridEl.appendChild(h);

            for (let c = 0; c < BOARD_SIZE; c++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.dataset.r = r;
                cell.dataset.c = c;

                const val = this.radarGrid[r][c];
                if (val === 'HIT') {
                    cell.classList.add('cell-hit');
                    cell.textContent = '✕';
                } else if (val === 'MISS') {
                    cell.classList.add('cell-miss');
                    cell.innerHTML = WATER_MISS_SVG;
                } else if (val === 'SUNK') {
                    cell.classList.add('cell-sunk');
                    cell.textContent = '✕';
                }

                cell.addEventListener('click', () => this.fireShot(r, c));
                this.radarGridEl.appendChild(cell);
            }
        }
    }

    renderOwnBattleGrid() {
        this.ownBattleGridEl.innerHTML = '';
        this.ownBattleGridEl.appendChild(document.createElement('div'));
        COLS.forEach(c => {
            const cell = document.createElement('div');
            cell.className = 'grid-header-cell';
            cell.textContent = c;
            this.ownBattleGridEl.appendChild(cell);
        });

        for (let r = 0; r < BOARD_SIZE; r++) {
            const h = document.createElement('div');
            h.className = 'grid-header-cell';
            h.textContent = ROWS[r];
            this.ownBattleGridEl.appendChild(h);

            for (let c = 0; c < BOARD_SIZE; c++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.dataset.r = r;
                cell.dataset.c = c;

                const cellData = this.myGrid[r][c];
                if (cellData && typeof cellData === 'string' && !cellData.startsWith('HIT_') && cellData !== 'MISS') {
                    const spec = FLEET_SPEC.find(s => s.name === cellData);
                    const shipId = spec ? spec.id : 'S';
                    cell.classList.add('cell-ship', `cell-ship-${shipId}`);
                    cell.textContent = shipId;
                } else if (cellData && typeof cellData === 'string' && cellData.startsWith('HIT_')) {
                    cell.classList.add('cell-hit');
                    cell.textContent = '✕';
                } else if (cellData === 'MISS') {
                    cell.classList.add('cell-miss');
                    cell.innerHTML = WATER_MISS_SVG;
                }

                this.ownBattleGridEl.appendChild(cell);
            }
        }
    }


    fireShot(r, c) {
        if (!this.isMyTurn) {
            window.soundEngine.playWater();
            return;
        }
        if (this.radarGrid[r][c]) {
            return; // Ya disparado
        }

        const coord = `${ROWS[r]}${c + 1}`;
        window.soundEngine.playShot();
        this.ws.send(JSON.stringify({
            type: "ATTACK",
            coord: coord
        }));
    }

    handleAttackResult(msg) {
        const isMeAttacker = (msg.attacker_num === this.playerNum);
        const [rowLetter, ...colParts] = msg.coord;
        const r = ROWS.indexOf(rowLetter);
        const c = parseInt(colParts.join('')) - 1;

        if (isMeAttacker) {
            if (msg.result === 'AGUA') {
                this.radarGrid[r][c] = 'MISS';
                window.soundEngine.playWater();
                this.addCombatLog(`Disparo a ${msg.coord}: AGUA (Lápiz azul)`, 'log-miss');
            } else if (msg.result === 'TOCADO') {
                this.radarGrid[r][c] = 'HIT';
                window.soundEngine.playHit();
                this.addCombatLog(`Disparo a ${msg.coord}: ¡IMPACTO! (Tocado)`, 'log-hit');
            } else if (msg.result === 'HUNDIDO') {
                this.radarGrid[r][c] = 'SUNK';
                this.oppShipsAlive = msg.defender_ships_remaining;
                window.soundEngine.playHit();
                this.addCombatLog(`Disparo a ${msg.coord}: ¡HUNDIDO! Destruiste el ${msg.sunk_ship} rival.`, 'log-sunk');
            }
            this.renderRadarGrid();
        } else {
            // El oponente nos atacó
            if (msg.result === 'AGUA') {
                this.myGrid[r][c] = 'MISS';
                window.soundEngine.playWater();
                this.addCombatLog(`${msg.attacker} disparó a ${msg.coord}: Cayó al agua.`, 'log-miss');
            } else {
                this.myGrid[r][c] = `HIT_${this.myGrid[r][c] || 'S'}`;
                window.soundEngine.playHit();
                this.myShipsAlive = msg.defender_ships_remaining;
                if (msg.result === 'HUNDIDO') {
                    this.addCombatLog(`ALERTA: ${msg.attacker} tachó y hundió tu ${msg.sunk_ship}.`, 'log-hit');
                } else {
                    this.addCombatLog(`ALERTA: Disparo enemigo en ${msg.coord} impactó en tu barco.`, 'log-hit');
                }
            }
            this.renderOwnBattleGrid();
        }

        this.updateFleetHpUI();
    }

    updateTurnUI() {
        const banner = document.getElementById('turn-banner');
        const text = document.getElementById('turn-text');
        const counter = document.getElementById('turn-number');

        counter.textContent = this.turnCount;
        if (this.isMyTurn) {
            banner.className = 'turn-banner your-turn';
            text.textContent = '¡ES TU TURNO DE DISPARAR!';
        } else {
            banner.className = 'turn-banner opp-turn';
            text.textContent = `ESPERANDO AL OPONENTE (${this.opponentName})...`;
        }
    }

    updateFleetHpUI() {
        const myHp = document.getElementById('hud-my-hp');
        const oppHp = document.getElementById('hud-opp-hp');
        myHp.textContent = `Barcos a flote: ${this.myShipsAlive} / 5`;
        oppHp.textContent = `Barcos a flote: ${this.oppShipsAlive} / 5`;
    }

    addCombatLog(text, className = '') {
        const log = document.getElementById('combat-log');
        const entry = document.createElement('div');
        entry.className = `log-entry ${className}`;
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        entry.textContent = `[${time}] ${text}`;
        log.prepend(entry);
    }

    handleGameOver(msg) {
        const isWin = (msg.winner === (this.user ? this.user.username : document.getElementById('slot-p1-name').textContent));
        
        document.getElementById('gameover-title').textContent = isWin ? '¡VICTORIA EN EL CUADERNO!' : '¡DERROTA NAVAL!';
        document.getElementById('gameover-title').style.color = isWin ? '#15803d' : '#dc2626';
        document.getElementById('gameover-reason').textContent = msg.reason;
        document.getElementById('go-turns').textContent = msg.turns || this.turnCount;
        document.getElementById('go-duration').textContent = `${msg.duration_seconds || 0}s`;

        if (isWin) {
            window.soundEngine.playVictory();
        } else {
            window.soundEngine.playDefeat();
        }

        this.openModal('gameover');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new BattleMishApp();
});
