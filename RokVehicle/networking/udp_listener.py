
import _thread
import socket
import ujson as json
import time

# Global: thread-safe queue for motor commands (to be processed by main thread)
try:
    import uasyncio as asyncio
except Exception:
    asyncio = None

class CommandQueue:
    def __init__(self, maxsize=100):
        self._q = []
        self._max = maxsize
        self._lock = _thread.allocate_lock()
    def put(self, item):
        with self._lock:
            if len(self._q) < self._max:
                self._q.append(item)
    def get_all(self):
        with self._lock:
            items = self._q[:]
            self._q.clear()
            return items

cmd_queue = CommandQueue()

UDP_PORT = 9999
RECV_BUF = 1024

# Rate limiting parameters (per-source token bucket)
# tokens are replenished at RATE tokens per second up to CAPACITY
RATE = 50       # tokens/sec (allow ~50 packets/sec)
CAPACITY = 100  # burst capacity

# state: addr -> {tokens: float, last_ts: float}
_rate_state = {}



def _process_packet(data):
    """Parse a JSON UDP packet and enqueue motor commands for main thread."""
    try:
        payload = json.loads(data)
    except Exception:
        return

    # Enqueue all commands (dict or list)
    if isinstance(payload, list):
        for p in payload:
            if isinstance(p, dict):
                cmd_queue.put(p)
    elif isinstance(payload, dict):
        cmd_queue.put(payload)


# _handle_cmd is now handled in main thread (see web_server)


def _udp_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", UDP_PORT))
    except Exception as e:
        print("UDP listener bind failed:", e)
        try:
            s.close()
        except:
            pass
        return

    s.settimeout(0.1)
    print("UDP listener started on port", UDP_PORT)

    while True:
        try:
            data, addr = s.recvfrom(RECV_BUF)
            if not data:
                continue
            # rate limit per source IP
            src = addr[0]
            now = time.ticks_ms() / 1000.0
            st = _rate_state.get(src)
            if st is None:
                st = {'tokens': CAPACITY, 'last_ts': now}
                _rate_state[src] = st

            # refill
            elapsed = now - st['last_ts']
            if elapsed > 0:
                st['tokens'] = min(CAPACITY, st['tokens'] + elapsed * RATE)
                st['last_ts'] = now

            if st['tokens'] < 1.0:
                # drop packet silently (could log occasionally)
                # print('UDP rate limit drop from', src)
                continue
            st['tokens'] -= 1.0
            # data may be bytes
            if isinstance(data, bytes):
                try:
                    text = data.decode()
                except Exception:
                    text = None
            else:
                text = str(data)

            if text:
                _process_packet(text)
        except OSError:
            # timeout or no data; continue loop
            pass
        except Exception as e:
            print("UDP listener error:", e)


def start():
    try:
        _thread.start_new_thread(_udp_loop, ())
    except Exception as e:
        print("Failed to start UDP listener thread:", e)


# Start automatically on import
start()
