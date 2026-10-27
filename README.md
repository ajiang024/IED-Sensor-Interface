# Flow — water filter monitor

React + TypeScript + Vite dashboard, FastAPI backend, SQLite storage, and an ESP32 Arduino/PlatformIO starter. Open this folder in VS Code. Install Node.js 22.12+ and Python 3.11+.

## 1. Start the backend

In a PowerShell terminal at the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:DEVICE_API_KEY = 'choose-a-local-device-key'
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Keep that terminal open. The database is created at `backend/water.sqlite3`. Interactive API documentation: http://localhost:8000/docs.

## 2. Start the dashboard

In another terminal:

```powershell
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173. Click **Add demo reading** to add 25 liters. The dashboard refreshes every two seconds. Click **Filter settings** to enter your actual rated capacity and install a fresh filter record. Demo and hardware readings cannot share the same filter record; install a new record before switching. Lifetime totals include demo records.

Dependencies have already been installed in this workspace. For the next run, skip installation and use `.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000` and `npm.cmd run dev` in separate terminals. If port 5173 is busy, Vite selects another port; use the address printed in the terminal. The initial preview uses port 5174.

## 3. Test sensor behavior without hardware

Start a new filter record first if you used the demo button. In another terminal, use the same key as the backend:

```powershell
$env:DEVICE_API_KEY = 'choose-a-local-device-key'
.\.venv\Scripts\python.exe simulator/send.py
```

The simulator sends cumulative counts, pauses flow, and keeps sending heartbeats. It uses the hardware ingestion path.

## 4. Connect the ESP32

1. Identify the exact ESP32 board and flowmeter model before wiring. Verify the signal voltage is compatible with the ESP32's 3.3 V input; do not connect an unverified 5 V signal directly.
2. Install the PlatformIO extension in VS Code and open `firmware` as its project folder. `esp32dev` is a generic starting board target; change it if your board requires another target.
3. Copy `firmware/include/secrets.example.h` to `firmware/include/secrets.h`. Enter Wi-Fi credentials, your computer's LAN address in `API_URL`, and the backend key. ESP32 and computer must reach each other on the local network. Permit port 8000 through Windows Firewall on your private network if prompted.
4. Replace the example 450 pulses/L with your sensor's actual calibration. Measure a known volume and calculate `pulses_per_liter = observed_pulses / measured_liters`. Set the appropriate GPIO and interrupt edge for your sensor.
5. Install a fresh filter record, upload the firmware, and check the PlatformIO serial monitor at 115200 baud. Successful uploads report HTTP 200.

## Behavior and limitations

- All quantities use liters. Life is `max(0, 1 - used/capacity) * 100`. Great: above 50%; Good: 20–50%; Poor: below 20%. Threshold alerts occur at 50%, 20%, and capacity exhausted.
- The flowmeter estimates capacity consumption; it does not measure water quality. Configure capacity using your filter specifications.
- The backend deduplicates uploads by device, boot ID, and sequence. Cumulative pulse counts recover readings missed during a network interruption within the same boot. Pulses not uploaded before a power loss are not recovered by this starter firmware.
- Keep one sensor per filter record. The firmware's 32-bit pulse counter must not wrap during a boot.
- Zero flow for 15 seconds produces one stopped-flow notification. Heartbeats expire after 12 seconds. Stopped flow does not confirm a batch completed; definitive completion needs a target volume or another sensor.
- Notifications are persisted in-app, with read status. They are evaluated on incoming data and dashboard refreshes. OS push/email and background delivery are not implemented.
- Chart dates are UTC and show the current filter record. Historical records remain in SQLite. Offline cumulative uploads are attributed to server receipt time, not reconstructed original flow dates.
- This is a trusted local-network prototype. Hardware ingestion requires a device key; dashboard/demo/replacement endpoints have no login. Add authentication and HTTPS before internet deployment. Do not forward this server publicly.
- The page uses optional Google Fonts with local font fallbacks.

## Verify

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m unittest backend.test_app -v
```

Tests cover duplicate/out-of-order readings, reconnects, reboot IDs, filter replacement, alerts, inactivity, and demo isolation. Firmware must still be compiled for your specific board and tested with the physical sensor.
