"""Send simulated ESP32 readings. Start a fresh filter before switching modes."""
import json
import os
import time
import uuid
import urllib.request

url = os.environ.get('API_URL', 'http://127.0.0.1:8000/api/readings')
key = os.environ.get('DEVICE_API_KEY', '')
boot = str(uuid.uuid4())
print('Simulating 10 seconds of flow, then 20 seconds of zero flow. Ctrl+C to stop.')
count = 0
sequence = 0
try:
    while True:
        if sequence % 15 < 5:
            count += 450
        payload = dict(device_id='simulated-esp32', boot_id=boot, sequence=sequence, cumulative_pulses=count, pulses_per_liter=450)
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','X-Device-Key':key})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                print(response.read().decode())
        except Exception as error:
            print(error)
        sequence += 1
        time.sleep(2)
except KeyboardInterrupt:
    print('\nSimulator stopped.')
