# Súbor je určený na spúšťanie na počítači alebo NodeNCU, ktorý komunikuje s Arduino UNO R3

"""_summary_

Čítanie: 115200 baud
COM / TTY port

Formát dát:
{
    "timestamp": "YYYY-MM-DD HH:MM:SS",
    "temperature": float,
    "pwm_peltier": int, [%]
}

Odosielanie na API:    JSON, každých X meraní (počet špecifikujeme po implementácii)

API Endpoint: dietpi.tailfa8c79.ts.net/dbdata/session
Metóda: POST
"""

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

# --- KONFIGURÁCIA ---
USE_DUMMY_DATA = True  # True = generuje náhodné dáta, False = číta z COM portu
SERIAL_PORT = "COM3"
BAUD_RATE = 115200
API_URL = "https://dietpi.tailfa8c79.ts.net/api/measurements"
STATUS_URL = "https://dietpi.tailfa8c79.ts.net/api/device/status"
WS_URL = "https://dietpi.tailfa8c79.ts.net"
SECRET_KEY = os.getenv("SECRET_KEY")
DEVICE_ID = "Arduino_Peltier_MiddleManComputer"
SEND_THRESHOLD = 10

VERIFY_SSL = True

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
    if USE_DUMMY_DATA:
        print(f"[SIMULÁCIA ARDUINO] Odoslané do Arduina: {json.dumps(payload)}")
        return

    if ser_global and ser_global.is_open:
        try:
            json_command = json.dumps(payload) + "\n"
            ser_global.write(json_command.encode("utf-8"))
            ser_global.flush()
            print(f"Odoslané do Arduina cez sériový port: {json_command.strip()}")
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
    }


def main():
    global system_active, ser_global
    data_buffer = []

    try:
        if not USE_DUMMY_DATA:
            ser_global = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Monitorujem port {SERIAL_PORT}...")
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

            line = None

            if USE_DUMMY_DATA:
                time.sleep(1)
                measurement = get_dummy_measurement()
            else:
                if ser_global.in_waiting > 0:
                    line = ser_global.readline().decode("utf-8").strip()
                    try:
                        measurement = json.loads(line)
                    except json.JSONDecodeError:
                        if line:
                            print(f"Chyba formátu (neplatný JSON): {line}")
                        continue
                else:
                    continue

            data_buffer.append(measurement)
            print(f"Prijaté dáta ({len(data_buffer)}/{SEND_THRESHOLD}): {measurement}")

            if len(data_buffer) >= SEND_THRESHOLD:
                send_to_api(data_buffer)
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
        print(f"Odosielam {len(payload)} záznamov na API...")
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


# TODO: pridať prenášanie príkazu on/off do Arduina cez sériový port

if __name__ == "__main__":
    main()
