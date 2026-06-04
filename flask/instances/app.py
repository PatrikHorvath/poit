from cloup import command

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import configparser
import json
import os
from datetime import datetime, timedelta, timezone
import warnings
from flask_socketio import SocketIO, emit, join_room, leave_room

BACKUP_DIR = "/home/devuser/flask/instances/static/files"
FILE_PATH = os.path.join(BACKUP_DIR, "backup.json")
LOCAL_TZ = timezone(timedelta(hours=2))
DEBUG_MODE = True

os.makedirs(BACKUP_DIR, exist_ok=True)

active_session_cache = {"start_time": None, "recent_measurements": []}

MAX_CACHE_SIZE = 50

if os.path.exists(FILE_PATH):
    try:
        with open(FILE_PATH, "a") as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line
            if last_line:
                last_data = json.loads(last_line)
                if last_data.get("type") == "session_start":
                    active_session_cache["start_time"] = last_data.get("timestamp")
    except Exception as e:
        print(f"Error checking initial backup file status: {e}")

warnings.filterwarnings("ignore", category=DeprecationWarning, module="eventlet")

app = Flask(__name__)
CORS(app)

# Načítanie konfigurácie
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "config.cfg"))

app.config["SECRET_KEY"] = config["auth"]["secret_key"]
socketio = SocketIO(app, cors_allowed_origins="*")

DB_CONFIG = {
    "host": config["mysql"]["host"],
    "user": config["mysql"]["user"],
    "password": config["mysql"]["passwd"],
    "database": config["mysql"]["database"],
}

# Stav systému
device_info = {
    "connected": False,
    "sid": None,
    "status": "off",  # 'on' alebo 'off'
    "connected_at": None,
}

# Stav monitorovania
monitoring_active = False
monitoring_start_time = None


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


# ---------------------------------------------------------------
#  WEBSOCKET - komunikácia so zariadením a webstránkou
# ---------------------------------------------------------------


@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    global device_info
    if device_info["connected"] and device_info["sid"] == request.sid:
        device_info = {
            "connected": False,
            "sid": None,
            "status": "off",
            "connected_at": None,
        }
        print("Device disconnected")

        end_current_session()
        end_backup_session()

        socketio.emit("device_status_update", {"status": "off", "connected": False})


# registrácia autorifikovaného zariadenia, ktoré môže zapisovať dáta do databázy
@socketio.on("register_device")
def handle_register(data):
    """Zariadenie sa registruje s secret_key"""
    global device_info
    secret_key = data.get("secret_key")
    device_id = data.get("device_id", "Teplotné zariadenie")

    if secret_key != app.config["SECRET_KEY"]:
        emit("registration_error", {"error": "Invalid secret key"})
        return False

    device_info = {
        "connected": True,
        "sid": request.sid,
        "status": "off",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
    }

    print(f"Device {device_id} registered successfully")
    emit("registration_success", {"status": "registered", "debug_mode": DEBUG_MODE})
    socketio.emit("device_status_update", {"status": "off", "connected": True})


# všetky stránky v miestnosti "monitoring" dostávajú aktualizácie o živých teplotách a stave monitorovania
@socketio.on("join_monitoring")
def handle_join_monitoring():
    """Webstránka sa pripojí do miestnosti pre live monitorovanie"""
    join_room("monitoring")
    print(f"Client {request.sid} joined monitoring room")
    emit("monitoring_confirmed", {"status": "active"})


@socketio.on("leave_monitoring")
def handle_leave_monitoring():
    """Webstránka opustí miestnosť pre live monitorovanie"""
    leave_room("monitoring")
    print(f"Client {request.sid} left monitoring room")
    emit("monitoring_confirmed", {"status": "inactive"})


@socketio.on("set_peltier_pwm")
def handle_set_peltier_pwm(data):
    """Nastavenie PWM hodnoty ak je zapnutý debug mode"""
    if not DEBUG_MODE:
        emit("debug_error", {"error": "Debug mode is disabled"})
        return False

    if not device_info["connected"]:
        emit("debug_error", {"error": "Device is not connected"})
        return False

    pwm_value = data.get("pwm")
    if pwm_value is None:
        emit("debug_error", {"error": "Missing pwm value"})
        return False

    try:
        pwm_value = int(pwm_value)
        if not (0 <= pwm_value <= 100):
            emit("debug_error", {"error": "PWM must be between 0 and 100"})
            return False
    except ValueError:
        emit("debug_error", {"error": "Invalid PWM value format"})
        return False

    socketio.emit(
        "control_command",
        {"command": "set_pwm", "value": pwm_value},
        room=device_info["sid"],
    )
    print(f"Debug command: sent PWM {pwm_value}% to device {device_info['sid']}")
    emit("debug_success", {"message": f"PWM nastavené na {pwm_value}%"})


