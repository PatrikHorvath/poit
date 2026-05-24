from cloup import command

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import configparser
import json
import os
from datetime import datetime, timedelta
import warnings
from flask_socketio import SocketIO, emit, join_room, leave_room

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
        "connected_at": datetime.now().isoformat(),
        "device_id": device_id,
    }

    print(f"Device {device_id} registered successfully")
    emit("registration_success", {"status": "registered"})
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


# ---------------------------------------------------------------
#  API ENDPOINTY - pre ovládanie zariadenia a získavanie dát
# ---------------------------------------------------------------


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
            }
        ),
        200,
    )


# endpoint pre prenesenie príkazu z webstránky do zariadenia (zapnúť/vypnúť)
@app.route("/api/device/control", methods=["POST"])
def control_device():
    global device_info
    data = request.get_json()
    command = data.get("command")

    if not device_info["connected"]:
        return jsonify({"error": "Zariadenie nie je pripojené"}), 404

    socketio.emit("control_command", {"command": command}, room=device_info["sid"])

    if command == "on":
        start_new_session_db()
    elif command == "off":
        end_current_session()

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

        if isinstance(payload, list):
            for item in payload:
                temp = item.get("temperature")
                pwm = item.get("pwm_peltier")
                timestamp = item.get("timestamp")
                cursor.execute(query, (temp, pwm, timestamp))
                broadcast_data.append({"value": temp, "timestamp": timestamp})
        else:
            temp = payload.get("temperature")
            pwm = payload.get("pwm_peltier")
            timestamp = payload.get("timestamp")
            cursor.execute(query, (temp, pwm, timestamp))
            broadcast_data.append({"value": temp, "timestamp": timestamp})

        conn.commit()

        # broadcast do websocket room
        for data_point in broadcast_data:
            socketio.emit("live_temperature", data_point, room="monitoring")

        return jsonify({"message": "Data saved successfully"}), 201

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------
#  POMOCNÉ FUNKCIE
# ---------------------------------------------------------------


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
        cursor.close()
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
        cursor.close()
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
        measurements = cursor.fetchall()

        return jsonify({"session_id": session_id, "measurements": measurements}), 200

    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
