import json
import os
import socket
import threading
from evdev import UInput, AbsInfo, ecodes as e

SOCKET_PATH = '/tmp/retro-pad.sock'

BUTTON_MAP = {
    'A':      (e.EV_KEY, e.BTN_SOUTH),
    'B':      (e.EV_KEY, e.BTN_EAST),
    'X':      (e.EV_KEY, e.BTN_WEST),
    'Y':      (e.EV_KEY, e.BTN_NORTH),
    'L1':     (e.EV_KEY, e.BTN_TL),
    'R1':     (e.EV_KEY, e.BTN_TR),
    'L2':     (e.EV_KEY, e.BTN_TL2),
    'R2':     (e.EV_KEY, e.BTN_TR2),
    'Start':  (e.EV_KEY, e.BTN_START),
    'Select': (e.EV_KEY, e.BTN_SELECT),
}

# axis, direction_value
HAT_MAP = {
    'DpadUp':    (e.ABS_HAT0Y, -1),
    'DpadDown':  (e.ABS_HAT0Y,  1),
    'DpadLeft':  (e.ABS_HAT0X, -1),
    'DpadRight': (e.ABS_HAT0X,  1),
}

AXIS_MAX = 32767

CAPABILITIES = {
    e.EV_KEY: [
        e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST,
        e.BTN_TL, e.BTN_TR, e.BTN_TL2, e.BTN_TR2,
        e.BTN_START, e.BTN_SELECT,
        e.BTN_THUMBL, e.BTN_THUMBR,
    ],
    e.EV_ABS: [
        (e.ABS_X,     AbsInfo(value=0, min=-AXIS_MAX, max=AXIS_MAX, fuzz=16, flat=128, resolution=0)),
        (e.ABS_Y,     AbsInfo(value=0, min=-AXIS_MAX, max=AXIS_MAX, fuzz=16, flat=128, resolution=0)),
        (e.ABS_RX,    AbsInfo(value=0, min=-AXIS_MAX, max=AXIS_MAX, fuzz=16, flat=128, resolution=0)),
        (e.ABS_RY,    AbsInfo(value=0, min=-AXIS_MAX, max=AXIS_MAX, fuzz=16, flat=128, resolution=0)),
        (e.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (e.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
    ],
}


def handle_event(ui, data):
    btn = data.get('button', '')
    state = int(data.get('state', 0))

    if btn in BUTTON_MAP:
        ev_type, code = BUTTON_MAP[btn]
        ui.write(ev_type, code, state)
        ui.syn()

    elif btn in HAT_MAP:
        axis, direction = HAT_MAP[btn]
        ui.write(e.EV_ABS, axis, direction if state else 0)
        ui.syn()

    elif btn == 'LStick':
        if state == 0:
            x, y = 0, 0
        else:
            x = int(float(data.get('x', 0)) * AXIS_MAX)
            y = int(float(data.get('y', 0)) * AXIS_MAX)
        ui.write(e.EV_ABS, e.ABS_X, x)
        ui.write(e.EV_ABS, e.ABS_Y, y)
        ui.syn()

    elif btn == 'RStick':
        if state == 0:
            x, y = 0, 0
        else:
            x = int(float(data.get('x', 0)) * AXIS_MAX)
            y = int(float(data.get('y', 0)) * AXIS_MAX)
        ui.write(e.EV_ABS, e.ABS_RX, x)
        ui.write(e.EV_ABS, e.ABS_RY, y)
        ui.syn()


def handle_client(ui, conn):
    try:
        raw = conn.recv(512).decode('utf-8', errors='ignore').strip()
        if raw:
            handle_event(ui, json.loads(raw))
    except Exception:
        pass
    finally:
        conn.close()


def serve(ui):
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    srv.listen(16)

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(ui, conn), daemon=True).start()


if __name__ == '__main__':
    # Named after Xbox 360 pad so RetroArch's built-in autoconfig picks it up
    ui = UInput(CAPABILITIES, name='Microsoft X-Box 360 pad', version=0x110)
    serve(ui)
