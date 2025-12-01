# bluetooth_controller.py
# Handles BLE scan, pair, and input for gamepads (BLE HID only)
import bluetooth
import uasyncio as asyncio

class BluetoothController:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.devices = []
        self.conn_handle = None
        self.paired_addr = None
        self.input_callback = None
        self.ble.irq(self._irq)

    def _irq(self, event, data):
        if event == 5:  # _IRQ_SCAN_RESULT
            addr_type, addr, adv_type, rssi, adv_data = data
            name = self._decode_name(adv_data)
            self.devices.append({'addr_type': addr_type, 'addr': bytes(addr), 'name': name, 'rssi': rssi})
        elif event == 6:  # _IRQ_SCAN_DONE
            pass
        elif event == 7:  # _IRQ_PERIPHERAL_CONNECT
            self.conn_handle, addr_type, addr = data
            self.paired_addr = bytes(addr)
        elif event == 8:  # _IRQ_PERIPHERAL_DISCONNECT
            self.conn_handle = None
            self.paired_addr = None
        elif event == 18:  # _IRQ_GATTC_NOTIFY
            conn_handle, value_handle, notify_data = data
            if self.input_callback:
                self.input_callback(bytes(notify_data))

    def _decode_name(self, adv_data):
        # Parse BLE advertisement for device name
        i = 0
        while i + 1 < len(adv_data):
            length = adv_data[i]
            if length == 0:
                break
            type = adv_data[i + 1]
            if type == 0x09:  # Complete Local Name
                return adv_data[i + 2:i + 1 + length].decode('utf-8')
            i += 1 + length
        return None

    async def scan(self, duration_ms=3000):
        self.devices = []
        self.ble.gap_scan(duration_ms, 30000, 30000)
        await asyncio.sleep_ms(duration_ms + 100)
        return self.devices

    async def pair(self, addr_type, addr):
        self.ble.gap_connect(addr_type, addr)
        # Wait for connection (simple, not robust)
        for _ in range(20):
            if self.conn_handle:
                return True
            await asyncio.sleep_ms(100)
        return False

    def set_input_callback(self, cb):
        self.input_callback = cb

# Singleton instance
controller = BluetoothController()