@socketio.on("set_setpoint")
def handle_set_setpoint(data):
    """Nastavenie želanej hodnoty teploty (setpoint pre regulátor)"""
    if not device_info["connected"]:
        emit("setpoint_error", {"error": "Zariadenie nie je pripojené"})
        return False

    setpoint_value = data.get("setpoint")
    if setpoint_value is None:
        emit("setpoint_error", {"error": "Chýba hodnota setpointu"})
        return False

    try:
        setpoint_value = float(setpoint_value)
    except (ValueError, TypeError):
        emit("setpoint_error", {"error": "Neplatný formát hodnoty"})
        return False

    # voliteľná validácia rozsahu - uprav podľa svojich potrieb
    if not (-20.0 <= setpoint_value <= 80.0):
        emit("setpoint_error", {"error": "Setpoint mimo povoleného rozsahu"})
        return False

    socketio.emit(
        "control_command",
        {"command": "set_setpoint", "value": setpoint_value},
        room=device_info["sid"],
    )
    # broadcast všetkým monitorujúcim klientom
    socketio.emit(
        "setpoint_update",
        {"setpoint": setpoint_value},
        room="monitoring",
    )
    print(f"Setpoint: sent {setpoint_value}°C to device {device_info['sid']}")
    emit("setpoint_success", {"message": f"Želaná teplota nastavená na {setpoint_value}°C"})

# ---------------------------------------------------------------
#  API ENDPOINTY - pre ovládanie zariadenia a získavanie dát
# ---------------------------------------------------------------


