# RokVision main.py
# Entry point for SeeedStudio XIAO ESP32-S3 Sense FPV camera board

from variables.vars_store import load_config, save_config
from networking.wifi_manager import setup_wifi
from web.web_server import start_web_server
from camera.camera_stream import start_camera_stream

if __name__ == "__main__":
    cfg = load_config()
    setup_wifi(cfg)
    start_web_server(cfg)
    # Only start camera if in STA mode
    if cfg.get("ip_mode", "dhcp") != "ap":
        start_camera_stream(cfg)
