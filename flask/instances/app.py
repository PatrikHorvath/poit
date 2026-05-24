from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import mysql.connector
import configparser
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="eventlet")

app = Flask(__name__)
CORS(app)

# Načítanie konfigurácie
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'config.cfg'))

app.config['SECRET_KEY'] = config['auth']['secret_key']
socketio = SocketIO(app, cors_allowed_origins="*")

DB_CONFIG = {
    'host':     config['mysql']['host'],
    'user':     config['mysql']['user'],
    'password': config['mysql']['passwd'],
    'database': config['mysql']['database'],
}

# Stav systému
device_info = {
    'connected': False,
    'sid': None,
    'status': 'off',  # 'on' alebo 'off'
    'connected_at': None
}

# Stav monitorovania
monitoring_active = False
monitoring_start_time = None

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def fmt_dt(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None


# ============ WEBSOCKET ENDPOINTY ============

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    global device_info
    # Ak sa odpojí zariadenie
    if device_info['connected'] and device_info['sid'] == request.sid:
        device_info = {
            'connected': False,
            'sid': None,
            'status': 'off',
            'connected_at': None
        }
        print('Device disconnected')
        socketio.emit('device_status_update', {'status': 'off', 'connected': False})

@socketio.on('register_device')
def handle_register(data):
    """Zariadenie sa registruje s secret_key"""
    global device_info
    secret_key = data.get('secret_key')
    device_id = data.get('device_id', 'Teplotné zariadenie')
    
    if secret_key != app.config['SECRET_KEY']:
        emit('registration_error', {'error': 'Invalid secret key'})
        return False
    
    device_info = {
        'connected': True,
        'sid': request.sid,
        'status': 'off',
        'connected_at': datetime.now().isoformat(),
        'device_id': device_id
    }
    
    print(f'Device {device_id} registered successfully')
    emit('registration_success', {'status': 'registered'})
    socketio.emit('device_status_update', {'status': 'off', 'connected': True})

@socketio.on('temperature_data')
def handle_temperature_data(data):
    """Zariadenie posiela teplotné dáta"""
    if not device_info['connected'] or device_info['status'] != 'on':
        return
    
    temperature = data.get('temperature')
    timestamp = data.get('timestamp', datetime.now().isoformat())
    
    # Uložiť teplotu do databázy
    save_temperature_reading(temperature, timestamp)
    
    # Ak monitorovanie beží, pošli live dáta
    if monitoring_active:
        socketio.emit('live_temperature', {
            'temperature': temperature,
            'timestamp': timestamp
        })

def save_temperature_reading(temperature, timestamp):
    """Uložiť teplotné dáta do databázy"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Získať aktuálnu session
        cursor.execute("""
            SELECT id, temperatures FROM temperature_session 
            WHERE end_time IS NULL 
            ORDER BY start_time DESC LIMIT 1
        """)
        
        session = cursor.fetchone()
        
        if session:
            session_id = session[0]
            # Append teploty do existujúceho JSON poľa
            cursor.execute("""
                UPDATE temperature_session 
                SET temperatures = JSON_ARRAY_APPEND(temperatures, '$', JSON_OBJECT('value', %s, 'timestamp', %s))
                WHERE id = %s
            """, (temperature, timestamp, session_id))
        else:
            # Vytvoriť novú session
            temperatures = json.dumps([{'value': temperature, 'timestamp': timestamp}])
            cursor.execute("""
                INSERT INTO temperature_session (temperatures, start_time) 
                VALUES (%s, %s)
            """, (temperatures, timestamp))
        
        conn.commit()
    except mysql.connector.Error as err:
        print(f'Database error: {err}')
    finally:
        cursor.close()
        conn.close()


# ============ HTTP ENDPOINTY ============

@app.route('/api/device/status', methods=['GET'])
def get_device_status():
    """Získať stav zariadenia"""
    return jsonify({
        'connected': device_info['connected'],
        'status': device_info['status'],
        'connected_at': device_info['connected_at']
    }), 200

@app.route('/api/device/control', methods=['POST'])
def control_device():
    """Ovládanie zariadenia (zapnúť/vypnúť) - BOD 1 a 4"""
    global device_info
    data = request.get_json()
    command = data.get('command')  # 'on' alebo 'off'
    
    if not device_info['connected']:
        return jsonify({'error': 'Zariadenie nie je pripojené'}), 404
    
    # Poslať príkaz zariadeniu cez WebSocket
    socketio.emit('control_command', {'command': command}, room=device_info['sid'])
    
    # Ak je príkaz na vypnutie, ukončiť aktuálnu session
    if command == 'off':
        end_current_session()
    
    # Aktualizovať stav
    device_info['status'] = command
    
    # Notifikovať všetkých klientov
    socketio.emit('device_status_update', {
        'status': command,
        'connected': True
    })
    
    return jsonify({'message': f'Systém {"zapnutý" if command == "on" else "vypnutý"}'}), 200

def end_current_session():
    """Ukončiť aktuálnu session"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE temperature_session 
            SET end_time = %s 
            WHERE end_time IS NULL
        """, (datetime.now(),))
        conn.commit()
    except mysql.connector.Error as err:
        print(f'Database error: {err}')
    finally:
        cursor.close()
        conn.close()

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """Začať monitorovanie"""
    global monitoring_active, monitoring_start_time
    
    monitoring_active = True
    monitoring_start_time = datetime.now().isoformat()
    
    return jsonify({
        'message': 'Monitorovanie spustené',
        'start_time': monitoring_start_time
    }), 200

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    """Zastaviť monitorovanie"""
    global monitoring_active, monitoring_start_time
    
    monitoring_active = False
    monitoring_start_time = None
    
    return jsonify({'message': 'Monitorovanie zastavené'}), 200

@app.route('/api/monitoring/status', methods=['GET'])
def get_monitoring_status():
    """Získať stav monitorovania"""
    return jsonify({
        'active': monitoring_active,
        'start_time': monitoring_start_time
    }), 200

@app.route('/api/temperatures/query', methods=['POST'])
def query_temperatures():
    """Získať teplotné dáta podľa časového rozsahu - BOD 5 a 6"""
    data = request.get_json()
    from_time = data.get('from_time')
    to_time = data.get('to_time')
    
    if not from_time:
        return jsonify({'error': 'from_time je povinný'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Získať všetky session v časovom rozsahu
        query = """
            SELECT id, temperatures, start_time, end_time 
            FROM temperature_session 
            WHERE start_time >= %s
        """
        params = [from_time]
        
        if to_time:
            query += " AND start_time <= %s"
            params.append(to_time)
        
        query += " ORDER BY start_time ASC"
        
        cursor.execute(query, params)
        sessions = cursor.fetchall()
        
        # Spojiť všetky teploty
        all_temperatures = []
        for session in sessions:
            temps = json.loads(session['temperatures']) if session['temperatures'] else []
            for temp in temps:
                temp_time = datetime.fromisoformat(temp['timestamp'])
                from_dt = datetime.fromisoformat(from_time)
                
                if temp_time >= from_dt:
                    if to_time:
                        to_dt = datetime.fromisoformat(to_time)
                        if temp_time <= to_dt:
                            all_temperatures.append(temp)
                    else:
                        all_temperatures.append(temp)
        
        # Výpočet štatistík
        stats = {}
        if all_temperatures:
            values = [t['value'] for t in all_temperatures]
            stats = {
                'count': len(all_temperatures),
                'avg': round(sum(values) / len(values), 2),
                'min': round(min(values), 2),
                'max': round(max(values), 2),
                'first': all_temperatures[0]['value'],
                'last': all_temperatures[-1]['value']
            }
        
        return jsonify({
            'temperatures': all_temperatures,
            'stats': stats,
            'from_time': from_time,
            'to_time': to_time
        }), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/session/latest', methods=['GET'])
def get_latest_session():
    """Získať poslednú session"""
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, temperatures, start_time, end_time 
            FROM temperature_session 
            ORDER BY start_time DESC LIMIT 1
        """)
        session = cursor.fetchone()
        
        if session:
            session['temperatures'] = json.loads(session['temperatures']) if session['temperatures'] else []
            session['start_time'] = fmt_dt(session.get('start_time'))
            session['end_time'] = fmt_dt(session.get('end_time'))
        
        return jsonify({'session': session}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/dbdata/session', methods=['GET'])
def list_sessions():
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, start_time, JSON_LENGTH(temperatures) AS count "
            "FROM temperature_session ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        for row in rows:
            row['start_time'] = fmt_dt(row.get('start_time'))
        return jsonify({'sessions': rows}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close(); conn.close()


@app.route('/dbdata/session/<int:session_id>', methods=['GET'])
def get_session(session_id):
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, temperatures, start_time FROM temperature_session WHERE id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': f'Záznam ID {session_id} neexistuje'}), 404

        row['start_time']   = fmt_dt(row.get('start_time'))
        row['temperatures'] = json.loads(row['temperatures'])
        return jsonify(row), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close(); conn.close()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)