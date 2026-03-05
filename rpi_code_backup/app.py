import serial
import time
import threading
import json
import os
import logging
import requests
import pytz
import yfinance as yf
from datetime import datetime
from flask import Flask, render_template, request, jsonify

SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 9600
CONFIG_PATH = "/home/gordo/splitflap/settings.json"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

serial_lock = threading.Lock()

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5) # Reduced timeout for faster chunk looping
except Exception as e:
    ser = None
    logging.error(f"Serial failed. Simulation Mode. Reason: {e}")

def load_settings():
    defaults = {
        "offsets": {str(i): 2832 for i in range(45)},
        "calibrations": {str(i): 4096 for i in range(45)}, 
        "tuned_chars": {str(i): {} for i in range(45)},
        "zip_code": "02118",
        "timezone": "US/Eastern",
        "weather_api_key": "",
        "mbta_stop": "place-bbsta",
        "mbta_route": "Orange",
        "stocks_list": "MSFT,GOOG,NVDA",
        "nhl_teams": "BOS,DAL",
        "auto_home": True
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                data = json.load(f)
                defaults.update(data)
                
                if "tuned_chars" not in defaults:
                    defaults["tuned_chars"] = {str(i): {} for i in range(45)}
                    
                return defaults
        except: pass
    return defaults

def save_settings(data):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f, indent=4)

settings = load_settings()

def send_raw(cmd):
    if not cmd.endswith('\n'):
        cmd += '\n'
    with serial_lock:
        if ser:
            ser.write(cmd.encode())
            ser.flush()
            time.sleep(0.02)

def sync_hardware_data(mod_id):
    if not ser: return False
    
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"m{mod_id:02d}d\n".encode())
        ser.flush()
        
        start = time.time()
        buffer = ""
        target = f"m{mod_id:02d}d:"
        
        # Buffer aggregation loop: Absorbs all data, ignores RS485 garbage bytes
        while time.time() - start < 5.0: 
            if ser.in_waiting > 0:
                try:
                    chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    
                    # Wait until we see our target AND a newline character
                    if target in buffer and '\n' in buffer[buffer.find(target):]:
                        valid_part = buffer[buffer.find(target):].split('\n')[0]
                        logging.info(f"RS485 Valid Sync: {valid_part}")
                        
                        data = valid_part.split('d:', 1)[1]
                        parts = data.split(':')
                        if len(parts) >= 2:
                            settings['offsets'][str(mod_id)] = int(parts[0])
                            settings['calibrations'][str(mod_id)] = int(parts[1])
                            
                            settings['tuned_chars'][str(mod_id)] = {}
                            if len(parts) == 3 and parts[2]:
                                pairs = parts[2].split(',')
                                for p in pairs:
                                    if '=' in p:
                                        idx, val = p.split('=')
                                        settings['tuned_chars'][str(mod_id)][idx] = int(val)
                            
                            save_settings(settings)
                            return True
                except Exception as e:
                    logging.error(f"Parse error: {e}")
            time.sleep(0.05)
            
        logging.error(f"Sync Timeout. Raw buffer held: {buffer}")
    return False

COLOR_MAP = {
    '🟥': 'r', '🟧': 'o', '🟨': 'y', '🟩': 'g', 
    '🟦': 'b', '🟪': 'p', '⬜': 'w', '⬛': ' '
}

def send_to_display(text):
    if not text: return
    clean_text = text.upper()
    for emoji, char in COLOR_MAP.items():
        clean_text = clean_text.replace(emoji, char)
        
    clean_text = clean_text.ljust(45)[:45]
    logging.info(f"DISPLAY: {clean_text}")
    
    with serial_lock:
        if ser:
            for i, char in enumerate(clean_text):
                cmd = f"m{i:02d}-{char}\n"
                ser.write(cmd.encode())
                ser.flush()
                time.sleep(0.015) 

# --- EXPLICIT GLOBAL APP STATE ---
current_playlist = []
loop_delay = 5
stop_event = threading.Event()
last_sent_page = None
active_app = None                 

last_fetches = {'weather': 0, 'metro': 0, 'sports': 0, 'stocks': 0}
app_caches = {'weather': "", 'metro': [], 'sports': [], 'stocks': []}


