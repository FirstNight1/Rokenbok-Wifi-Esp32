// --- Application State ---
const state = {
    // Gamepad and controls
    gamepads: [],
    selectedGamepadIndex: 0,
    gamepadPollInterval: null,
    controlState: {}, // Tracks active controls to prevent redundant commands
    driveMode: 'dpad', // 'tank' or 'dpad'
    mapping: {},
    keyboardState: {}, // Tracks currently pressed keys for D-Pad mode
    slowModeActive: false, // Tracks if slow mode is currently active

    // Combined control state for efficient packet sending
    activeControls: {
        axisMotors: {},      // {motorName: {dir, power, useSlowMode}}
        functionMotors: {},  // {motorName: {dir, on}}
        logicFunctions: {}   // {funcId: pressed}
    },
    lastSentControls: '',    // JSON string of last sent state for comparison
    
    // Control packet timing
    pollCount: 0,            // Track polls for every-third sending
    lastControlActiveTime: 0, // Track when controls were last active for abandonment timeout
    controlAbandonmentMs: 60000, // 1 minute timeout
    
    // Axis jitter handling for tank mode
    tankModeSnapshot: null,  // Snapshot taken at intervals for tank mode
    tankModeSnapshotInterval: null,  // Interval for taking snapshots in tank mode

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
const KEEPALIVE_INTERVAL = 140; // ms, for motor watchdog (7 * 20ms polling)

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initUI();
    initGamepad();
    initWebSocket();
    loadConfiguration();
    initKeyboardMapping();
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

    // Control Mapping - use new edit button
    const editMappingBtn = document.getElementById('edit_mapping_btn');
    if (editMappingBtn && !editMappingBtn.dataset.initialized) {
        editMappingBtn.addEventListener('click', () => {
            const isDpadMode = state.driveMode === 'dpad';
            
            if (state.gamepads.length > 0) {
                // Controller connected - allow both controller and keyboard mapping
                renderMappingUI();
            } else if (isDpadMode) {
                // No controller but in D-Pad mode - allow keyboard-only mapping
                renderMappingUI();
            } else {
                // Tank mode without controller - not supported
                alert('Controller required for Tank mode mapping. Please connect a controller or switch to D-Pad mode for keyboard mapping.');
            }
        });
        editMappingBtn.dataset.initialized = 'true';
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
    state.gamepadPollInterval = setInterval(gamepadLoop, 20);
    
    // Initialize drive mode specific handling
    initDriveModeHandling();
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
            // Clear intervals when disconnected
            if (state.gamepadPollInterval) {
                clearInterval(state.gamepadPollInterval);
                state.gamepadPollInterval = null;
            }
            if (state.watchdogInterval) {
                clearInterval(state.watchdogInterval);
                state.watchdogInterval = null;
            }
            if (state.tankModeSnapshotInterval) {
                clearInterval(state.tankModeSnapshotInterval);
                state.tankModeSnapshotInterval = null;
            }
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
        state.driveMode = config.drive_mode || 'dpad';
        state.mapping = config.mapping || {};

        // Load vehicle config
        state.vehicleConfig = {
            axisMotors: config.axis_motors || [],
            motorFunctions: config.motor_functions || [],
            logicFunctions: config.logic_functions || [],
            vehicleType: config.vehicle_type || '',
            slowModeDisableFunctions: config.slow_mode_disable_functions || false,
        };

        // Update UI with loaded config
        updateAllUI();
        
        // Initialize drive mode handling after config is loaded
        if (typeof initDriveModeHandling === 'function') {
            initDriveModeHandling();
        }

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

/**
 * Initialize drive mode specific handling
 */
function initDriveModeHandling() {
    // Clear any existing tank mode snapshot interval
    if (state.tankModeSnapshotInterval) {
        clearInterval(state.tankModeSnapshotInterval);
        state.tankModeSnapshotInterval = null;
    }
    
    // Set up tank mode snapshot interval if in tank mode
    if (state.driveMode === 'tank') {
        state.tankModeSnapshotInterval = setInterval(processTankModeSnapshot, 80); // Every 80ms for tank mode
    }
}

/**
 * Process tank mode snapshot to reduce axis jitter
 */
function processTankModeSnapshot() {
    if (state.driveMode !== 'tank') return;
    
    // Take a snapshot of current active controls
    const currentSnapshot = JSON.stringify(state.activeControls);
    
    // Compare with last snapshot and send if different
    if (currentSnapshot !== state.tankModeSnapshot) {
        sendControlPacketIfNeeded();
        state.tankModeSnapshot = currentSnapshot;
    } else {
        // No change, but still need to check timing for logic functions
        sendControlPacketIfNeeded();
    }
}

// --- Gamepad Handling & Control Loop ---

/**
 * The main loop for polling the gamepad and sending control commands.
 */
function gamepadLoop() {
    // Get current gamepad
    const gp = state.gamepads.length > 0 ? navigator.getGamepads()[state.selectedGamepadIndex] : null;
    
    // Check if mapping modal is open - don't send controls to vehicle
    const mappingModal = document.getElementById('mapping_modal');
    const isModalOpen = mappingModal && mappingModal.style.display === 'block';

    // If mapping UI is open, check for input to map but don't send vehicle controls.
    if (state.mappingActive || isModalOpen) {
        if (state.mappingActive && gp) {
            detectMappingInput(gp);
        }
        return; // Don't process regular controls while mapping modal is open
    }

    if (!state.isConnected) {
        stopAllMotors();
        return;
    }

    // If no gamepad but in D-Pad mode, still allow keyboard controls
    const isDpadMode = state.driveMode === 'dpad';
    const hasValidInput = gp || (isDpadMode && Object.keys(state.keyboardState).length > 0);
    
    if (!hasValidInput) {
        // If no gamepad and not D-Pad mode (or no keyboard input), ensure all motors are stopped.
        stopAllMotors();
        return;
    }

    // Update UI with live gamepad data (optional, can be throttled)
    if (gp) {
        updateBrowserGamepadUI(gp);
    }

    // Process controls based on drive mode
    if (state.driveMode === 'dpad') {
        processDpadMode(gp); // gp can be null, processDpadMode will handle keyboard
    } else {
        processTankMode(gp); // Tank mode requires gamepad
    }

    processSlowMode(gp);
    processMotorFunctions(gp);
    processLogicFunctions(gp);
    
    // Send control packet based on drive mode and timing
    if (state.driveMode === 'dpad') {
        // D-pad mode: use immediate sending with every-third logic
        sendControlPacketIfNeeded();
    } else {
        // Tank mode: snapshot approach handled by interval to avoid axis jitter
        // The tankModeSnapshotInterval will handle sending packets
    }
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
            () => setMotorState(leftMotor, leftPower > 0 ? 'fwd' : 'rev', 100),
            () => setMotorState(leftMotor, 'fwd', 0)
        );
        processControl(`dpad_right`, rightPower !== 0,
            () => setMotorState(rightMotor, rightPower > 0 ? 'fwd' : 'rev', 100),
            () => setMotorState(rightMotor, 'fwd', 0)
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
            () => setMotorState(motorName, dir, absPower),
            () => setMotorState(motorName, 'fwd', 0)
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
            () => setMotorState(fnName, dir, 100),
            () => setMotorState(fnName, 'fwd', 0)
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
            () => setLogicState(fnName, true),
            () => setLogicState(fnName, false)
        );
    });
}

