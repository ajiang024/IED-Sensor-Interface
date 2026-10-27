"""Single-device prototype. All measurements are liters; times are UTC."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

DB = Path(os.environ.get('WATER_DB', Path(__file__).with_name('water.sqlite3')))
TIMEOUT = 15  # Inactivity means flow stopped, not confirmed batch completion.

def now():
    return datetime.now(timezone.utc).timestamp()

@contextmanager
def database():
    db = sqlite3.connect(DB, timeout=15)
    try:
        db.row_factory = sqlite3.Row
        with db:
            yield db
    finally:
        db.close()

def init():
    with database() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS filters(id INTEGER PRIMARY KEY, installed REAL, capacity REAL, used REAL DEFAULT 0, source TEXT);
        CREATE TABLE IF NOT EXISTS streams(device TEXT, boot TEXT, sequence INTEGER, pulses INTEGER, PRIMARY KEY(device,boot));
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, filter_id INTEGER, time REAL, liters REAL, life REAL, source TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, time REAL, message TEXT, kind TEXT, seen INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), last_seen REAL, last_flow REAL, active INTEGER DEFAULT 0, source TEXT);
        INSERT OR IGNORE INTO state(id) VALUES(1);
        ''')
        if not db.execute('SELECT id FROM filters').fetchone():
            db.execute('INSERT INTO filters(installed,capacity) VALUES(?,1000)', (now(),))

@asynccontextmanager
async def lifespan(app):
    init()
    yield

app = FastAPI(title='Flow water monitor', lifespan=lifespan)

class Reading(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    boot_id: str = Field(min_length=1, max_length=80)
    sequence: int = Field(ge=0)
    cumulative_pulses: int = Field(ge=0)
    pulses_per_liter: float = Field(gt=0, le=100000)

class Replacement(BaseModel):
    capacity_liters: float = Field(gt=0, le=10000000)

def notify(db, message, kind):
    db.execute('INSERT INTO notifications(time,message,kind) VALUES(?,?,?)', (now(),message,kind))

def stop_if_idle(db):
    state = db.execute('SELECT * FROM state').fetchone()
    if state['active'] and now() - state['last_flow'] >= TIMEOUT:
        db.execute('UPDATE state SET active=0 WHERE id=1')
        notify(db, 'Flow stopped. The filtering session may be complete.', 'session')

def add_volume(db, liters, source):
    f = db.execute('SELECT * FROM filters ORDER BY id DESC LIMIT 1').fetchone()
    if f['source'] and f['source'] != source:
        raise HTTPException(409, 'Replace the filter record before switching between demo and hardware data.')
    old = max(0, 100 * (1-f['used']/f['capacity']))
    used = f['used'] + liters
    life = max(0, 100 * (1-used/f['capacity']))
    db.execute('UPDATE filters SET used=?,source=? WHERE id=?', (used,source,f['id']))
    db.execute('UPDATE state SET last_seen=?,source=? WHERE id=1', (now(),source))
    if liters > 0:
        db.execute('INSERT INTO readings(filter_id,time,liters,life,source) VALUES(?,?,?,?,?)', (f['id'],now(),liters,life,source))
        db.execute('UPDATE state SET active=1,last_flow=? WHERE id=1', (now(),))
    for threshold, message in [(50,'Filter life is now Good.'),(20,'Filter life is at or below 20%. Plan a replacement.'),(0,'Rated capacity reached. Replace the filter.')]:
        if old > threshold >= life:
            notify(db, message, 'filter')

@app.post('/api/readings')
def ingest(r: Reading, x_device_key: str = Header(default='')):
    key = os.environ.get('DEVICE_API_KEY')
    if not key:
        raise HTTPException(503, 'Set DEVICE_API_KEY on the backend before accepting hardware data.')
    if x_device_key != key:
        raise HTTPException(401, 'Invalid device key')
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        stop_if_idle(db)
        previous = db.execute('SELECT * FROM streams WHERE device=? AND boot=?', (r.device_id,r.boot_id)).fetchone()
        if previous and r.sequence <= previous['sequence']:
            return {'accepted':False,'reason':'duplicate or old sequence'}
        if previous and r.cumulative_pulses < previous['pulses']:
            raise HTTPException(409, 'Pulse count decreased; use a new boot ID after a restart')
        # A new boot starts its counter at zero; first upload includes all pulses since boot.
        delta = r.cumulative_pulses - (previous['pulses'] if previous else 0)
        add_volume(db, delta / r.pulses_per_liter, 'hardware')
        db.execute('INSERT OR REPLACE INTO streams VALUES(?,?,?,?)', (r.device_id,r.boot_id,r.sequence,r.cumulative_pulses))
    return {'accepted':True}

@app.post('/api/demo')
def demo():
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        stop_if_idle(db)
        add_volume(db, 25, 'demo')
    return {'added_liters':25}

@app.post('/api/filters/replace')
def replace(r: Replacement):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO filters(installed,capacity) VALUES(?,?)', (now(),r.capacity_liters))
        db.execute('UPDATE state SET active=0,last_seen=NULL,last_flow=NULL,source=NULL WHERE id=1')
        notify(db, 'New filter installed. Usage reset; history preserved.', 'filter')
    return {'ok':True}

@app.post('/api/notifications/read')
def mark_read():
    with database() as db:
        db.execute('UPDATE notifications SET seen=1')
    return {'ok':True}

@app.get('/api/dashboard')
def dashboard():
    with database() as db:
        stop_if_idle(db)
        f = dict(db.execute('SELECT * FROM filters ORDER BY id DESC LIMIT 1').fetchone())
        state = dict(db.execute('SELECT * FROM state').fetchone())
        history = [dict(row) for row in db.execute("SELECT strftime('%Y-%m-%d',time,'unixepoch') AS date, SUM(liters) AS liters, MIN(life) AS life FROM readings WHERE filter_id=? GROUP BY date ORDER BY date", (f['id'],))]
        alerts = [dict(row) for row in db.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT 30')]
        lifetime = db.execute('SELECT COALESCE(SUM(used),0) FROM filters').fetchone()[0]
    remaining = max(0,f['capacity']-f['used'])
    life = remaining/f['capacity']*100
    connected = bool(state['last_seen'] and now()-state['last_seen'] < 12)
    return {'filter':f,'life':life,'remaining':remaining,'status':'Great' if life>50 else 'Good' if life>=20 else 'Poor','lifetime':lifetime,'history':history,'notifications':alerts,'connected':connected,'flowing':bool(state['active'] and connected),'source':state['source'],'last_seen':state['last_seen']}
