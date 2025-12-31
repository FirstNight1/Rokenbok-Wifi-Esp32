// --- Application State ---
const state = {
    // Gamepad and controls
    gamepads: [],
    selectedGamepadIndex: 0,
    gamepadPollInterval: null,
    controlState: {}, // Tracks active controls to prevent redundant commands
    driveMode: 'tank', // 'tank' or 'dpad'
    mapping: {},

    // Vehicle Configuration
    vehicleConfig: {
        axisMotors: [],
        motorFunctions: [],
        logicFunctions: [],
        vehicleType: '',
    },

    // UI and View
    view: {
        mode: 'area', // 'area', 'fpv', 'pip'
        pipFlipped: false,
        areaIP: '',
        fpvIP: '',
    },

    // WebSocket
    ws: null,
    isConnected: false,

    // Mapping UI
    mappingActive: null, // { field, type, ... }
};

// --- Constants ---
const DEADZONE = 0.1;
const KEEPALIVE_INTERVAL = 100; // ms, for motor watchdog

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initUI();
    initGamepad();
    initWebSocket();
    loadConfiguration();
});

/**
 * Attaches all initial event listeners to UI elements.
 */
function initUI() {
    // Gamepad selection
    document.getElementById('rescan_gamepads_btn')?.addEventListener('click', scanGamepads);
    document.getElementById('gamepad_select')?.addEventListener('change', (e) => {
        state.selectedGamepadIndex = parseInt(e.target.value, 10);
        updateGamepadStatusUI();
    });

    // View controls
    document.getElementById('view_area_btn')?.addEventListener('click', () => setViewMode('area'));
    document.getElementById('view_fpv_btn')?.addEventListener('click', () => setViewMode('fpv'));
    document.getElementById('view_pip_btn')?.addEventListener('click', () => setViewMode('pip'));
    document.getElementById('flip_pip_btn')?.addEventListener('click', flipPIP);
    document.getElementById('save_ips_btn')?.addEventListener('click', saveCameraIPs);

    // Drive mode - ensure we only attach once
    const toggleBtn = document.getElementById('toggle_mode_btn');
    if (toggleBtn && !toggleBtn.dataset.initialized) {
        toggleBtn.addEventListener('click', toggleDriveMode);
        toggleBtn.dataset.initialized = 'true';
    }

    // Control Mapping - use addEventListener for consistency
    const mappingHeader = document.getElementById('control_mapping_header');
    if (mappingHeader && !mappingHeader.dataset.initialized) {
        mappingHeader.style.cursor = 'pointer';
        mappingHeader.addEventListener('click', () => {
            if (state.gamepads.length > 0) {
                renderMappingUI();
            } else {
                alert('No controller detected. Please connect a controller to map controls.');
            }
        });
        mappingHeader.dataset.initialized = 'true';
    }
}

/**
 * Sets up gamepad connection listeners and starts the polling loop.
 */
function initGamepad() {
    window.addEventListener('gamepadconnected', (e) => {
        scanGamepads();
    });
    window.addEventListener('gamepaddisconnected', (e) => {
        scanGamepads();
    });
    scanGamepads();
    // Start the main control loop
    if (state.gamepadPollInterval) clearInterval(state.gamepadPollInterval);
    state.gamepadPollInterval = setInterval(gamepadLoop, 50);
}

/**
 * Initializes the WebSocket connection.
 */
function initWebSocket() {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) return;

    const wsUrl = `ws://${location.host}/ws`;
    try {
        state.ws = new WebSocket(wsUrl);
        state.ws.onopen = () => {
            state.isConnected = true;
            updateConnectionStatusUI('Connected');
        };
        state.ws.onclose = () => {
            state.isConnected = false;
            updateConnectionStatusUI('Disconnected');
            // Optional: try to reconnect
            setTimeout(initWebSocket, 3000);
        };
        state.ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            state.isConnected = false;
            updateConnectionStatusUI('Error');
        };
        state.ws.onmessage = (event) => {
            // Handle incoming messages if needed
        };
    } catch (error) {
        console.error('WebSocket initialization failed:', error);
        updateConnectionStatusUI('Error');
    }
}