# pozeranie aktualneho backup JSON suboru
@app.route("/api/backup/download", methods=["GET"])
def get_backup_file():
    """Získať aktuálny JSON súbor zálohy"""
    if not os.path.exists(FILE_PATH):
        return jsonify({"sessions": []}), 200

    sessions = []
    current_session = None

    try:
        # Čítanie riadok po riadku na zabránenie preťaženiu pamäte RAM
        with open(FILE_PATH, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    entry_type = entry.get("type")

                    if entry_type == "session_start":
                        if current_session:
                            sessions.append(current_session)
                        current_session = {
                            "start_time": entry.get("timestamp"),
                            "end_time": None,
                            "measurements": [],
                        }
                    elif entry_type == "measurement":
                        if not current_session:
                            current_session = {
                                "start_time": entry.get("timestamp"),
                                "end_time": None,
                                "measurements": [],
                            }
                        current_session["measurements"].append(
                            {
                                "temperature": entry.get("temperature"),
                                "peltier_pwm": entry.get("peltier_pwm"),
                                "timestamp": entry.get("timestamp"),
                            }
                        )
                    elif entry_type == "session_end":
                        if current_session:
                            current_session["end_time"] = entry.get("timestamp")
                            sessions.append(current_session)
                            current_session = None
                except json.JSONDecodeError:
                    continue

        if current_session:
            sessions.append(current_session)

        return jsonify({"sessions": sessions}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to read backup file: {str(e)}"}), 500


# end point pre získanie aktuálneho stavu zariadenia, na zobrazenie na webstránke
@app.route("/api/device/status", methods=["GET"])
def get_device_status():
    """Získať stav zariadenia"""
    return (
        jsonify(
            {
                "connected": device_info["connected"],
                "status": device_info["status"],
                "connected_at": device_info["connected_at"],
                "debug_mode": DEBUG_MODE,
            }
        ),
        200,
    )


@app.route("/api/archive/<int:start_timestamp>/<int:end_timestamp>", methods=["GET"])
def archived_data_filter(start_timestamp, end_timestamp):
    if start_timestamp > end_timestamp:
        return (
            jsonify({"error": "Start timestamp cannot be greater than end timestamp"}),
            400,
        )

    try:
        start_dt = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT temperature, peltier_pwm, time_measured
            FROM temperature_measurements
            WHERE time_measured BETWEEN %s AND %s
            ORDER BY time_measured ASC
        """,
            (start_dt, end_dt),
        )

        rows = cursor.fetchall()

        # Serializácia datetime na string
        temperatures = [
            {
                "value": (
                    float(row["temperature"])
                    if row["temperature"] is not None
                    else None
                ),
                "pwm": (
                    int(row["peltier_pwm"]) if row["peltier_pwm"] is not None else None
                ),
                "timestamp": (
                    row["time_measured"].isoformat()
                    if isinstance(row["time_measured"], datetime)
                    else row["time_measured"]
                ),
            }
            for row in rows
        ]

        # Štatistiky
        stats = {}
        if temperatures:
            values = [t["value"] for t in temperatures if t["value"] is not None]
            if values:
                stats = {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "first": values[0],
                    "last": values[-1],
                }

        return (
            jsonify(
                {
                    "temperatures": temperatures,
                    "stats": stats,
                    "from": start_dt.isoformat(),
                    "to": end_dt.isoformat(),
                }
            ),
            200,
        )

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@app.route("/api/session/last", methods=["GET"])
def get_last_session_data():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, time_start, time_end 
            FROM working_session
            ORDER BY time_start DESC 
            LIMIT 1
        """)
        session = cursor.fetchone()

        if not session:
            return jsonify({"error": "No sessions found in the database"}), 404

        session_id = session["id"]

        cursor.execute(
            """
            SELECT temperature, peltier_pwm, time_measured 
            FROM temperature_measurements 
            WHERE session_id = %s
            ORDER BY time_measured ASC
        """,
            (session_id,),
        )
        rows = cursor.fetchall()

        temperatures = [
            {
                "value": (
                    float(row["temperature"])
                    if row["temperature"] is not None
                    else None
                ),
                "pwm": (
                    int(row["peltier_pwm"]) if row["peltier_pwm"] is not None else None
                ),
                "timestamp": (
                    row["time_measured"].isoformat()
                    if isinstance(row["time_measured"], datetime)
                    else row["time_measured"]
                ),
            }
            for row in rows
        ]

        stats = {}
        if temperatures:
            values = [t["value"] for t in temperatures if t["value"] is not None]
            if values:
                stats = {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 2),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "first": values[0],
                    "last": values[-1],
                }

        return (
            jsonify(
                {
                    "session_id": session_id,
                    "time_start": (
                        session["time_start"].isoformat()
                        if isinstance(session["time_start"], datetime)
                        else session["time_start"]
                    ),
                    "time_end": (
                        session["time_end"].isoformat()
                        if isinstance(session["time_end"], datetime)
                        else session["time_end"]
                    ),
                    "temperatures": temperatures,
                    "stats": stats,
                }
            ),
            200,
        )

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# endpoint pre prenesenie príkazu z webstránky do zariadenia (zapnúť/vypnúť)
@app.route("/api/device/control", methods=["POST"])
def control_device():
    global device_info
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "Missing command parameter"}), 400

    command = data.get("command")
    if command not in ["on", "off"]:
        return jsonify({"error": "Invalid command value"}), 400

    if not device_info["connected"]:
        return jsonify({"error": "Zariadenie nie je pripojené"}), 404

    socketio.emit("control_command", {"command": command}, room=device_info["sid"])

    if command == "on":
        start_new_session_db()
        start_new_backup_session()
    elif command == "off":
        end_current_session()
        end_backup_session()

    device_info["status"] = command
    socketio.emit("device_status_update", {"status": command, "connected": True})

    return (
        jsonify({"message": f'Systém {"zapnutý" if command == "on" else "vypnutý"}'}),
        200,
    )