/**
 * Processes slow mode button
 * @param {Gamepad} gp - The gamepad object (can be null for keyboard)
 */
function processSlowMode(gp) {
    const slowBtnMap = state.mapping['slow_btn'];
    let isSlowPressed = false;
    
    // Check gamepad input
    if (gp && slowBtnMap) {
        if (slowBtnMap.type === 'button' && gp.buttons.length > slowBtnMap.index) {
            isSlowPressed = gp.buttons[slowBtnMap.index]?.pressed || false;
        } else if (slowBtnMap.type === 'axis' && gp.axes.length > slowBtnMap.index) {
            const axisValue = gp.axes[slowBtnMap.index] || 0;
            isSlowPressed = Math.abs(axisValue) > 0.5;
        }
    }
    
    // Update slow mode state
    const wasSlowActive = state.slowModeActive;
    state.slowModeActive = isSlowPressed;
    
    // If slow mode state changed, handle function motor disabling if configured
    if (wasSlowActive !== isSlowPressed) {
        handleSlowModeChange(isSlowPressed);
    }
}

/**
 * Handle slow mode state changes
 * @param {boolean} isSlowActive - Whether slow mode is now active
 */
function handleSlowModeChange(isSlowActive) {
    // Check if slow mode should disable function motors
    const shouldDisableFunctions = state.vehicleConfig.slowModeDisableFunctions;
    
    if (shouldDisableFunctions && isSlowActive) {
        // Stop all function motors when slow mode activates
        state.vehicleConfig.motorFunctions.forEach(fnName => {
            setMotorState(fnName, 'fwd', 0); // Stop motor
        });
    }
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
        if (gp && gp.buttons.length > mapObj.index) {
            return gp.buttons[mapObj.index]?.pressed || false;
        }
        return false;
    }
    
    if (mapObj.type === 'axis') {
        // Ensure axis exists on gamepad before checking
        if (gp && gp.axes.length > mapObj.index) {
            const val = gp.axes[mapObj.index] || 0;
            return mapObj.direction === 1 ? val > 0.7 : val < -0.7;
        }
        return false;
    }
    
    if (mapObj.type === 'key') {
        // Check if the mapped key is currently pressed
        return state.keyboardState[mapObj.code] || false;
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
    // Clear all active controls
    state.activeControls.axisMotors = {};
    state.activeControls.functionMotors = {};
    state.activeControls.logicFunctions = {};
    
    // Clear old control state for compatibility
    Object.keys(state.controlState).forEach(key => {
        state.controlState[key].active = false;
    });
    
    // Send the cleared state immediately
    sendControlPacket();
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

    // Check if this is a function motor and slow mode should block it
    const isAxisMotor = state.vehicleConfig.axisMotors.includes(name);
    const isFunctionMotor = state.vehicleConfig.motorFunctions.includes(name);
    const shouldDisableFunctions = state.vehicleConfig.slowModeDisableFunctions;
    
    if (isFunctionMotor && state.slowModeActive && shouldDisableFunctions && power > 0) {
        // Block function motor commands when slow mode is active and configured to disable them
        return;
    }

    // Use stop action when power is 0, otherwise use set action
    if (power === 0) {
        const command = { action: 'stop', name };
        state.ws.send(JSON.stringify(command));
    } else {
        // Power is already in 0-100 range
        const clampedPower = Math.max(0, Math.min(100, power));
        
        // For axis motors, add slow mode flag if active
        const command = { 
            action: 'set', 
            name, 
            dir, 
            power: clampedPower,
            useSlowMode: isAxisMotor && state.slowModeActive
        };
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

/**
 * Updates the active control state for a motor command.
 * @param {string} name - The name of the motor.
 * @param {string} dir - The direction ('fwd' or 'rev').
 * @param {number} power - The power level (0 to 100).
 */
function updateMotorState(name, dir, power) {
    // Check if this is an axis motor or function motor
    const isAxisMotor = state.vehicleConfig.axisMotors.includes(name);
    const isFunctionMotor = state.vehicleConfig.motorFunctions.includes(name);
    
    if (isAxisMotor) {
        if (power === 0) {
            // Remove from active controls when stopped
            delete state.activeControls.axisMotors[name];
        } else {
            // Check if this is a function motor and slow mode should block it
            const shouldDisableFunctions = state.vehicleConfig.slowModeDisableFunctions;
            if (isFunctionMotor && state.slowModeActive && shouldDisableFunctions) {
                // Don't add function motor commands when slow mode blocks them
                return;
            }
            
            state.activeControls.axisMotors[name] = {
                dir: dir,
                power: power,
                useSlowMode: state.slowModeActive
            };
        }
    } else if (isFunctionMotor) {
        // Check if this is a function motor and slow mode should block it
        const shouldDisableFunctions = state.vehicleConfig.slowModeDisableFunctions;
        if (state.slowModeActive && shouldDisableFunctions && power > 0) {
            // Don't add function motor commands when slow mode blocks them
            return;
        }
        
        if (power === 0) {
            // Remove from active controls when stopped
            delete state.activeControls.functionMotors[name];
        } else {
            state.activeControls.functionMotors[name] = {
                dir: dir
            };
        }
    }
}

/**
 * Updates the active control state for a logic function.
 * @param {string} id - The ID of the logic function.
 * @param {boolean} pressed - The state of the function.
 */
function updateLogicState(id, pressed) {
    if (pressed) {
        state.activeControls.logicFunctions[id] = pressed;
    } else {
        delete state.activeControls.logicFunctions[id];
    }
}

/**
 * Sends control packet based on state changes and timing rules
 * - Immediate send on state changes
 * - Every 150ms (3rd poll) if no changes but logic functions active
 * - Handles controller abandonment timeout
 */
function sendControlPacketIfNeeded() {
    if (!state.isConnected) return;
    
    const currentControls = JSON.stringify(state.activeControls);
    const hasChanged = currentControls !== state.lastSentControls;
    const now = Date.now();
    
    // Check if any controls are currently active
    const hasActiveMotors = Object.keys(state.activeControls.axisMotors).length > 0 || 
                           Object.keys(state.activeControls.functionMotors).length > 0;
    const hasActiveLogicFunctions = Object.keys(state.activeControls.logicFunctions).length > 0;
    const hasAnyActiveControls = hasActiveMotors || hasActiveLogicFunctions;
    
    // Update last active time if controls are active
    if (hasAnyActiveControls) {
        state.lastControlActiveTime = now;
    }
    
    // Check for controller abandonment (1 minute of inactivity)
    const timeSinceActive = now - state.lastControlActiveTime;
    const isAbandoned = timeSinceActive > state.controlAbandonmentMs;
    
    if (isAbandoned && hasActiveLogicFunctions && !hasActiveMotors) {
        // Turn off abandoned logic functions
        console.log('Controller abandoned - turning off logic functions');
        state.activeControls.logicFunctions = {};
        state.lastControlActiveTime = now; // Reset to prevent immediate re-trigger
        sendControlPacket();
        return;
    }
    
    // Send immediately on any state change (button press/release)
    if (hasChanged) {
        sendControlPacket();
        return;
    }
    
    // Send every 7th poll (140ms) if ANY controls are active to keep watchdog happy
    // This prevents the 400ms watchdog timeout from stopping motors during sustained input
    state.pollCount++;
    if (state.pollCount >= 7 && hasAnyActiveControls) {
        sendControlPacket();
        state.pollCount = 0;
    }
}

/**
 * Sends the current control packet
 */
function sendControlPacket() {
    if (!state.isConnected) return;
    
    state.ws.send(JSON.stringify(state.activeControls));
    state.lastSentControls = JSON.stringify(state.activeControls);
    state.pollCount = 0; // Reset poll count after sending
}

/**
 * State-based motor command that updates the control state instead of sending individual commands.
 * @param {string} name - The name of the motor.
 * @param {string} dir - The direction ('fwd' or 'rev').
 * @param {number} power - The power level (0 to 100).
 */
function setMotorState(name, dir, power) {
    updateMotorState(name, dir, power);
}

/**
 * State-based logic function command that updates the control state.
 * @param {string} id - The ID of the logic function.
 * @param {boolean} pressed - The state of the function.
 */
function setLogicState(id, pressed) {
    updateLogicState(id, pressed);
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

// --- Keyboard Event Handlers ---

function handleKeyDown(e) {
    if (!state.keyboardController.enabled) return;
    
    // Prevent default browser behavior for mapped keys
    const key = e.code;
    if (Object.values(state.keyboardController.mapping).includes(key)) {
        e.preventDefault();
    }
    
    state.keyboardController.pressedKeys.add(key);
    
    // Handle mapping mode
    if (state.mappingActive && state.mappingActive.inputType === 'keyboard') {
        e.preventDefault();
        handleKeyboardMapping(key);
    }
}

function handleKeyUp(e) {
    if (!state.keyboardController.enabled) return;
    
    const key = e.code;
    state.keyboardController.pressedKeys.delete(key);
    
    // Prevent default for mapped keys
    if (Object.values(state.keyboardController.mapping).includes(key)) {
        e.preventDefault();
    }
}

function handleKeyboardMapping(key) {
    if (!state.mappingActive) return;
    
    const { field, motorType } = state.mappingActive;
    state.keyboardController.mapping[field] = key;
    
    // Update UI to show the mapped key
    const cell = document.querySelector(`[data-field="${field}"]`);
    if (cell) {
        cell.textContent = getKeyDisplayName(key);
        cell.classList.remove('mapping');
    }
    
    state.mappingActive = null;
    
    // Save keyboard mapping separately
    saveConfiguration('save_keyboard_mapping', {
        keyboard_mapping: state.keyboardController.mapping,
    });
}

function getKeyDisplayName(keyCode) {
    // Convert key codes to readable names
    const keyMap = {
        'KeyW': 'W', 'KeyA': 'A', 'KeyS': 'S', 'KeyD': 'D',
        'ArrowUp': '↑', 'ArrowDown': '↓', 'ArrowLeft': '←', 'ArrowRight': '→',
        'Space': 'Space', 'ShiftLeft': 'Shift', 'ControlLeft': 'Ctrl',
        'KeyQ': 'Q', 'KeyE': 'E', 'KeyR': 'R', 'KeyT': 'T',
        'KeyY': 'Y', 'KeyU': 'U', 'KeyI': 'I', 'KeyO': 'O',
        'KeyP': 'P', 'KeyF': 'F', 'KeyG': 'G', 'KeyH': 'H',
        'KeyJ': 'J', 'KeyK': 'K', 'KeyL': 'L', 'KeyZ': 'Z',
        'KeyX': 'X', 'KeyC': 'C', 'KeyV': 'V', 'KeyB': 'B',
        'KeyN': 'N', 'KeyM': 'M',
    };
    return keyMap[keyCode] || keyCode;
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

    const createVideoEl = (ip, port) => {
        if (!ip || ip.trim() === '') return '';
        
        // Handle different stream formats
        let streamUrl;
        if (port && port !== '80' && port !== '') {
            streamUrl = `http://${ip}:${port}/stream`;
        } else {
            streamUrl = `http://${ip}/stream`;
        }
        
        // Use img tag for MJPEG streams which is more compatible than video
        return `<img class="video-full" src="${streamUrl}" style="width: 100%; height: 100%; object-fit: contain; background: #000;" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                <div style="display: none; color: #fff; text-align: center; line-height: 100%; padding: 20px;">Stream unavailable: ${streamUrl}</div>`;
    };

    if (mode === 'area') {
        container.innerHTML = createVideoEl(areaIP);
    } else if (mode === 'fpv') {
        // Handle FPV IP format - extract IP and port if provided
        const fpvParts = fpvIP.split(':');
        const fpvIPOnly = fpvParts[0];
        const fpvPort = fpvParts[1] || '8081'; // Default to 8081 for FPV
        container.innerHTML = createVideoEl(fpvIPOnly, fpvPort);
    } else if (mode === 'pip') {
        const mainIP = pipFlipped ? fpvIP : areaIP;
        const pipIP = pipFlipped ? areaIP : fpvIP;
        
        // Handle main video (could be area or FPV)
        let mainContent, pipContent;
        if (pipFlipped) {
            // FPV is main
            const fpvParts = fpvIP.split(':');
            mainContent = createVideoEl(fpvParts[0], fpvParts[1] || '8081');
            pipContent = createVideoEl(areaIP);
        } else {
            // Area is main  
            const fpvParts = fpvIP.split(':');
            mainContent = createVideoEl(areaIP);
            pipContent = createVideoEl(fpvParts[0], fpvParts[1] || '8081');
        }
        
        container.innerHTML = `
            <div class="video-main">${mainContent}</div>
            <div class="video-pip">${pipContent}</div>
        `;
    }
}

// --- Drive Mode Toggle ---

function toggleDriveMode() {
    state.driveMode = (state.driveMode === 'tank') ? 'dpad' : 'tank';
    updateDriveModeUI();
    
    // Reinitialize drive mode specific handling
    initDriveModeHandling();
    
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

    // Special Controls
    html += '<tr><td colspan="3" class="mapping-header">Special Controls</td></tr>';
    html += buildMappingRow('slow_btn', 'Slow Mode', 'Button');

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
        } else if (mapping.type === 'key') {
            mappedTo = `Key: ${mapping.key}`;
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
    
    const isDpadMode = state.driveMode === 'dpad';
    const hasController = state.gamepads.length > 0;
    
    if (isDpadMode && !hasController) {
        label.textContent = 'Press a keyboard key...';
    } else if (isDpadMode && hasController) {
        label.textContent = 'Press controller button/axis or keyboard key...';
    } else {
        label.textContent = 'Press a button or move an axis...';
    }
    
    label.classList.add('mapping-active');

    // Set a timeout to automatically cancel if no input is received
    setTimeout(() => {
        if (state.mappingActive && state.mappingActive.field === field) {
            updateMappingUI(field, state.mapping[field]); // Revert to old mapping
            state.mappingActive = null;
        }
    }, 8000); // Longer timeout for keyboard input
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
        } else if (mapping.type === 'key') {
            mappedTo = `Key: ${mapping.key}`;
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

/**
 * Initializes keyboard event listening for mapping and gameplay
 */
function initKeyboardMapping() {
    // Keyboard mapping detection (only during active mapping)
    document.addEventListener('keydown', (e) => {
        // Handle mapping mode
        if (state.mappingActive && state.driveMode === 'dpad') {
            e.preventDefault();
            
            // Map the key to a readable string
            let keyName = e.key;
            
            // Convert common keys to readable names
            const keyMap = {
                ' ': 'Space',
                'ArrowUp': '↑',
                'ArrowDown': '↓', 
                'ArrowLeft': '←',
                'ArrowRight': '→'
            };
            
            if (keyMap[keyName]) {
                keyName = keyMap[keyName];
            }
            
            // Store the keyboard mapping
            const newMapping = { type: 'key', key: keyName, code: e.code };
            state.mapping[state.mappingActive.field] = newMapping;
            updateMappingUI(state.mappingActive.field, newMapping);
            state.mappingActive = null;
            return;
        }
        
        // Handle gameplay (D-Pad mode only)
        if (state.driveMode === 'dpad' && !state.mappingActive) {
            state.keyboardState[e.code] = true;
        }
    });
    
    document.addEventListener('keyup', (e) => {
        // Handle gameplay key release (D-Pad mode only)
        if (state.driveMode === 'dpad' && !state.mappingActive) {
            state.keyboardState[e.code] = false;
        }
    });
    
    // Clear keyboard state when window loses focus
    window.addEventListener('blur', () => {
        state.keyboardState = {};
    });
}

/**
 * Check for keyboard input during gameplay (for D-Pad mode)
 */
function handleKeyboardInput() {
    if (state.driveMode !== 'dpad') return;
    
    // This would be called from the main game loop to handle keyboard controls
    // For now, we'll handle it through regular keydown/keyup events in the control processing
}
