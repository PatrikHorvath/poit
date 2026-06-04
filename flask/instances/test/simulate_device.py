import socketio
import time
import random
from datetime import datetime

# Konfigurácia
SECRET_KEY = "-"
SERVER_URL = "http://localhost:5000"

# Vytvorenie Socket.IO klienta
sio = socketio.Client()

@sio.event
def connect():
    print("Pripojené k serveru")
    # Registrácia zariadenia
    sio.emit('register_device', {
        'secret_key': SECRET_KEY,
        'device_id': 'Simulovane_Zariadenie_001'
    })

@sio.event
def disconnect():
    print("Odpojené od serveru")

@sio.event
def registration_success(data):
    print(f"Registrácia úspešná: {data}")

@sio.event
def registration_error(data):
    print(f"Chyba registrácie: {data}")

@sio.event
def control_command(data):
    print(f"Prijatý príkaz: {data}")
    command = data.get('command')
    
    if command == 'on':
        print("Zariadenie bolo ZAPNUTÉ")
        start_sending_data()
    elif command == 'off':
        print("Zariadenie bolo VYPNUTÉ")
        stop_sending_data()

# Premenné pre odosielanie dát
sending_data = False
should_send = False

def start_sending_data():
    global should_send, sending_data
    should_send = True
    if not sending_data:
        sending_data = True
        send_data_loop()

def stop_sending_data():
    global should_send
    should_send = False

def send_data_loop():
    global should_send, sending_data
    while should_send:
        # Generovanie náhodnej teploty (20-35°C)
        temperature = round(random.uniform(20.0, 35.0), 1)
        timestamp = datetime.now().isoformat()
        
        print(f"Odosielam teplotu: {temperature}°C o {timestamp}")
        sio.emit('temperature_data', {
            'temperature': temperature,
            'timestamp': timestamp
        })
        
        time.sleep(2)  # Každé 2 sekundy
    
    sending_data = False

# Pripojenie k serveru
try:
    print("Pripájam sa k serveru...")
    sio.connect(SERVER_URL)
    sio.wait()
except Exception as e:
    print(f"Chyba pripojenia: {e}")