# endpoint na zápis teplotných dát do databázy
@app.route("/api/measurements", methods=["POST"])
def add_measurements():
    token = request.headers.get("X-Device-Token")
    if token != app.config["SECRET_KEY"]:
        return jsonify({"error": "Unauthorized device"}), 401
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Empty payload"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        query = """
            INSERT INTO temperature_measurements 
            (temperature, peltier_pwm, time_measured) 
            VALUES (%s, %s, %s)
        """
        broadcast_data = []
        items = payload if isinstance(payload, list) else [payload]

        for item in items:
            try:
                temp = (
                    float(item.get("temperature"))
                    if item.get("temperature") is not None
                    else None
                )
                pwm = (
                    int(item.get("pwm_peltier"))
                    if item.get("pwm_peltier") is not None
                    else None
                )
                ts_raw = item.get("timestamp")

                if isinstance(ts_raw, (int, float)):
                    timestamp = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
                else:
                    timestamp = ts_raw

                cursor.execute(query, (temp, pwm, timestamp))

                ts_str = (
                    timestamp.isoformat()
                    if isinstance(timestamp, datetime)
                    else str(timestamp)
                )
                append_measurement_to_backup(temp, pwm, ts_str)

                broadcast_data.append(
                    {
                        "id": cursor.lastrowid,
                        "value": temp,
                        "pwm": pwm,
                        "timestamp": ts_str,
                    }
                )
            except (ValueError, TypeError):
                continue

        conn.commit()
        # broadcast do websocket room
        for data_point in broadcast_data:
            socketio.emit("live_temperature", data_point, room="monitoring")
        return jsonify({"message": "Data saved successfully"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# ---------------------------------------------------------------
#  POMOCNÉ FUNKCIE
# ---------------------------------------------------------------


def start_new_backup_session():
    global active_session_cache
    # Zmena z timezone.utc na LOCAL_TZ
    now_str = datetime.now(LOCAL_TZ).isoformat()

    active_session_cache["start_time"] = now_str
    active_session_cache["recent_measurements"] = []

    try:
        with open(FILE_PATH, "a") as f:
            f.write(json.dumps({"type": "session_start", "timestamp": now_str}) + "\n")
    except Exception as e:
        print(f"Error writing session start to backup: {e}")


def end_backup_session():
    global active_session_cache
    # Zmena z timezone.utc na LOCAL_TZ
    now_str = datetime.now(LOCAL_TZ).isoformat()
    try:
        with open(FILE_PATH, "a") as f:
            f.write(json.dumps({"type": "session_end", "timestamp": now_str}) + "\n")
    except Exception as e:
        print(f"Error writing session end to backup: {e}")

    active_session_cache["start_time"] = None
    active_session_cache["recent_measurements"] = []


def append_measurement_to_backup(temp, pwm, timestamp_str):
    global active_session_cache
    if not active_session_cache["start_time"]:
        start_new_backup_session()

    measurement_node = {
        "type": "measurement",
        "temperature": temp,
        "peltier_pwm": pwm,
        "timestamp": timestamp_str,
    }

    # Udržiavanie obmedzenej cache vyrovnávacej pamäte
    active_session_cache["recent_measurements"].append(measurement_node)
    if len(active_session_cache["recent_measurements"]) > MAX_CACHE_SIZE:
        active_session_cache["recent_measurements"].pop(0)

    try:
        with open(FILE_PATH, "a") as f:
            f.write(json.dumps(measurement_node) + "\n")
    except Exception as e:
        print(f"Error appending measurement to backup: {e}")


def start_new_session_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Volanie uloženej procedúry, ktorá manažuje staré relácie a začína novú
        cursor.callproc("start_new_session")
        conn.commit()
        print("Nová pracovná relácia úspešne inicializovaná v DB.")
    except mysql.connector.Error as err:
        print(f"Database error pri spúšťaní relácie: {err}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


def end_current_session():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE working_session SET time_end = NOW() WHERE time_end IS NULL"
        )
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# ---------------------------------------------------------------
#  DEBUG ENDPOINTY - pre testovanie a simuláciu dát
# ---------------------------------------------------------------
@app.route("/api/session/current", methods=["GET"])
def get_current_session_data():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Získať aktuálnu session
        cursor.execute("""
            SELECT id FROM working_session
            WHERE time_end IS NULL
            ORDER BY time_start DESC LIMIT 1
        """)
        session = cursor.fetchone()

        if not session:
            return jsonify({"error": "No active session found"}), 404

        session_id = session["id"]

        # Získať všetky merania pre aktuálnu session
        cursor.execute(
            """
            SELECT temperature, peltier_pwm, time_measured 
            FROM temperature_measurements 
            WHERE session_id = %s
            ORDER BY time_measured ASC
        """,
            (session_id,),
        )
        rows = cursor.fetchall()

        measurements = [
            {
                "temperature": (
                    float(row["temperature"])
                    if row["temperature"] is not None
                    else None
                ),
                "peltier_pwm": (
                    int(row["peltier_pwm"]) if row["peltier_pwm"] is not None else None
                ),
                "time_measured": (
                    row["time_measured"].isoformat()
                    if isinstance(row["time_measured"], datetime)
                    else row["time_measured"]
                ),
            }
            for row in rows
        ]

        return jsonify({"session_id": session_id, "measurements": measurements}), 200

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