@app.route('/')
def index(): return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    global settings
    if request.method == 'POST':
        data = request.json
        action = data.get('action')
        mod_id = str(data.get('id', '0'))

        if action == 'save_global':
            keys = ['zip_code','weather_api_key','timezone','mbta_stop','mbta_route','stocks_list','nhl_teams']
            settings.update({k: data[k] for k in keys})
            save_settings(settings)
            return jsonify(status="Saved")

        if action == 'adjust':
            delta = int(data.get('delta', 0))
            current = int(settings['offsets'].get(mod_id, 2832))
            new_offset = current + delta
            settings['offsets'][mod_id] = new_offset
            save_settings(settings)
            send_raw(f"m{int(mod_id):02d}o{new_offset}")
            return jsonify(new_offset=settings['offsets'][mod_id])

        if action == 'home_one':
            send_raw(f"m{int(mod_id):02d}h")
            return jsonify(status="Homing")

        if action == 'calibrate':
            with serial_lock:
                if ser:
                    ser.reset_input_buffer() 
                    ser.write(f"m{int(mod_id):02d}c\n".encode())
                    ser.flush() 
                    
                    start_wait = time.time()
                    buffer = ""
                    target = f"m{int(mod_id):02d}:"
                    
                    # 45 second timeout to allow full 360 degree physical rotation
                    while (time.time() - start_wait) < 45.0: 
                        if ser.in_waiting > 0:
                            chunk = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                            buffer += chunk
                            
                            # Filter garbage bytes and wait for newline
                            if target in buffer and '\n' in buffer[buffer.find(target):]:
                                valid_part = buffer[buffer.find(target):].split('\n')[0]
                                logging.info(f"RS485 Valid Calibration: {valid_part}")
                                try:
                                    val = int(valid_part.split(target)[1])
                                    settings['calibrations'][mod_id] = val
                                    save_settings(settings)
                                    ser.write(f"m{int(mod_id):02d}t{val}\n".encode())
                                    ser.flush()
                                    return jsonify(status="success", steps=val)
                                except: pass
                        time.sleep(0.1) 
                    return jsonify(status="error", message="Timeout"), 500
    return jsonify(settings)

@app.route('/custom_tune', methods=['POST'])
def custom_tune():
    data = request.json
    action = data.get('action')
    mod_id = int(data.get('id', 0))
            
    if action == 'goto':
        step = int(data.get('step', 0))
        send_raw(f"m{mod_id:02d}g{step}")
        
    elif action == 'save':
        idx = int(data.get('index', 0))
        step = int(data.get('step', 0))
        send_raw(f"m{mod_id:02d}w{idx}:{step}")
        settings['tuned_chars'][str(mod_id)][str(idx)] = step
        save_settings(settings)
            
    elif action == 'erase':
        idx = str(data.get('index', ''))
        if idx:
            send_raw(f"m{mod_id:02d}w{idx}:65535")
            if idx in settings['tuned_chars'][str(mod_id)]:
                del settings['tuned_chars'][str(mod_id)][idx]
        else:
            send_raw(f"m{mod_id:02d}e")
            settings['tuned_chars'][str(mod_id)] = {}
        save_settings(settings)
        
    return jsonify(status="Success")

@app.route('/sync_module', methods=['POST'])
def sync_module():
    mod_id = int(request.json.get('id', 0))
    success = sync_hardware_data(mod_id)
    return jsonify(status="success" if success else "failed", settings=settings)

@app.route('/sync_all', methods=['POST'])
def sync_all():
    for i in range(45):
        sync_hardware_data(i)
    return jsonify(status="success", settings=settings)

@app.route('/assign_id', methods=['POST'])
def assign_id():
    data = request.json
    new_id = int(data.get('id', 0))
    send_raw(f"m**i{new_id:02d}")
    return jsonify(status="ID Assigned")

@app.route('/toggle_autohome', methods=['POST'])
def toggle_autohome():
    global settings
    data = request.json
    enabled = data.get('enabled', True)
    settings['auto_home'] = enabled
    save_settings(settings)
    val = 1 if enabled else 0
    send_raw(f"m**a{val}")
    return jsonify(status="Auto-home updated")

