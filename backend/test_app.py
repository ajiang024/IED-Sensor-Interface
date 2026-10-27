import os
import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException
from backend import app as monitor

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        monitor.DB = Path(self.temp.name)/'test.sqlite3'
        monitor.init()
        os.environ['DEVICE_API_KEY'] = 'test'
    def tearDown(self):
        self.temp.cleanup()
    def send(self, seq, pulses, boot='boot'):
        return monitor.ingest(monitor.Reading(device_id='sensor',boot_id=boot,sequence=seq,cumulative_pulses=pulses,pulses_per_liter=450), 'test')
    def test_duplicate_and_reconnect(self):
        self.send(0,450)
        self.send(0,450)
        self.send(4,2250)
        self.send(2,900)
        self.assertEqual(monitor.dashboard()['filter']['used'],5)
        self.send(0,450,'new-boot')
        self.assertEqual(monitor.dashboard()['filter']['used'],6)
    def test_reset_preserves_history_and_stream_baseline(self):
        self.send(0,450)
        monitor.replace(monitor.Replacement(capacity_liters=200))
        self.send(1,900)
        d=monitor.dashboard()
        self.assertEqual(d['filter']['used'],1)
        self.assertEqual(d['lifetime'],2)
        self.assertEqual(d['filter']['capacity'],200)
    def test_threshold_notifications_once(self):
        self.send(0,450*850)
        self.send(1,450*860)
        d=monitor.dashboard()
        self.assertEqual(d['status'],'Poor')
        self.assertEqual(len(d['notifications']),2)
    def test_idle_and_disconnect(self):
        self.send(0,450)
        with monitor.database() as db:
            db.execute('UPDATE state SET last_flow=?,last_seen=?',(monitor.now()-30,monitor.now()-30))
        d=monitor.dashboard()
        self.assertFalse(d['connected'])
        self.assertFalse(d['flowing'])
        self.assertEqual(len(d['notifications']),1)
        self.assertEqual(len(monitor.dashboard()['notifications']),1)
    def test_demo_cannot_mix_with_hardware(self):
        monitor.demo()
        with self.assertRaises(HTTPException):
            self.send(0,450)
        self.assertEqual(monitor.dashboard()['filter']['used'],25)
    def test_bad_key_and_decreasing_counter(self):
        with self.assertRaises(HTTPException):
            monitor.ingest(monitor.Reading(device_id='a',boot_id='a',sequence=0,cumulative_pulses=1,pulses_per_liter=1), 'wrong')
        self.send(0,450)
        with self.assertRaises(HTTPException):
            self.send(1,100)

if __name__ == '__main__':
    unittest.main()
