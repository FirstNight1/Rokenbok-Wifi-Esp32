# camera_stream.py for RokVision
# MicroPython camera streaming for SeeedStudio XIAO ESP32-S3 Sense
# Streams MJPEG over HTTP (for browser FPV)

import network
import time

try:
    import camera
except ImportError:
    camera = None  # For dev/testing on non-camera boards

from machine import Pin

# --- Camera config ---
CAMERA_CONFIG = {
    'framesize': camera.FRAME_QVGA if camera else 8,  # 320x240
    'quality': 10,
    'contrast': 1,
    'brightness': 0,
    'saturation': 0,
    'vflip': 0,
    'hmirror': 0,
}

CAMERA_LED_PIN = 21  # Change if needed for your board


def start_camera_stream(cfg):
    if not camera:
        print("Camera module not available.")
        return
    # Only start if in STA mode
    if cfg.get("ip_mode", "dhcp") == "ap":
        print("Camera streaming disabled in AP mode.")
        return
    # Init camera
    try:
        camera.init(0, format=camera.JPEG)
        for k, v in CAMERA_CONFIG.items():
            setattr(camera, k, v)
        print("Camera initialized.")
    except Exception as e:
        print("Camera init failed:", e)
        return
    # Optional: turn on camera LED
    try:
        led = Pin(CAMERA_LED_PIN, Pin.OUT)
        led.value(1)
    except Exception:
        pass
    # Start HTTP MJPEG stream
    import socket
    addr = socket.getaddrinfo('0.0.0.0', 8081)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    print('Camera stream ready at http://<ip>:8081/stream')
    while True:
        cl, addr = s.accept()
        print('Client connected from', addr)
        cl.send('HTTP/1.1 200 OK\r\n')
        cl.send('Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n')
        try:
            while True:
                buf = camera.capture() if camera else b''
                cl.send(b'--frame\r\n')
                cl.send(b'Content-Type: image/jpeg\r\n\r\n')
                cl.send(buf)
                cl.send(b'\r\n')
                time.sleep(0.05)  # ~20 FPS
        except Exception as e:
            print('Stream ended:', e)
        cl.close()