@app.route('/update_playlist', methods=['POST'])
def update_playlist():
    global current_playlist, loop_delay, last_sent_page, active_app
    data = request.json
    current_playlist = data.get('pages', [])
    loop_delay = data.get('delay', 5)
    last_sent_page = None 
    active_app = None 
    stop_event.set()
    return jsonify(status="success")

@app.route('/run_app', methods=['POST'])
def run_app():
    global active_app, last_fetches, loop_delay
    data = request.json
    active_app = data.get('app')
    last_fetches = {k: 0 for k in last_fetches}
    if active_app == 'stocks': loop_delay = 10
    else: loop_delay = 5 
    stop_event.set()
    return jsonify(status=f"App {active_app} started")

@app.route('/home_all')
def home_all():
    send_raw("m**h")
    return jsonify(status="Homing All")


def format_lines(l1, l2, l3):
    return l1.center(15)[:15] + l2.center(15)[:15] + l3.center(15)[:15]

def fetch_weather():
    api_key = settings.get("weather_api_key", "").strip()
    zip_code = settings.get("zip_code", "02118").strip()
    tz_str = settings.get("timezone", "US/Eastern")
    if not api_key: return format_lines("NO API KEY", "SET IN TAB", "")
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?zip={zip_code},us&appid={api_key}&units=imperial"
        res = requests.get(url, timeout=5).json()
        city = res['name'].upper()
        tz = pytz.timezone(tz_str)
        now_time = datetime.now(tz).strftime("%I:%M%p").lstrip("0")
        max_city_len = 14 - len(now_time) 
        l1 = f"{city[:max_city_len]} {now_time}".center(15)
        temp = round(res['main']['temp'])
        feels = round(res['main']['feels_like'])
        desc = res['weather'][0]['main'].upper()
        l2_prefix = f"{temp}F ({feels}F) "
        rem_len = 15 - len(l2_prefix)
        l2 = (l2_prefix + desc[:rem_len]).center(15)
        high = round(res['main']['temp_max'])
        low = round(res['main']['temp_min'])
        l3 = f"H:{high}F L:{low}F".center(15)
        return l1 + l2 + l3
    except Exception as e:
        logging.error(f"Weather error: {e}")
        return format_lines("WEATHER", "FETCH ERROR", "")

def fetch_metro():
    stop = settings.get('mbta_stop', 'place-bbsta')
    route = settings.get('mbta_route', 'Orange')
    url = f"https://api-v3.mbta.com/predictions?filter[stop]={stop}&filter[route]={route}&sort=departure_time"
    try:
        res = requests.get(url, timeout=5).json()
        predictions = res.get('data', [])
        dirs = {0: [], 1: []} 
        for p in predictions:
            dt = p['attributes']['departure_time'] or p['attributes']['arrival_time']
            if not dt: continue
            pred_time = datetime.fromisoformat(dt).astimezone(pytz.utc)
            now = datetime.now(pytz.utc)
            mins = int((pred_time - now).total_seconds() / 60)
            if mins < 0: continue
            dir_id = p['attributes']['direction_id']
            if dir_id in dirs and len(dirs[dir_id]) < 2:
                dirs[dir_id].append(str(mins))
        def format_dir(name, times):
            if not times: return f"{name} ---".ljust(15)
            t_str = ",".join(times) + "M"
            return f"{name} {t_str}"[:15].ljust(15)
        l1 = "BACK BAY STN.".center(15)
        l2 = format_dir("OAK GRV", dirs[1])
        l3 = format_dir("FRST HLS", dirs[0])
        return [l1 + l2 + l3]
    except Exception as e:
        logging.error(f"Metro error: {e}")
        return [format_lines("METRO ERROR", "", "")]

