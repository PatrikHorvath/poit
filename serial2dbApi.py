import serial
from serial import SerialException
import json
import requests
import time
import random
import os
from datetime import datetime
from dotenv import load_dotenv
import socketio

load_dotenv()

USE_DUMMY_DATA = False  # True = generuje náhodné dáta, False = číta z COM portu
SERIAL_PORT = "COM5"
BAUD_RATE = 115200
API_URL = "https://dietpi.tailfa8c79.ts.net/api/measurements"
STATUS_URL = "https://dietpi.tailfa8c79.ts.net/api/device/status"
WS_URL = "https://dietpi.tailfa8c79.ts.net"
SECRET_KEY = os.getenv("SECRET_KEY")
DEVICE_ID = "Arduino_Peltier_MiddleManComputer"
SEND_THRESHOLD = 1
VERIFY_SSL = True

THINGSBOARD_TELEMETRY_URL = (
    "http://eu.thingsboard.cloud/api/v1/hz7h7ollbxpxwy95qnvi/telemetry"
)

sio = socketio.Client(ssl_verify=VERIFY_SSL)
system_active = False
ser_global = None


@sio.event
def connect():
    sio.emit("register_device", {"secret_key": SECRET_KEY, "device_id": DEVICE_ID})


@sio.on("registration_success")
def on_registration_success(data):
    print("Registrácia zariadenia cez WebSocket prebehla úspešne.")
    check_and_sync_initial_debug_state()


@sio.on("registration_error")
def on_registration_error(data):
    print(f"Chyba registrácie cez WebSocket: {data.get('error')}")
    sio.disconnect()


@sio.on("control_command")
def on_control_command(data):
    global system_active, ser_global
    print(f"Prijatý príkaz z backendu: {data}")
    command = data.get("command")

    if command == "on":
        if not system_active:
            print("Spúšťam zber dát na základe príkazu z backendu...")
            system_active = True
            send_command_to_arduino({"command": "on"})
    elif command == "off":
        if system_active:
            print("Zastavujem zber dát na základe príkazu z backendu...")
            system_active = False
            send_command_to_arduino({"command": "off"})
    elif command == "set_pwm":
        pwm_value = data.get("value")
        print(f"Nastavujem manuálne PWM na: {pwm_value}%")
        send_command_to_arduino({"command": "set_pwm", "value": pwm_value})
    elif command == "set_setpoint":
        sp_value = data.get("value")
        print(f"Nastavujem setpoint na: {sp_value}")
        send_command_to_arduino({"command": "set_setpoint", "value": sp_value})


