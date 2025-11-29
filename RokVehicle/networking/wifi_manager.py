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

    print("AP Mode Started:", tag, ap.ifconfig())
    return ap


def connect_to_wifi():
    import network, time
    cfg = load_config()

    ssid = cfg.get("ssid")
    password = cfg.get("wifipass")

    if not ssid:
        print("No stored WiFi config. Skipping STA mode.")
        return None

    # HARD RESET BOTH INTERFACES
    sta = network.WLAN(network.STA_IF)
    ap  = network.WLAN(network.AP_IF)

    print("Resetting WiFi interfaces...")

    ap.active(False)
    sta.active(False)
    time.sleep_ms(300)

    # Sometimes S3 needs two resets
    ap.active(False)
    sta.active(False)
    time.sleep_ms(300)

    print("Enabling STA...")
    sta.active(True)
    time.sleep_ms(200)

    # Extra sanity configuration (prevents Internal Error)
    try:
        sta.config(pm=0)  # disable power save
    except:
        pass

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
                return sta

            time.sleep(0.3)

        print("Retrying WiFi...")

    print("Failed to connect after 5 attempts.")
    cfg["wifi_error"] = True
    save_config(cfg)
    return None

