import network
import time
from variables.vars_store import load_config, save_config


def start_ap_mode(tag):
    # Disable STA to avoid AP broadcast failure
    sta = network.WLAN(network.STA_IF)
    if sta.active():
        sta.active(False)
        time.sleep_ms(200)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    # Ensure config happens AFTER active(True)
    ap.config(essid=tag, password="1234567890", authmode=3)

    return ap


def connect_to_wifi():
    import network, time, ubinascii

    cfg = load_config()

    # --- Reboot counter logic ---
    reboot_file = "/variables/reboot_count.txt"
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
    # If last reboot was < 20s ago, increment; else reset
    if now - last_reboot < 20:
        reboot_count += 1
    else:
        reboot_count = 1
    with open(reboot_file, "w") as f:
        f.write(f"{reboot_count},{now}")
    # If rebooted 3+ times in 60s, force AP mode
    if reboot_count >= 3:
        print("Detected multiple quick reboots, forcing AP mode.")
        tag = cfg.get("vehicleTag") or "RokVehicle"
        return start_ap_mode(tag)

    ssid = cfg.get("ssid")
    password = cfg.get("wifipass")
    ip_mode = cfg.get("ip_mode", "dhcp")
    static_ip = cfg.get("static_ip", "")
    static_mask = cfg.get("static_mask", "")
    static_gw = cfg.get("static_gw", "")
    static_dns = cfg.get("static_dns", "")

    if not ssid:
        print("No stored WiFi config. Skipping STA mode.")
        return None

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

    sta.active(True)
    time.sleep_ms(200)

    # Extra sanity configuration (prevents Internal Error)
    try:
        sta.config(pm=0)  # disable power save
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

    # --- Set static IP if requested ---
    if ip_mode == "static" and static_ip and static_mask and static_gw:
        try:
            sta.ifconfig((static_ip, static_mask, static_gw, static_dns or static_gw))
            print(
                f"Set static IP: {static_ip} {static_mask} {static_gw} {static_dns or static_gw}"
            )
        except Exception as e:
            print("Failed to set static IP:", e)

    # --- CONNECT ---
    for attempt in range(5):
        print(f"Attempt {attempt+1}/5 connecting to {ssid}...")

        try:
            sta.connect(ssid, password)
        except Exception as e:
            print("STA connect() threw:", e)
            time.sleep(1)
            continue

        for _ in range(20):  # 6 seconds max
            if sta.isconnected():
                print("Connected!", sta.ifconfig())
                cfg["wifi_error"] = False
                save_config(cfg)
                # Reset reboot counter on success
                with open(reboot_file, "w") as f:
                    f.write(f"0,{now}")
                return sta

            time.sleep(0.3)

        print("Retrying WiFi...")

    print("Failed to connect after 5 attempts.")
    cfg["wifi_error"] = True
    save_config(cfg)
    return None
