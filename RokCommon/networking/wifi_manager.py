import network
import time
import gc
from RokCommon.variables.vars_store import get_config_value, save_config_value

# Variables
reboot_file = "/variables/reboot_count.txt"
# Time window in seconds to count reboots for AP mode fallback
reboot_time_window = 20
# Number of reboots within time window to trigger AP mode
reboot_threshold = 3
# Default AP password
default_ap_password = "1234567890"


# ---------------------------------------------------------
# Yielding sleep function to prevent REPL hanging
# ---------------------------------------------------------
def yielding_sleep(duration):
    """Sleep for duration seconds while yielding to prevent REPL hang"""
    end_time = time.time() + duration
    while time.time() < end_time:
        time.sleep_ms(50)  # 50ms chunks to yield frequently
        gc.collect()  # Help with memory management


# ---------------------------------------------------------
# Function to set the device to AP mode with a given SSID (tag)
# ---------------------------------------------------------
def start_ap_mode(tag):
    # Properly disable and reset STA interface
    sta = network.WLAN(network.STA_IF)
    if sta.active():
        sta.disconnect()
        yielding_sleep(0.2)
        sta.active(False)
        yielding_sleep(0.5)

    # Initialize AP interface with proper timing
    ap = network.WLAN(network.AP_IF)
    if not ap.active():
        ap.active(True)
        yielding_sleep(0.5)  # Allow AP interface to fully initialize
    
    # Configure AP settings after initialization
    try:
        ap.config(
            essid=tag, 
            password=default_ap_password, 
            authmode=3,  # WPA2
            channel=1,   # Use channel 1 for better compatibility
            max_clients=4  # Limit concurrent clients
        )
        yielding_sleep(0.2)
        print(f"AP mode started: {tag}")
    except Exception as e:
        print(f"AP config error: {e}")
    
    gc.collect()
    return ap


