import network
import time
import ubinascii
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
# Function to set the device to AP mode with a given SSID (tag)
# ---------------------------------------------------------
def start_ap_mode(tag):
    # Disable STA to avoid AP broadcast failure
    sta = network.WLAN(network.STA_IF)
    if sta.active():
        sta.active(False)
        time.sleep_ms(200)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    # Ensure config happens AFTER active(True)
    ap.config(essid=tag, password=default_ap_password, authmode=3)

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
        print("No stored WiFi config. Skipping STA mode.")
        return start_ap_mode(tag)

    # Log reboot time and count, and if multiple quick reboots detected, force AP mode
    if logreboot():
        print("Detected multiple quick reboots, forcing AP mode.")
        tag = get_config_value("vehicleTag", "RokDevice")
        return start_ap_mode(tag)

    # Continue to STA mode to connect to configured network.
    # HARD RESET BOTH INTERFACES
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    sta.active(False)
    time.sleep_ms(300)

    # Sometimes S3 needs two resets
    ap.active(False)
    sta.active(False)
    time.sleep_ms(300)

    # Activate STA mode only
    sta.active(True)
    time.sleep_ms(200)

    # disable power save mode on STA (prevents internal error on S3)
    try:
        sta.config(pm=0)
    except:
        pass

    # Decrypt password if needed
    if password and not password.startswith("{"):
        try:
            key = b"rokwifi1234"
            enc = ubinascii.a2b_base64(password)
            password = "".join([chr(b ^ key[i % len(key)]) for i, b in enumerate(enc)])
        except Exception:
            pass

    # Set static IP if requested
    if ip_mode == "static" and static_ip and static_mask and static_gw:
        try:
            sta.ifconfig((static_ip, static_mask, static_gw, static_dns or static_gw))
            print(
                f"Set static IP: {static_ip} {static_mask} {static_gw} {static_dns or static_gw}"
            )
        except Exception as e:
            print("Failed to set static IP:", e)

    # Connect to the AP, retrying up to 5 times
    for attempt in range(5):
        print(f"Attempt {attempt+1}/5 connecting to {ssid}...")

        try:
            sta.connect(ssid, password)
        except Exception as e:
            print("STA connect() threw:", e)
            wifierror = e
            time.sleep(3)
            continue

        # Check if the connection was successful
        for _ in range(20):  # 6 seconds max
            if sta.isconnected():
                print("Connected!", sta.ifconfig())
                save_config_value("wifi_error", False)
                return sta

            time.sleep(0.3)

    print("Failed to connect after 5 attempts.")
    save_config_value("wifi_error", True)
    save_config_value(
        "wifi_error_text", locals().get("wifierror", "Unknown Error occurred")
    )
    return None


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