def fetch_stocks():
    tickers = [t.strip() for t in settings.get('stocks_list', 'MSFT,GOOG,NVDA').split(',') if t.strip()]
    pages = []
    chunks = [tickers[i:i + 3] for i in range(0, len(tickers), 3)]
    for chunk in chunks:
        price_lines = ["               ", "               ", "               "]
        pct_lines = ["               ", "               ", "               "]
        for idx, sym in enumerate(chunk):
            try:
                stock = yf.Ticker(sym)
                price = stock.fast_info.last_price
                prev = stock.fast_info.previous_close
                pct = ((price - prev) / prev) * 100
                sign = "+" if pct >= 0 else ""
                p_str = f"{sym[:5]:<5} ${price:<7.2f}"[:15].ljust(15)
                c_str = f"{sym[:5]:<5} {sign}{pct:.2f}%"[:15].ljust(15)
                price_lines[idx] = p_str
                pct_lines[idx] = c_str
            except Exception as e:
                logging.error(f"Stock error for {sym}: {e}")
                err_str = f"{sym[:5]:<5} ERR".ljust(15)
                price_lines[idx] = err_str
                pct_lines[idx] = err_str
        pages.append(price_lines[0] + price_lines[1] + price_lines[2])
        pages.append(pct_lines[0] + pct_lines[1] + pct_lines[2])
    return pages if pages else [format_lines("NO STOCKS", "CONFIGURED", "")]

def fetch_sports():
    teams = [t.strip() for t in settings.get('nhl_teams', 'BOS,DAL').split(',') if t.strip()]
    url = "https://api-web.nhle.com/v1/score/now" 
    pages = []
    try:
        res = requests.get(url, timeout=5).json()
        games = res.get('games', [])
        for g in games:
            away = g['awayTeam']['abbrev']
            home = g['homeTeam']['abbrev']
            if away in teams or home in teams:
                score_str = f"{away} {g['awayTeam'].get('score', 0)} {home} {g['homeTeam'].get('score', 0)}"
                state = g['gameState']
                if state in ['F', 'FINAL']: clock = "FINAL"
                elif state in ['LIVE', 'CRIT']: clock = f"P{g['period']} {g['clock']['timeRemaining']}"
                else: clock = "SCHEDULED"
                pages.append(format_lines("NHL SCORE", score_str, clock))
        return pages if pages else [format_lines("NHL SCORES", "NO GAMES", "TODAY")]
    except: return [format_lines("SPORTS ERR", "", "")]

def playlist_loop():
    global current_playlist, loop_delay, last_sent_page, active_app, last_fetches, app_caches
    while True:
        now = time.time()
        display_pages = []
        
        # Guard against NameError
        if 'active_app' not in globals() or active_app is None:
            display_pages = current_playlist
        elif active_app == 'weather':
            if now - last_fetches['weather'] > 600:
                app_caches['weather'] = [fetch_weather()]
                last_fetches['weather'] = now
            display_pages = app_caches['weather']
        elif active_app == 'metro':
            if now - last_fetches['metro'] > 30: 
                app_caches['metro'] = fetch_metro()
                last_fetches['metro'] = now
            display_pages = app_caches['metro']
        elif active_app == 'stocks':
            if now - last_fetches['stocks'] > 60: 
                app_caches['stocks'] = fetch_stocks()
                last_fetches['stocks'] = now
            display_pages = app_caches['stocks']
        elif active_app == 'sports':
            if now - last_fetches['sports'] > 60: 
                app_caches['sports'] = fetch_sports()
                last_fetches['sports'] = now
            display_pages = app_caches['sports']
        elif active_app == 'dashboard':
            tz = pytz.timezone(settings.get('timezone', 'US/Eastern'))
            dt = datetime.now(tz)
            time_page = format_lines(dt.strftime("%A").upper(), dt.strftime("%b %d %Y").upper(), dt.strftime("%I:%M %p").upper())
            if now - last_fetches['weather'] > 600:
                app_caches['weather'] = [fetch_weather()]
                last_fetches['weather'] = now
            weather_page = app_caches['weather'][0]
            display_pages = [time_page, weather_page]
        else:
            display_pages = current_playlist

        if not display_pages:
            time.sleep(1)
            continue

        for page in display_pages:
            if stop_event.is_set(): break
            if page != last_sent_page:
                send_to_display(page)
                last_sent_page = page
            for _ in range(int(float(loop_delay)*10)):
                if stop_event.is_set(): break
                time.sleep(0.1)
        if stop_event.is_set(): stop_event.clear()

threading.Thread(target=playlist_loop, daemon=True).start()

if __name__ == '__main__':
    logging.info("Web UI running on 0.0.0.0:80")
    app.run(host='0.0.0.0', port=80)