// --- Configuration Management ---

/**
 * Loads all configuration from the server.
 */
async function loadConfiguration() {
    try {
        const response = await fetch('/play?config=1');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const config = await response.json();

        // Load view config
        state.view.areaIP = config.area_ip || localStorage.getItem('area_ip') || '';
        state.view.fpvIP = config.fpv_ip || localStorage.getItem('fpv_ip') || '';
        state.view.mode = config.view_mode || 'area';
        state.view.pipFlipped = !!config.pip_flip;

        // Load control config
        state.driveMode = config.drive_mode || 'tank';
        state.mapping = config.mapping || {};

        // Load vehicle config
        state.vehicleConfig = {
            axisMotors: config.axis_motors || [],
            motorFunctions: config.motor_functions || [],
            logicFunctions: config.logic_functions || [],
            vehicleType: config.vehicle_type || '',
        };

        // Update UI with loaded config
        updateAllUI();

    } catch (error) {
        console.error('Failed to load configuration:', error);
    }
}

/**
 * Saves a specific part of the configuration to the server.
 * @param {string} action - The type of config to save ('save_view', 'save_mapping').
 * @param {object} payload - The data to save.
 */
async function saveConfiguration(action, payload) {
    try {
        const response = await fetch('/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, ...payload }),
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    } catch (error) {
        console.error(`Failed to save configuration for ${action}:`, error);
    }
}

// --- Gamepad Handling & Control Loop ---

/**
 * The main loop for polling the gamepad and sending control commands.
 */
function gamepadLoop() {
    if (state.gamepads.length === 0) {
        // If no gamepad, ensure all motors are stopped.
        stopAllMotors();
        return;
    }

    const gp = navigator.getGamepads()[state.selectedGamepadIndex];
    if (!gp) return;

    // Check if mapping modal is open - don't send controls to vehicle
    const mappingModal = document.getElementById('mapping_modal');
    const isModalOpen = mappingModal && mappingModal.style.display === 'block';

    // If mapping UI is open, check for input to map but don't send vehicle controls.
    if (state.mappingActive || isModalOpen) {
        if (state.mappingActive) {
            detectMappingInput(gp);
        }
        return; // Don't process regular controls while mapping modal is open
    }

    if (!state.isConnected) {
        stopAllMotors();
        return;
    }

    // Update UI with live gamepad data (optional, can be throttled)
    updateBrowserGamepadUI(gp);

    // Process controls based on drive mode
    if (state.driveMode === 'dpad') {
        processDpadMode(gp);
    } else {
        processTankMode(gp);
    }

    processMotorFunctions(gp);
    processLogicFunctions(gp);
}

/**
 * Scans for connected gamepads and updates the UI.
 */
function scanGamepads() {
    state.gamepads = Array.from(navigator.getGamepads()).filter(Boolean);
    updateGamepadDropdownUI();
    if (state.gamepads.length > 0 && state.selectedGamepadIndex >= state.gamepads.length) {
        state.selectedGamepadIndex = 0;
    }
    updateGamepadStatusUI();
}

/**
 * Processes controls for 'tank' drive mode.
 * @param {Gamepad} gp - The gamepad object.
 */
function processTankMode(gp) {
    state.vehicleConfig.axisMotors.forEach(motorName => {
        const axisMap = state.mapping[`axis_${motorName}_axis`];
        let power = 0;

        // 1. Check axis input first, ensuring the axis exists on the gamepad
        if (axisMap && axisMap.type === 'axis' && gp.axes.length > axisMap.index) {
            const rawValue = gp.axes[axisMap.index] || 0;
            if (Math.abs(rawValue) > DEADZONE) {
                power = rawValue * (axisMap.direction || 1);
            }
        }

        // 2. Check button overrides ONLY if axis is idle
        if (power === 0) {
            const fwdBtnMap = state.mapping[`axis_${motorName}_fwd`];
            const revBtnMap = state.mapping[`axis_${motorName}_rev`];

            // Check forward button, ensuring it exists on the gamepad
            if (fwdBtnMap && fwdBtnMap.type === 'button' && gp.buttons.length > fwdBtnMap.index && gp.buttons[fwdBtnMap.index]?.pressed) {
                power = 1.0;
            }
            // Check reverse button, ensuring it exists on the gamepad
            else if (revBtnMap && revBtnMap.type === 'button' && gp.buttons.length > revBtnMap.index && gp.buttons[revBtnMap.index]?.pressed) {
                power = -1.0;
            }
        }

        const dir = power >= 0 ? 'fwd' : 'rev';
        // Ensure power is a number and clamped between 0 and 100.
        const absPower = Math.max(0, Math.min(100, Math.abs(power || 0) * 100));

        processControl(`axis_${motorName}`, absPower > 0,
            () => sendMotorCommand(motorName, dir, absPower),
            () => sendMotorCommand(motorName, 'fwd', 0)
        );
    });
}

/**
 * Processes controls for 'dpad' drive mode.
 * @param {Gamepad} gp - The gamepad object.
 */
function processDpadMode(gp) {
    const { axisMotors } = state.vehicleConfig;
    const leftMotor = axisMotors.find(m => m.toLowerCase() === 'left');
    const rightMotor = axisMotors.find(m => m.toLowerCase() === 'right');

    if (leftMotor && rightMotor) {
        const fwd = isControlActive(gp, state.mapping['drive_dpad_fwd']);
        const rev = isControlActive(gp, state.mapping['drive_dpad_rev']);
        const left = isControlActive(gp, state.mapping['drive_dpad_left']);
        const right = isControlActive(gp, state.mapping['drive_dpad_right']);

        let leftPower = 0;
        let rightPower = 0;

        if (fwd) { leftPower = 1; rightPower = 1; }
        else if (rev) { leftPower = -1; rightPower = -1; }
        else if (left) { leftPower = -1; rightPower = 1; }
        else if (right) { leftPower = 1; rightPower = -1; }

        processControl(`dpad_left`, leftPower !== 0,
            () => sendMotorCommand(leftMotor, leftPower > 0 ? 'fwd' : 'rev', 100),
            () => sendMotorCommand(leftMotor, 'fwd', 0)
        );
        processControl(`dpad_right`, rightPower !== 0,
            () => sendMotorCommand(rightMotor, rightPower > 0 ? 'fwd' : 'rev', 100),
            () => sendMotorCommand(rightMotor, 'fwd', 0)
        );
    }

    // Handle other non-drive axis motors - they can accept variable power from axes
    const otherMotors = axisMotors.filter(m => m.toLowerCase() !== 'left' && m.toLowerCase() !== 'right');
    otherMotors.forEach(motorName => {
        const fwdMap = state.mapping[`axis_${motorName}_fwd`];
        const revMap = state.mapping[`axis_${motorName}_rev`];

        let power = 0;

        // Check for axis input first (variable power 0-100)
        if (fwdMap && fwdMap.type === 'axis' && gp.axes.length > fwdMap.index) {
            const rawValue = gp.axes[fwdMap.index] || 0;
            if (Math.abs(rawValue) > DEADZONE) {
                power = rawValue * (fwdMap.direction || 1);
            }
        } else if (revMap && revMap.type === 'axis' && gp.axes.length > revMap.index) {
            const rawValue = gp.axes[revMap.index] || 0;
            if (Math.abs(rawValue) > DEADZONE) {
                power = rawValue * (revMap.direction || 1) * -1; // Reverse direction
            }
        }

        // Check for button input (on/off only)
        if (power === 0) {
            if (fwdMap && fwdMap.type === 'button' && gp.buttons.length > fwdMap.index && gp.buttons[fwdMap.index]?.pressed) {
                power = 1.0;
            } else if (revMap && revMap.type === 'button' && gp.buttons.length > revMap.index && gp.buttons[revMap.index]?.pressed) {
                power = -1.0;
            }
        }

        const dir = power >= 0 ? 'fwd' : 'rev';
        const absPower = Math.max(0, Math.min(100, Math.abs(power || 0) * 100));

        processControl(`axis_${motorName}`, absPower > 0,
            () => sendMotorCommand(motorName, dir, absPower),
            () => sendMotorCommand(motorName, 'fwd', 0)
        );
    });
}

/**
 * Processes controls for all motor functions.
 * @param {Gamepad} gp - The gamepad object.
 */
function processMotorFunctions(gp) {
    state.vehicleConfig.motorFunctions.forEach(fnName => {
        const fwd = isControlActive(gp, state.mapping[`motorfn_${fnName}_fwd`]);
        const rev = isControlActive(gp, state.mapping[`motorfn_${fnName}_rev`]);

        let power = 0;
        if (fwd) power = 1;
        else if (rev) power = -1;

        const dir = power >= 0 ? 'fwd' : 'rev';

        processControl(`motorfn_${fnName}`, power !== 0,
            () => sendMotorCommand(fnName, dir, 100),
            () => sendMotorCommand(fnName, 'fwd', 0)
        );
    });
}

/**
 * Processes controls for all logic functions.
 * @param {Gamepad} gp - The gamepad object.
 */
function processLogicFunctions(gp) {
    state.vehicleConfig.logicFunctions.forEach(fnName => {
        const isActive = isControlActive(gp, state.mapping[`logicfn_${fnName}_btn`]);
        processControl(`logicfn_${fnName}`, isActive,
            () => sendLogicCommand(fnName, true),
            () => sendLogicCommand(fnName, false)
        );
    });
}


/**
 * Generic helper to check if a mapped control is active.
 * @param {Gamepad} gp - The gamepad object.
 * @param {object} mapObj - The mapping object for the control.
 * @returns {boolean} - True if the control is active.
 */
function isControlActive(gp, mapObj) {
    if (!mapObj) return false;
    if (mapObj.type === 'button') {
        // Ensure button exists on gamepad before checking
        if (gp.buttons.length > mapObj.index) {
            return gp.buttons[mapObj.index]?.pressed || false;
        }
        return false;
    }
    if (mapObj.type === 'axis') {
        // Ensure axis exists on gamepad before checking
        if (gp.axes.length > mapObj.index) {
            const val = gp.axes[mapObj.index] || 0;
            return mapObj.direction === 1 ? val > 0.7 : val < -0.7;
        }
        return false;
    }
    return false;
}

/**
 * Manages sending commands for a single control, handling state changes and keep-alives.
 * @param {string} key - A unique identifier for the control.
 * @param {boolean} isActive - Whether the control is currently active.
 * @param {function} sendActive - Function to call when the control is active.
 * @param {function} sendStop - Function to call when the control becomes inactive.
 */
function processControl(key, isActive, sendActive, sendStop) {
    const wasActive = state.controlState[key]?.active || false;
    const now = Date.now();

    if (isActive) {
        const lastSent = state.controlState[key]?.lastSent || 0;
        if (!wasActive || (now - lastSent >= KEEPALIVE_INTERVAL)) {
            sendActive();
            state.controlState[key] = { active: true, lastSent: now };
        }
    } else {
        if (wasActive) {
            sendStop();
            state.controlState[key] = { active: false, lastSent: now };
        }
    }
}

/**
 * Stops all motors by clearing the control state.
 */
function stopAllMotors() {
    Object.keys(state.controlState).forEach(key => {
        if (state.controlState[key].active) {
            if (key.startsWith('axis_') || key.startsWith('dpad_') || key.startsWith('motorfn_')) {
                const motorName = key.split('_')[1];
                // Use proper stop command instead of power 0
                if (state.isConnected) {
                    const command = { action: 'stop', name: motorName };
                    state.ws.send(JSON.stringify(command));
                }
            }
            state.controlState[key].active = false;
        }
    });
}


// --- WebSocket Command Senders ---

/**
 * Sends a command to a motor.
 * @param {string} name - The name of the motor.
 * @param {string} dir - The direction ('fwd' or 'rev').
 * @param {number} power - The power level (0 to 100).
 */
function sendMotorCommand(name, dir, power) {
    if (!state.isConnected) return;

    // Use stop action when power is 0, otherwise use set action
    if (power === 0) {
        const command = { action: 'stop', name };
        state.ws.send(JSON.stringify(command));
    } else {
        // Power is already in 0-100 range
        const clampedPower = Math.max(0, Math.min(100, power));
        const command = { action: 'set', name, dir, power: clampedPower };
        state.ws.send(JSON.stringify(command));
    }
}

/**
 * Sends a command for a logic function.
 * @param {string} id - The ID of the logic function.
 * @param {boolean} pressed - The state of the function.
 */
function sendLogicCommand(id, pressed) {
    if (!state.isConnected) return;
    const command = { action: 'logic_function', id, pressed };
    state.ws.send(JSON.stringify(command));
}


// --- UI Update Functions ---

/**
 * Updates all relevant UI parts based on the current state.
 */
function updateAllUI() {
    updateViewUI();
    updateDriveModeUI();
    updateConnectionStatusUI(state.isConnected ? 'Connected' : 'Disconnected');
    // Update IP input fields
    const areaIpEl = document.getElementById('area_ip');
    const fpvIpEl = document.getElementById('fpv_ip');
    if (areaIpEl) areaIpEl.value = state.view.areaIP;
    if (fpvIpEl) fpvIpEl.value = state.view.fpvIP;
}

function updateConnectionStatusUI(status) {
    const connEl = document.getElementById('conn_status');
    const vehicleEl = document.getElementById('vehicle_status_indicator');
    if (connEl) connEl.textContent = status;

    if (vehicleEl) {
        switch (status) {
            case 'Connected':
                vehicleEl.textContent = 'Vehicle Connected';
                vehicleEl.className = 'status-connected';
                break;
            case 'Disconnected':
                vehicleEl.textContent = 'Vehicle Disconnected';
                vehicleEl.className = 'status-disconnected';
                break;
            case 'Error':
                vehicleEl.textContent = 'Vehicle Error';
                vehicleEl.className = 'status-error';
                break;
        }
    }
}

function updateGamepadDropdownUI() {
    const select = document.getElementById('gamepad_select');
    if (!select) return;
    select.innerHTML = '';
    if (state.gamepads.length === 0) {
        const opt = document.createElement('option');
        opt.textContent = 'No controllers found';
        select.appendChild(opt);
        select.disabled = true;
    } else {
        state.gamepads.forEach((gp, index) => {
            const opt = document.createElement('option');
            opt.value = index;
            opt.textContent = gp.id;
            select.appendChild(opt);
        });
        select.disabled = false;
        select.value = state.selectedGamepadIndex;
    }
}

function updateGamepadStatusUI() {
    const status = document.getElementById('gamepad_status');
    if (!status) return;
    if (state.gamepads.length > 0) {
        const gp = state.gamepads[state.selectedGamepadIndex];
        status.textContent = `Selected: ${gp.id}`;
    } else {
        status.textContent = 'Press a button on a controller to connect.';
    }
}

function updateBrowserGamepadUI(gp) {
    const section = document.getElementById('browser_controller_section');
    if (!section) return;

    if (!gp) {
        section.innerHTML = '<div style="color:#888">No gamepad detected.</div>';
        return;
    }

    // Minimal display - just show connection status without verbose details
    section.innerHTML = '<div style="color:#4caf50;font-size:0.9em;">Controller Ready</div>';
}

function updateDriveModeUI() {
    const indicator = document.getElementById('drive_mode_indicator');
    if (indicator) {
        indicator.textContent = state.driveMode.charAt(0).toUpperCase() + state.driveMode.slice(1);
    }
}

// --- View and Camera Controls ---

function setViewMode(mode) {
    state.view.mode = mode;
    updateViewUI();
    saveConfiguration('save_view', {
        area_ip: state.view.areaIP,
        fpv_ip: state.view.fpvIP,
        view_mode: state.view.mode,
        pip_flip: state.view.pipFlipped,
    });
}

function flipPIP() {
    state.view.pipFlipped = !state.view.pipFlipped;
    updateViewUI();
    saveConfiguration('save_view', {
        area_ip: state.view.areaIP,
        fpv_ip: state.view.fpvIP,
        view_mode: state.view.mode,
        pip_flip: state.view.pipFlipped,
    });
}

function saveCameraIPs() {
    state.view.areaIP = document.getElementById('area_ip').value;
    state.view.fpvIP = document.getElementById('fpv_ip').value;
    localStorage.setItem('area_ip', state.view.areaIP);
    localStorage.setItem('fpv_ip', state.view.fpvIP);
    updateViewUI();
    saveConfiguration('save_view', {
        area_ip: state.view.areaIP,
        fpv_ip: state.view.fpvIP,
        view_mode: state.view.mode,
        pip_flip: state.view.pipFlipped,
    });
    alert('Camera IPs saved!');
}

function updateViewUI() {
    ['area', 'fpv', 'pip'].forEach(m => {
        const btn = document.getElementById(`view_${m}_btn`);
        if (btn) btn.classList.toggle('active', state.view.mode === m);
    });

    const container = document.getElementById('video_container');
    if (!container) return;
    container.innerHTML = ''; // Clear previous content

    const { mode, areaIP, fpvIP, pipFlipped } = state.view;

    const createVideoEl = (ip) => {
        if (!ip || ip.trim() === '') return '';
        return `<video class="video-full" src="http://${ip}/stream" controls autoplay muted loop playsinline></video>`;
    };

    if (mode === 'area') {
        container.innerHTML = createVideoEl(areaIP);
    } else if (mode === 'fpv') {
        container.innerHTML = createVideoEl(fpvIP);
    } else if (mode === 'pip') {
        const mainIP = pipFlipped ? fpvIP : areaIP;
        const pipIP = pipFlipped ? areaIP : fpvIP;
        container.innerHTML = `
            <div class="video-main">${createVideoEl(mainIP)}</div>
            <div class="video-pip">${createVideoEl(pipIP)}</div>
        `;
    }
}

// --- Drive Mode Toggle ---

function toggleDriveMode() {
    state.driveMode = (state.driveMode === 'tank') ? 'dpad' : 'tank';
    updateDriveModeUI();
    saveConfiguration('save_mapping', {
        mapping: state.mapping,
        drive_mode: state.driveMode,
    });
    alert(`Drive mode set to ${state.driveMode.charAt(0).toUpperCase() + state.driveMode.slice(1)}`);
    // If mapping UI is open, re-render it
    const modal = document.getElementById('mapping_modal');
    if (modal && modal.style.display === 'block') {
        renderMappingUI();
    }
}

// --- Control Mapping UI ---

/**
 * Renders the entire control mapping modal, building the UI from scratch.
 */
function renderMappingUI() {
    let modal = document.getElementById('mapping_modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'mapping_modal';
        // Using classes from play_page.css for styling
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span id="close_mapping_modal" class="modal-close">&times;</span>
                <h2 style="margin-top:0">Control Mapping</h2>
                <div id="vehicle_type_reminder" style="margin-bottom:10px; color:#888; font-size:1em;"></div>
                <div id="mapping_modal_body"></div>
                <div class="modal-footer">
                    <button id="save_mapping_btn" class="button">Save Mapping</button>
                </div>
            </div>`;
        document.body.appendChild(modal);
        document.getElementById('close_mapping_modal').addEventListener('click', hideMappingModal);
        document.getElementById('save_mapping_btn').addEventListener('click', saveCurrentMapping);
        modal.addEventListener('click', (e) => { if (e.target === modal) hideMappingModal(); });
    }

    document.getElementById('vehicle_type_reminder').textContent = `Vehicle Type: ${state.vehicleConfig.vehicleType || '(unknown)'}`;

    const body = document.getElementById('mapping_modal_body');
    body.innerHTML = buildMappingTableHTML();

    // Attach event listeners to the newly created "Set" buttons
    body.querySelectorAll('.map-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const field = e.target.dataset.field;
            startMapping(field);
        });
    });

    // Stop all motors when opening the modal to prevent unintended vehicle movement
    stopAllMotors();

    modal.style.display = 'block';
}

/**
 * Builds the HTML string for the mapping table based on current drive mode and vehicle config.
 * @returns {string} The HTML for the table.
 */
function buildMappingTableHTML() {
    const { axisMotors, motorFunctions, logicFunctions } = state.vehicleConfig;
    let html = '<table class="mapping-table">';

    // Header
    html += '<thead><tr><th>Function</th><th>Control</th><th>Mapped To</th></tr></thead>';
    html += '<tbody>';

    // Drive controls based on mode
    if (state.driveMode === 'tank') {
        html += '<tr><td colspan="3" class="mapping-header">Tank Drive</td></tr>';
        axisMotors.forEach(motor => {
            html += buildMappingRow(`axis_${motor}_axis`, `${motor} Axis`, 'Axis');
            html += buildMappingRow(`axis_${motor}_fwd`, `${motor} Fwd`, 'Button');
            html += buildMappingRow(`axis_${motor}_rev`, `${motor} Rev`, 'Button');
        });
    } else { // dpad mode
        html += '<tr><td colspan="3" class="mapping-header">DPad Drive</td></tr>';
        html += buildMappingRow('drive_dpad_fwd', 'Forward', 'Button/Axis');
        html += buildMappingRow('drive_dpad_rev', 'Reverse', 'Button/Axis');
        html += buildMappingRow('drive_dpad_left', 'Left', 'Button/Axis');
        html += buildMappingRow('drive_dpad_right', 'Right', 'Button/Axis');

        // Show other axis motors (non-left/right) for individual control in dpad mode
        const otherMotors = axisMotors.filter(m => m.toLowerCase() !== 'left' && m.toLowerCase() !== 'right');
        if (otherMotors.length > 0) {
            html += '<tr><td colspan="3" class="mapping-header">Other Axis Motors</td></tr>';
            otherMotors.forEach(motor => {
                html += buildMappingRow(`axis_${motor}_fwd`, `${motor} Fwd`, 'Button/Axis');
                html += buildMappingRow(`axis_${motor}_rev`, `${motor} Rev`, 'Button/Axis');
            });
        }
    }

    // Motor Functions
    if (motorFunctions.length > 0) {
        html += '<tr><td colspan="3" class="mapping-header">Motor Functions</td></tr>';
        motorFunctions.forEach(fn => {
            html += buildMappingRow(`motorfn_${fn}_fwd`, `${fn} Fwd`, 'Button/Axis');
            html += buildMappingRow(`motorfn_${fn}_rev`, `${fn} Rev`, 'Button/Axis');
        });
    }

    // Logic Functions
    if (logicFunctions.length > 0) {
        html += '<tr><td colspan="3" class="mapping-header">Logic Functions</td></tr>';
        logicFunctions.forEach(fn => {
            html += buildMappingRow(`logicfn_${fn}_btn`, fn, 'Button');
        });
    }

    html += '</tbody></table>';
    return html;
}

/**
 * Builds a single row for the mapping table.
 * @param {string} field - The mapping field ID (e.g., 'axis_left_fwd').
 * @param {string} label - The display name for the function (e.g., 'Left Fwd').
 * @param {string} type - The expected control type (e.g., 'Button').
 * @returns {string} The HTML for the table row.
 */
function buildMappingRow(field, label, type) {
    const mapping = state.mapping[field];
    let mappedTo = 'Not Set';
    if (mapping) {
        if (mapping.type === 'button') {
            mappedTo = `Button ${mapping.index}`;
        } else if (mapping.type === 'axis') {
            mappedTo = `Axis ${mapping.index} (${mapping.direction > 0 ? '+' : '-'})`;
        }
    }
    return `
        <tr>
            <td>${label}</td>
            <td><button class="map-btn" data-field="${field}">Set</button></td>
            <td id="map-label-${field}">${mappedTo}</td>
        </tr>
    `;
}

/**
 * Hides the mapping modal and cancels any pending mapping operation.
 */
function hideMappingModal() {
    const modal = document.getElementById('mapping_modal');
    if (modal) modal.style.display = 'none';
    if (state.mappingActive) {
        const label = document.getElementById(`map-label-${state.mappingActive.field}`);
        if (label) label.classList.remove('mapping-active');
        state.mappingActive = null;
    }

    // Stop all motors when closing the modal to prevent stuck controls
    stopAllMotors();
}

/**
 * Initiates the process of mapping a control.
 * @param {string} field - The mapping field ID to be mapped.
 */
function startMapping(field) {
    // If another mapping is active, cancel it first
    if (state.mappingActive) {
        const oldLabel = document.getElementById(`map-label-${state.mappingActive.field}`);
        if (oldLabel) oldLabel.classList.remove('mapping-active');
    }

    state.mappingActive = { field };
    const label = document.getElementById(`map-label-${field}`);
    label.textContent = 'Press a button or move an axis...';
    label.classList.add('mapping-active');

    // Set a timeout to automatically cancel if no input is received
    setTimeout(() => {
        if (state.mappingActive && state.mappingActive.field === field) {
            updateMappingUI(field, state.mapping[field]); // Revert to old mapping
            state.mappingActive = null;
        }
    }, 5000);
}

/**
 * Called from the main gamepad loop to detect input for an active mapping.
 * @param {Gamepad} gp - The gamepad object.
 */
function detectMappingInput(gp) {
    if (!state.mappingActive) return;

    // Check for button press
    for (let i = 0; i < gp.buttons.length; i++) {
        if (gp.buttons[i].pressed) {
            const newMapping = { type: 'button', index: i };
            state.mapping[state.mappingActive.field] = newMapping;
            updateMappingUI(state.mappingActive.field, newMapping);
            state.mappingActive = null;
            return;
        }
    }

    // Check for axis movement
    for (let i = 0; i < gp.axes.length; i++) {
        const value = gp.axes[i];
        if (Math.abs(value) > 0.8) {
            const newMapping = { type: 'axis', index: i, direction: Math.sign(value) };
            state.mapping[state.mappingActive.field] = newMapping;
            updateMappingUI(state.mappingActive.field, newMapping);
            state.mappingActive = null;
            return;
        }
    }
}

/**
 * Updates a single row in the mapping UI after a control has been set.
 * @param {string} field - The mapping field ID.
 * @param {object} mapping - The new mapping object.
 */
function updateMappingUI(field, mapping) {
    const label = document.getElementById(`map-label-${field}`);
    if (!label) return;

    label.classList.remove('mapping-active');
    let mappedTo = 'Not Set';
    if (mapping) {
        if (mapping.type === 'button') {
            mappedTo = `Button ${mapping.index}`;
        } else if (mapping.type === 'axis') {
            mappedTo = `Axis ${mapping.index} (${mapping.direction > 0 ? '+' : '-'})`;
        }
    }
    label.textContent = mappedTo;
}

/**
 * Saves the current mapping configuration to the server.
 */
function saveCurrentMapping() {
    saveConfiguration('save_mapping', {
        mapping: state.mapping,
        drive_mode: state.driveMode,
    });
    alert('Mapping saved!');
    hideMappingModal();
}
