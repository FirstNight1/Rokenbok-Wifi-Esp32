// Basic websocket helper for realtime control (extracted from play_page.py)
var ws = null;
function connectWS() {
    if (ws && ws.readyState === 1) return;
    try {
        ws = new WebSocket('ws://' + location.host + '/ws');
        ws.onopen = function () { console.log('WS open'); document.getElementById('conn_status').textContent = 'Connected'; };
        ws.onclose = function () { console.log('WS closed'); document.getElementById('conn_status').textContent = 'Disconnected'; };
        ws.onerror = function (e) { console.log('WS error', e); document.getElementById('conn_status').textContent = 'Error'; };
        ws.onmessage = function (m) { console.log('WS msg', m.data); };
    } catch (e) { console.log('WS init failed', e); document.getElementById('conn_status').textContent = 'Error'; }
}

function disconnectWS() {
    if (ws) { try { ws.close(); } catch (e) { } ws = null; }
    document.getElementById('conn_status').textContent = 'Disconnected';
}

function sendCmd(obj) {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); }
    else { console.log('WS not connected, cmd skipped', obj); }
}

// Placeholder: UI will call this with mapped values when implemented
function sendTest() {
    var left = document.getElementById('map_left').value;
    var right = document.getElementById('map_right').value;
    // example: drive both forward at 30%
    sendCmd({ action: 'set', name: left, dir: 'fwd', power: 0.3 });
    sendCmd({ action: 'set', name: right, dir: 'fwd', power: 0.3 });
}
