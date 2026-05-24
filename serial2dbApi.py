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

# TODO: Impementovať najeký access token do API, a nadviazanie Session
# aby nebolo možné posielať dáta z iných zdrojov

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

# Načítanie premenných prostredia z .env súboru
load_dotenv()

# --- KONFIGURÁCIA ---
USE_DUMMY_DATA = True  # True = generuje náhodné dáta, False = číta z COM portu
SERIAL_PORT = "COM3"
BAUD_RATE = 115200
API_URL = "https://dietpi.tailfa8c79.ts.net/dbdata/session"
WS_URL = "https://dietpi.tailfa8c79.ts.net"
SECRET_KEY = os.getenv("SECRET_KEY")
DEVICE_ID = "NodeMCU_Temp_Sensor"
SEND_THRESHOLD = 10

# Ak váš tunel/funnel používa self-signed certifikáty, vypnite overovanie zmenou na False
VERIFY_SSL = True

sio = socketio.Client(ssl_verify=VERIFY_SSL)

# Globálny stav určujúci, či má prebiehať generovanie/čítanie dát
system_active = False


@sio.event
def connect():
    sio.emit("register_device", {"secret_key": SECRET_KEY, "device_id": DEVICE_ID})


@sio.on("registration_success")
def on_registration_success(data):
    print("Registrácia zariadenia cez WebSocket prebehla úspešne.")


@sio.on("registration_error")
def on_registration_error(data):
    print(f"Chyba registrácie cez WebSocket: {data.get('error')}")
    sio.disconnect()


@sio.on("control_command")
def on_control_command(data):
    global system_active
    print(f"Prijatý príkaz z backendu: {data}")
    command = data.get("command")

    if command == "on":
        if not system_active:
            print("Spúšťam zber dát na základe príkazu z backendu...")
            system_active = True
    elif command == "off":
        if system_active:
            print("Zastavujem zber dát na základe príkazu z backendu...")
            system_active = False


def get_dummy_measurement():
    """Generuje náhodný objekt merania pre testovacie účely."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": round(random.uniform(20.0, 30.0), 2),
        "pwm_peltier": random.randint(0, 100),
    }


def main():
    global system_active
    data_buffer = []
    ser = None

    try:
        sio.connect(WS_URL)

        if not USE_DUMMY_DATA:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Monitorujem port {SERIAL_PORT}...")
        else:
            print("Režim simulácie: Generujem dummy dáta...")

        print("Čakám na príkaz 'on' z backendu pre spustenie merania...")

        while True:
            # Ak systém nie je aktívny, uspíme slučku a preskočíme spracovanie dát
            if not system_active:
                time.sleep(0.5)
                # Ak bol systém vypnutý počas rozrobeného cyklu, vyčistíme buffer, aby neobsahoval staré dáta
                if data_buffer:
                    data_buffer.clear()
                continue

            line = None

            if USE_DUMMY_DATA:
                time.sleep(1)
                measurement = get_dummy_measurement()
            else:
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8").strip()
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
        if ser and ser.is_open:
            ser.close()
        sio.disconnect()


def send_to_api(payload):
    try:
        print(f"Odosielam {len(payload)} záznamov na API...")
        # Odkomentujte po nasadení API
        # response = requests.post(
        #     API_URL,
        #     json=payload,
        #     headers={"Content-Type": "application/json"},
        #     verify=VERIFY_SSL,
        #     timeout=10,
        # )
        # if response.status_code in [200, 201]:
        #     print("Dáta boli úspešne uložené do databázy.")
        # else:
        #     print(f"API vrátilo chybu: {response.status_code} - {response.text}")

        # Dočasná simulácia úspešného odoslania
        # je potrebné najprv implementovať v API pwm_pump a pwm_peltier
        print("Simulácia odoslania prebehla v poriadku.")

    except requests.exceptions.RequestException as e:
        print(f"Nepodarilo sa spojiť s API: {e}")


if __name__ == "__main__":
    main()