def check_and_sync_initial_debug_state():
    """Zistí aktuálny stav debug režimu z API a odošle ho do Arduina."""
    try:
        print("Zisťujem počiatočný stav debug režimu z API...")
        response = requests.get(STATUS_URL, verify=VERIFY_SSL, timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            debug_mode = status_data.get("debug_mode", False)
            print(f"Aktuálny debug režim na serveri: {debug_mode}")
            send_command_to_arduino({"command": "debug_state", "enabled": debug_mode})
        else:
            print(f"Nepodarilo sa získať stav zariadenia z API: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Chyba pri komunikácii s API pre získanie stavu: {e}")


def send_command_to_arduino(payload):
    global ser_global
    command = payload.get("command")
    cmd_str = ""

    if command == "on":
        cmd_str = "ON\n"
    elif command == "off":
        cmd_str = "OFF\n"
    elif command == "debug_state":
        state = 1 if payload.get("enabled", False) else 0
        cmd_str = f"DEBUG:{state}\n"
    elif command == "set_pwm":
        cmd_str = f"PWM:{payload.get('value', 0)}\n"
    elif command == "set_setpoint":
        cmd_str = f"SP:{payload.get('value', 23.0)}\n"

    if USE_DUMMY_DATA:
        print(f"[SIMULÁCIA ARDUINO] Odoslané do Arduina: {cmd_str.strip()}")
        return

    if ser_global and ser_global.is_open:
        try:
            ser_global.write(cmd_str.encode("utf-8"))
            ser_global.flush()
            print(f"Odoslané do Arduina cez sériový port: {cmd_str.strip()}")
        except SerialException as e:
            print(f"Chyba pri zápise na sériový port: {e}")
    else:
        print("Chyba: Nie je možné odoslať príkaz, sériový port nie je otvorený.")


def get_dummy_measurement():
    """Generuje náhodný objekt merania pre testovacie účely."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": round(random.uniform(20.0, 30.0), 2),
        "pwm_peltier": random.randint(0, 100),
        "setpoint": 23.0,
    }


def main():
    global system_active, ser_global
    data_buffer = []

    try:
        if not USE_DUMMY_DATA:
            ser_global = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Monitorujem port {SERIAL_PORT}...")
            print("Čakám na reštart Arduina po otvorení portu...")
            time.sleep(2)
        else:
            print("Režim simulácie: Generujem dummy dáta...")

        sio.connect(WS_URL)
        print("Čakám na príkaz 'on' z backendu pre spustenie merania...")

        while True:
            if not system_active:
                time.sleep(0.5)
                if data_buffer:
                    data_buffer.clear()
                continue

            if USE_DUMMY_DATA:
                time.sleep(1)
                measurement = get_dummy_measurement()
            else:
                if ser_global.in_waiting > 0:
                    line = ser_global.readline().decode("utf-8").strip()
                    if line.startswith("DATA:"):
                        try:
                            parts = line.split(":", 1)[1].split(",")
                            temp_val = float(parts[0])
                            pwm_val = int(parts[1])
                            sp_val = float(parts[2])
                            measurement = {
                                "timestamp": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "temperature": temp_val,
                                "pwm_peltier": pwm_val,
                                "setpoint": sp_val,
                            }
                        except (ValueError, IndexError):
                            print(f"Chyba formátu dát z Arduina: {line}")
                            continue
                    else:
                        continue
                else:
                    continue

            data_buffer.append(measurement)
            print(f"Prijaté dáta ({len(data_buffer)}/{SEND_THRESHOLD}): {measurement}")

            if len(data_buffer) >= SEND_THRESHOLD:
                send_to_api(data_buffer)
                send_to_thingsboard(data_buffer)
                data_buffer.clear()

    except SerialException as e:
        print(f"Chyba sériového portu: {e}")
    except KeyboardInterrupt:
        print("\nUkončujem program...")
    finally:
        if ser_global and ser_global.is_open:
            ser_global.close()
        sio.disconnect()


def send_to_api(payload):
    try:
        print(f"Odosielam {len(payload)} záznamov na interné API...")
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json", "X-Device-Token": SECRET_KEY},
            verify=VERIFY_SSL,
            timeout=10,
        )
        if response.status_code in [200, 201]:
            print("Dáta boli úspešne uložené do databázy.")
        else:
            print(f"API vrátilo chybu: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Nepodarilo sa spojiť s API: {e}")


def send_to_thingsboard(payload_buffer):
    try:
        print(f"Odosielam {len(payload_buffer)} záznamov na ThingsBoard...")

        formatted_telemetry = []
        for entry in payload_buffer:
            try:
                dt = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
                ts_ms = int(dt.timestamp() * 1000)
            except ValueError:
                ts_ms = int(time.time() * 1000)

            formatted_telemetry.append(
                {
                    "ts": ts_ms,
                    "values": {
                        "temperature": entry["temperature"],
                        "pwm_peltier": entry["pwm_peltier"],
                        "setpoint": entry.get("setpoint", 23.0),
                    },
                }
            )

        response = requests.post(
            THINGSBOARD_TELEMETRY_URL,
            json=formatted_telemetry,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code in [200, 201]:
            print("Dáta boli úspešne odoslané do ThingsBoard.")
        else:
            print(f"ThingsBoard vrátil chybu: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Nepodarilo sa spojiť s ThingsBoard: {e}")


if __name__ == "__main__":
    main()