# ---------------------------------------------------------
# Function to set the device to STA mode and connect to a configured Wifi network
# Falls back to AP mode if the connection fails, or multiple reboots are detected (while in STA mode)
# ---------------------------------------------------------
def connect_to_wifi():
    ssid = get_config_value("ssid")
    password = get_config_value("wifipass")
    ip_mode = get_config_value("ip_mode", "dhcp")
    static_ip = get_config_value("static_ip", "")
    static_mask = get_config_value("static_mask", "")
    static_gw = get_config_value("static_gw", "")
    static_dns = get_config_value("static_dns", "")

    tag = get_config_value("vehicleTag", "RokDevice")

    # If ssid is not defined, do not connect to local network, and use AP mode.
    if not ssid:
        return start_ap_mode(tag)

    # Log reboot time and count, and if multiple quick reboots detected, force AP mode
    if logreboot():
        return start_ap_mode(tag)

    # Continue to STA mode to connect to configured network.
    
    # Complete WiFi interface reset and proper initialization for ESP32-S3
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    
    # Ensure clean state - disconnect and deactivate all interfaces with proper timing
    if sta.active() and sta.isconnected():
        sta.disconnect()
        yielding_sleep(0.5)  # Extra time for clean disconnect
    
    if ap.active():
        ap.active(False)
        yielding_sleep(0.5)  # Ensure AP is fully deactivated
    
    if sta.active():
        sta.active(False)
        yielding_sleep(0.8)  # Extended delay for ESP32-S3 to fully reset

    # Clear any cached network data and force garbage collection
    gc.collect()
    yielding_sleep(0.3)  # Brief pause after GC
    
    # Initialize STA interface with ESP32-S3 optimized timing

    sta.active(True)
    yielding_sleep(1.2)  # Extended initialization delay for ESP32-S3 stability

    # Configure WiFi settings for maximum reliability and ESP32-S3 optimization
    try:
        # Critical: Disable power saving first for stable connection
        sta.config(pm=0)
        yielding_sleep(0.3)  # Let power management setting take effect
        
        # Set single reconnection attempt to avoid conflicts
        sta.config(reconnects=1)
        yielding_sleep(0.2)
        
        # Set DHCP hostname for identification
        sta.config(dhcp_hostname=tag[:15])  # Limit hostname length
        yielding_sleep(0.3)  # Extended delay for hostname config
        
        # Additional ESP32-S3 specific optimizations
        try:
            sta.config(txpower=20)  # Maximum TX power for better range
            yielding_sleep(0.2)
        except Exception:
            pass  # Not all firmware supports txpower setting
            

    except Exception as e:
        print(f"Warning: WiFi config partially failed: {e}")

    # Set static IP if requested - do this after all WiFi config is complete
    if ip_mode == "static" and static_ip and static_mask and static_gw:
        try:
            sta.ifconfig((static_ip, static_mask, static_gw, static_dns or static_gw))
            yielding_sleep(0.4)  # Extended delay for static IP to apply
            print(f"Static IP configured: {static_ip}")
        except Exception as e:
            print(f"Failed to set static IP: {e}")
            print("Continuing with DHCP...")

    # Connect to the AP with optimized retry strategy
    wifierror = "No error"
    for attempt in range(3):  # Reduced from 5 to 3 attempts
        print(f"WiFi connection attempt {attempt+1}/3 to {ssid}...")
        
        # Reset adapter on retry attempts (but not first attempt) with ESP32-S3 optimization
        if attempt > 0:
            print("Resetting WiFi adapter for retry (ESP32-S3 optimized)...")
            if sta.isconnected():
                sta.disconnect()
                yielding_sleep(0.5)  # Extended disconnect time
            
            # Thorough adapter reset with ESP32-S3 timing
            sta.active(False)
            yielding_sleep(1.0)  # Extended delay for complete reset
            gc.collect()  # Clear any cached state
            yielding_sleep(0.3)
            sta.active(True)
            yielding_sleep(1.2)  # Extended reactivation time for ESP32-S3
            
            # Re-apply critical settings with proper delays
            try:
                sta.config(pm=0)  # Power save off
                yielding_sleep(0.3)
                sta.config(reconnects=1)
                yielding_sleep(0.2)
                sta.config(dhcp_hostname=tag[:15])
                yielding_sleep(0.3)
                # Re-apply TX power if supported
                try:
                    sta.config(txpower=20)
                    yielding_sleep(0.2)
                except Exception:
                    pass
                print("WiFi adapter reset and reconfigured")
            except Exception as e:
                print(f"Retry config error: {e}")
            
            # Re-apply static IP if configured
            if ip_mode == "static" and static_ip and static_mask and static_gw:
                try:
                    sta.ifconfig((static_ip, static_mask, static_gw, static_dns or static_gw))
                    yielding_sleep(0.4)
                    print("Static IP reconfigured after reset")
                except Exception as e:
                    print(f"Static IP retry error: {e}")

        # Initiate connection with error handling
        try:
            print(f"Initiating connection to {ssid}...")
            sta.connect(ssid, password)
            yielding_sleep(0.8)  # Extended delay after connect call for ESP32-S3
        except Exception as e:
            print(f"Connection initiation failed: {e}")
            wifierror = f"Connect failed: {str(e)}"
            if attempt < 2:
                yielding_sleep(3)  # Wait before retry
            continue

        # Monitor connection status with 20 second timeout for all attempts  
        # Increased from 15s as connections have been getting close
        max_checks = 20  # 20 seconds (20 * 1.0s)
        max_time_desc = "20s"
            
        print(f"Monitoring connection status (up to {max_time_desc})...")
        connected = False
        for check in range(max_checks):
            if sta.isconnected():
                ip_info = sta.ifconfig()
                print(f"✓ Connected on attempt {attempt+1}! IP: {ip_info[0]}, Gateway: {ip_info[2]}")
                print(f"  Signal strength: {sta.status('rssi')} dBm")
                print(f"  Connection took {check+1} seconds")
                save_config_value("wifi_error", False)
                save_config_value("wifi_error_text", "")
                return sta
            
            status = sta.status()
            # Create status description without nested f-strings (MicroPython doesn't support them)
            if status == 0:
                status_desc = "IDLE"
            elif status == 1:
                status_desc = "CONNECTING"
            elif status == -3:
                status_desc = "WRONG_PASSWORD"
            elif status == -2:
                status_desc = "NO_AP_FOUND"
            elif status == -1:
                status_desc = "CONNECT_FAIL"
            elif status == 3:
                status_desc = "GOT_IP"
            else:
                status_desc = f"UNKNOWN({status})"
            
            print(f"  Check {check+1}/{max_checks}: Status={status} ({status_desc})")
            
            if status == network.STAT_WRONG_PASSWORD:
                print("✗ Authentication failed (may be network congestion, not wrong password)")
                wifierror = "Authentication failed"
                # Don't break - retry as this is often temporary
            elif status == network.STAT_NO_AP_FOUND:
                print("✗ Network not found")
                wifierror = "Network not found"
                break
            elif status == network.STAT_CONNECT_FAIL:
                print("✗ Connection failed")
                wifierror = "Connection failed"
                # Don't break - retry as this could be temporary
                
            time.sleep_ms(1000)  # 1 second monitoring intervals
            if check % 5 == 0:  # Progress indicator every 5 seconds
                current_time = check + 1
                # Extract numeric part from "20s" -> "20"
                max_time_numeric = max_time_desc[:-1]
                print(f"  Connecting... ({current_time}/{max_time_numeric}s)")
            gc.collect()  # Regular memory cleanup during long waits
        
        # Handle connection failure for this attempt
        if not connected:
            status = sta.status()
            if status == network.STAT_NO_AP_FOUND:
                # Only treat "network not found" as permanent - retry auth failures
                wifierror = f"Permanent failure: status {status}"
                break
            else:
                wifierror = f"Timeout after {max_time_desc} (status: {status})"
                print(f"Connection timeout on attempt {attempt+1} - will retry")
        
        # Wait before next attempt (extended for ESP32-S3 stability)
        if attempt < 2 and not connected:
            print("Waiting before next attempt...")
            yielding_sleep(5)  # Extended delay between attempts for better stability

    print(f"✗ Failed to connect after 3 attempts (total time: up to 60 seconds). Error: {wifierror}")
    save_config_value("wifi_error", True)
    save_config_value("wifi_error_text", wifierror)
    
    # Clean disconnect before fallback with extended timing
    try:
        if sta.isconnected():
            sta.disconnect()
        yielding_sleep(0.5)  # Extended cleanup time
    except Exception:
        pass
    
    # Fall back to AP mode when STA connection fails
    print("Falling back to AP mode...")
    tag = get_config_value("vehicleTag", "RokDevice")
    return start_ap_mode(tag)


# ---------------------------------------------------------
# Function to log a reboot to the reboot file, and return if the reboot threshold is met
# ---------------------------------------------------------
def logreboot():
    now = time.time()
    reboot_count = 0
    last_reboot = 0
    try:
        with open(reboot_file, "r") as f:
            parts = f.read().split(",")
            if len(parts) == 2:
                reboot_count = int(parts[0])
                last_reboot = float(parts[1])
    except Exception:
        pass
    # If last reboot was < time window ago, increment; else reset
    if now - last_reboot < reboot_time_window:
        reboot_count += 1
    else:
        reboot_count = 1
    with open(reboot_file, "w") as f:
        f.write(f"{reboot_count},{now}")
    return reboot_count >= reboot_threshold
